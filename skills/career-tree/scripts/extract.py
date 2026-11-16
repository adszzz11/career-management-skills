#!/usr/bin/env python3
"""
career-tree 데이터 추출기.

두 가지 소스를 읽어 하나의 career-data.json으로 합친다:

1. --tree-dir  : company/role/problem 트리 (root.yaml + leaf *.yaml)
2. --legacy-dir: 아직 마이그레이션 안 된 기존 components/project, components/achievement
                 (frontmatter + 마크다운 섹션 구조의 .md)

마이그레이션이 끝나면 --legacy-dir 없이 --tree-dir 하나만 넘기면 된다.
두 소스를 동시에 넘겼을 때 같은 role이 양쪽에 다 있는 상황은 이 스크립트가
알아서 판단하지 않는다 — 한쪽을 지우는 건 사람(또는 migrate 스크립트)의 몫이다.

출력 스키마:
{
  "generated_at": "...",
  "companies": [
    {
      "id": "example-company", "title": "...", "period": "...", "description": "...",
      "roles": [
        {
          "id": "core-pipeline", "group": "example-backend" | null,
          "title": "...", "period": "...", "headcount": 1, "tags": [...],
          "stack": [...], "key_results": [...], "summary": "...",
          "problems": [
            {"id": "...", "title": "...", "issue": "...", "resolution": "...", "result": "..."}
          ]
        }
      ]
    }
  ]
}
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import minimal_yaml as yml


# ---------- 1. 새 트리(company/role/problem, root.yaml) ----------

def load_tree(tree_dir: str) -> list[dict]:
    companies = []
    if not os.path.isdir(tree_dir):
        return companies

    for company_name in sorted(os.listdir(tree_dir)):
        company_path = os.path.join(tree_dir, company_name)
        root_yaml = os.path.join(company_path, "root.yaml")
        if not os.path.isdir(company_path) or not os.path.isfile(root_yaml):
            continue
        company_data = yml.load_file(root_yaml)
        if company_data.get("type") != "company":
            continue

        company = {
            "id": company_name,
            "title": company_data.get("title", company_name),
            "period": company_data.get("period"),
            "description": company_data.get("description"),
            "roles": [],
        }
        _walk_for_roles(company_path, group=None, roles_out=company["roles"])
        companies.append(company)
    return companies


def _walk_for_roles(dir_path: str, group: str | None, roles_out: list[dict]):
    """company_path 아래를 재귀 탐색해서 type: role인 디렉터리를 전부 찾는다.
    role 디렉터리를 만나면 그 아래로는 더 들어가지 않는다(problem은 leaf 파일이므로)."""
    for name in sorted(os.listdir(dir_path)):
        sub = os.path.join(dir_path, name)
        root_yaml = os.path.join(sub, "root.yaml")
        if not os.path.isdir(sub) or not os.path.isfile(root_yaml):
            continue
        node = yml.load_file(root_yaml)
        node_type = node.get("type")

        if node_type == "role":
            roles_out.append(_load_role(sub, node, name, group))
        elif node_type == "group":
            _walk_for_roles(sub, group=name, roles_out=roles_out)
        # company 타입은 이 함수에 다시 들어올 일이 없음(load_tree가 최상위만 처리)


def _load_role(role_dir: str, node: dict, role_id: str, group: str | None) -> dict:
    problems = []
    for fname in sorted(os.listdir(role_dir)):
        if fname == "root.yaml" or not fname.endswith(".yaml"):
            continue
        pdata = yml.load_file(os.path.join(role_dir, fname))
        if pdata.get("type") != "problem":
            continue
        problems.append({
            "id": fname[:-len(".yaml")],
            "title": pdata.get("title"),
            "issue": pdata.get("issue"),
            "resolution": pdata.get("resolution"),
            "result": pdata.get("result"),
            "attachments": pdata.get("attachments") or [],
        })
    return {
        "id": role_id,
        "group": group,
        "title": node.get("title", role_id),
        "period": node.get("period"),
        "headcount": node.get("headcount"),
        "tags": node.get("tags") or [],
        "one_liner": node.get("one_liner"),
        "summary": node.get("summary"),
        "stack": node.get("stack") or [],
        "key_results": node.get("key_results") or [],
        "attachments": node.get("attachments") or [],
        "problems": problems,
        "source": "tree",
    }


# ---------- 2. 레거시(components/project/*.md + components/achievement/*.md) ----------

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def _split_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    return yml.parse(fm_text), body


def _extract_h1(body: str) -> str | None:
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else None


def _extract_section(body: str, heading: str) -> str | None:
    """`## heading` 다음, 다음 `##`(또는 문서 끝)까지의 본문을 반환."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_bullets(section_text: str | None) -> list[str]:
    """`- ...` 불릿 라인을 뽑는다. 중첩 불릿(`  - ...`)도 들여쓰기와 무관하게
    같은 레벨로 평탄화한다 — 계층은 버리지만 "- Core 로직 개발..."처럼 원본
    대시가 텍스트에 그대로 남는 것보다는 낫다(실제로 이 흔적이 role
    root.yaml에 그대로 새어나간 적이 있다)."""
    if not section_text:
        return []
    result = []
    for l in section_text.split("\n"):
        stripped = l.strip()
        if stripped.startswith("- "):
            result.append(re.sub(r"^-\s+", "", stripped))
    return result


def _extract_wikilink_ids(section_text: str | None) -> list[str]:
    if not section_text:
        return []
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", section_text)


def load_company_aliases(path: str) -> dict[str, str]:
    """레거시 org: 값 -> 트리 company id 매핑. 파일이 없으면 빈 dict.
    (path는 company-aliases.yaml 파일 자체의 경로. 테스트에서 픽스처 경로를
    바로 넘길 수 있도록 skill_dir이 아니라 파일 경로를 직접 받는다.)"""
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read()
    aliases = {}
    for line in text.split("\n"):
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        org, _, cid = line.partition(":")
        aliases[org.strip()] = cid.strip()
    return aliases


def load_legacy(
    legacy_dir: str,
    aliases: dict[str, str] | None = None,
    known_company_ids: set[str] | None = None,
    warnings: list[str] | None = None,
) -> list[dict]:
    aliases = aliases or {}
    known_company_ids = known_company_ids or set()
    warnings = warnings if warnings is not None else []
    project_dir = os.path.join(legacy_dir, "project")
    achievement_dir = os.path.join(legacy_dir, "achievement")

    achievements_by_id: dict[str, dict] = {}
    referenced_achievement_ids: set[str] = set()
    unmapped_orgs_warned: set[str] = set()
    if os.path.isdir(achievement_dir):
        for fname in sorted(os.listdir(achievement_dir)):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(achievement_dir, fname)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            fm, body = _split_frontmatter(text)
            title = _extract_h1(body) or fname[:-3]
            issue = _match_bold_field(body, "문제")
            resolution = _match_bold_field(body, "해결")
            result = _match_bold_field(body, "결과")
            achievements_by_id[fname[:-3]] = {
                "id": fname[:-3],
                "title": title,
                "issue": issue,
                "resolution": resolution,
                "result": result,
                "attachments": [],
            }

    companies: dict[str, dict] = {}
    if os.path.isdir(project_dir):
        for fname in sorted(os.listdir(project_dir)):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(project_dir, fname)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            fm, body = _split_frontmatter(text)
            org = fm.get("org", "미상")
            if org in aliases:
                company_id = aliases[org]
            else:
                company_id = _slugify(org)
                if known_company_ids and company_id not in known_company_ids and org not in unmapped_orgs_warned:
                    unmapped_orgs_warned.add(org)
                    warnings.append(
                        f"미해결 회사 매핑: org='{org}' (예: {fname}) 가 company-aliases.yaml에도 없고 "
                        f"트리의 어느 company id와도 안 맞음(추정 id='{company_id}'). "
                        f"기존 회사의 다른 표기인지, 정말 새 회사인지 확인 필요 — "
                        f"확인되면 company-aliases.yaml에 '{org}: <올바른 id>' 추가."
                    )
            company = companies.setdefault(company_id, {
                "id": company_id,
                "title": org,
                "period": None,
                "description": None,
                "roles": [],
            })

            role_id = fname[:-3]
            achv_section = _extract_section(body, "업적")
            problem_ids = _extract_wikilink_ids(achv_section)
            problems = []
            for pid in problem_ids:
                if pid in achievements_by_id:
                    problems.append(achievements_by_id[pid])
                    referenced_achievement_ids.add(pid)
                else:
                    warnings.append(
                        f"끊어진 링크: {fname}의 [[{pid}]]가 achievement/{pid}.md를 가리키는데 "
                        f"그 파일이 없음."
                    )

            full_section = _extract_section(body, "full") or ""
            stack = _match_bold_field(full_section, "기술스택")
            key_results = _match_bold_field(full_section, "주요 성과")

            company["roles"].append({
                "id": role_id,
                "group": None,
                "title": _extract_h1(body) or role_id,
                "period": fm.get("period"),
                "headcount": None,
                "tags": fm.get("tags") or [],
                "one_liner": _extract_section(body, "one-liner"),
                "summary": _extract_section(body, "summary"),
                "stack": [s.strip() for s in stack.split(",")] if stack else [],
                "key_results": [s.strip() for s in key_results.split(",")] if key_results else [],
                "attachments": [],
                "problems": problems,
                "source": "legacy",
            })

    orphan_ids = set(achievements_by_id) - referenced_achievement_ids
    for oid in sorted(orphan_ids):
        warnings.append(
            f"고아 achievement: achievement/{oid}.md가 어느 project의 '## 업적'에서도 "
            f"[[{oid}]]로 참조되지 않음 — 대시보드/이력서에 절대 안 나타남. "
            f"참조를 추가하거나, 정말 안 쓰는 파일이면 삭제 검토."
        )

    return list(companies.values())


def _match_bold_field(text: str, label: str) -> str | None:
    m = re.search(rf"\*\*{re.escape(label)}\*\*[:：]?\s*(.+?)(?=\n\n|\Z)", text, re.DOTALL)
    if not m:
        return None
    return " ".join(l.strip() for l in m.group(1).strip().split("\n")).strip()


def _slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9가-힣]+", "-", s).strip("-").lower()


# ---------- merge + main ----------

def _normalize_title(s: str | None) -> str:
    return re.sub(r"[^a-z0-9가-힣]", "", (s or "").lower())


def detect_duplicate_roles(companies: list[dict]) -> list[str]:
    """마이그레이션 도중 같은 role이 tree에도 legacy에도 남아있는 상태를 잡는다.
    (제목이 똑같으면 십중팔구 같은 일이다 — extract.py는 이걸 알아서 하나로
    합치거나 어느 한쪽을 버리지 않는다. 사람이 legacy 원본을 지워야 한다.)"""
    warnings = []
    for c in companies:
        tree_roles = [r for r in c.get("roles", []) if r.get("source") == "tree"]
        legacy_roles = [r for r in c.get("roles", []) if r.get("source") == "legacy"]
        for tr in tree_roles:
            tr_title = _normalize_title(tr.get("title"))
            if not tr_title:
                continue
            for lr in legacy_roles:
                if tr_title == _normalize_title(lr.get("title")):
                    warnings.append(
                        f"중복 의심 role: company='{c['id']}'에 tree role '{tr['id']}'"
                        f"({tr.get('title')})와 legacy role '{lr['id']}'({lr.get('title')})가 "
                        f"제목이 똑같음 — 같은 일을 두 번 마이그레이션한 것으로 보임. "
                        f"마이그레이션이 끝났다면 레거시 project .md(및 거기서만 참조되는 "
                        f"achievement .md들)를 지워야 대시보드에서 중복이 사라짐."
                    )
    return warnings


def merge(tree_companies: list[dict], legacy_companies: list[dict]) -> list[dict]:
    by_id = {c["id"]: c for c in tree_companies}
    for lc in legacy_companies:
        if lc["id"] in by_id:
            by_id[lc["id"]]["roles"].extend(lc["roles"])
        else:
            by_id[lc["id"]] = lc
    return list(by_id.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree-dir", default=None, help="company/role/problem 트리 루트")
    ap.add_argument("--legacy-dir", default=None, help="기존 components/project, components/achievement가 있는 디렉터리")
    ap.add_argument("--out", default="career-data.json")
    ap.add_argument(
        "--aliases",
        default=None,
        help="company-aliases.yaml 경로 (기본값: 이 스크립트 기준 ../company-aliases.yaml)",
    )
    args = ap.parse_args()

    aliases_path = args.aliases or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "company-aliases.yaml"
    )
    aliases = load_company_aliases(aliases_path)
    tree_companies = load_tree(args.tree_dir) if args.tree_dir else []
    known_company_ids = {c["id"] for c in tree_companies} | set(aliases.values())

    warnings: list[str] = []
    legacy_companies = (
        load_legacy(args.legacy_dir, aliases, known_company_ids, warnings)
        if args.legacy_dir else []
    )
    companies = merge(tree_companies, legacy_companies)
    warnings.extend(detect_duplicate_roles(companies))

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "companies": companies,
        "warnings": warnings,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    n_roles = sum(len(c["roles"]) for c in companies)
    n_problems = sum(len(r["problems"]) for c in companies for r in c["roles"])
    print(f"{args.out}: company {len(companies)}, role {n_roles}, problem {n_problems}")

    if warnings:
        print(f"\n❓ 확인 필요 — {len(warnings)}건 (조용히 넘어가지 말고 사용자에게 물어볼 것):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        sys.exit(2)  # 성공(0)도 하드 에러(1)도 아닌, "사람 판단 필요"


if __name__ == "__main__":
    main()
