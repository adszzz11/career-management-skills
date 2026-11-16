#!/usr/bin/env python3
"""
레거시 project .md 한 개 + 그게 참조하는 achievement .md들을 읽어서
company/role/problem 트리의 role 디렉터리(root.yaml + problem yaml들)를
자동 생성한다.

지원하는 achievement 본문 포맷 2가지:
  1. 신식: **문제** / **해결** / **결과** 굵은 라벨 3단
  2. 구식: `## story` 아래 불릿 정확히 2개(문제, 해결) — `## one-liner`를
     결과(result)로 대신 쓴다. 세 번째 불릿이 있거나 하나도 없으면
     자동 변환을 포기하고 경고만 남긴다 — 추측해서 지어내지 않는다.

사용법:
  python3 migrate_role.py \
    --project components/project/example-project.md \
    --achievement-dir components/achievement \
    --out components/example-company/example-backend/sample-project \
    [--dry-run]

--dry-run이면 파일을 쓰지 않고 만들 내용을 stdout에 미리 보여준다.
"""
from __future__ import annotations
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import extract as ex  # _split_frontmatter, _extract_h1 등 파싱 헬퍼 재사용


def _yaml_scalar(value: str) -> str:
    """짧은 한 줄 값. 콜론/따옴표가 있으면 큰따옴표로 감싸고 이스케이프."""
    value = value.strip()
    if re.search(r'[:"#]|^\s|\s$', value) or value == "":
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _yaml_folded(key: str, text: str | None, indent: str = "") -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    # minimal_yaml의 folded scalar는 어차피 공백으로 합치므로, 줄바꿈 위치는
    # 가독성만을 위해 60자 근처에서 끊는다(파싱 결과에는 영향 없음).
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 70:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    body = "\n".join(f"{indent}  {l}" for l in lines)
    return f"{indent}{key}: >-\n{body}\n"


def _yaml_list(key: str, items: list[str], indent: str = "") -> str:
    if not items:
        return f"{indent}{key}: []\n"
    lines = "\n".join(f"{indent}  - {_yaml_scalar(it)}" for it in items)
    return f"{indent}{key}:\n{lines}\n"


def _extract_h4_section(text: str, heading: str) -> str | None:
    """`## full` 안에 `#### 서비스 소개`, `#### 주요 업무`처럼 h4로 중첩된 섹션을 뽑는다.
    (h2용 ex._extract_section과 별개 — full 섹션 본문 안에서만 쓴다.)"""
    m = re.search(rf"^####\s+{re.escape(heading)}\s*\n(.*?)(?=^####\s|\Z)", text, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def _split_by_comma(text: str | None) -> list[str]:
    """쉼표로 나누되, 괄호 안의 쉼표는 무시한다 — "JavaScript(Node.js, type:module)"
    같은 기술스택 표기가 "JavaScript(Node.js" / "type:module)"로 두 동강 나던
    버그(실제 sample-workflow 마이그레이션에서 발견) 수정."""
    if not text:
        return []
    parts, buf, depth = [], "", 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def parse_achievement(path: str, warnings: list[str]) -> dict | None:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fm, body = ex._split_frontmatter(text)
    title = ex._extract_h1(body) or os.path.basename(path)[:-3]

    issue = ex._match_bold_field(body, "문제")
    resolution = ex._match_bold_field(body, "해결")
    result = ex._match_bold_field(body, "결과")
    if issue and resolution and result:
        return {"title": title, "issue": issue, "resolution": resolution, "result": result}

    story = ex._extract_section(body, "story")
    bullets = ex._extract_bullets(story)
    if len(bullets) == 2:
        one_liner = ex._extract_section(body, "one-liner") or ""
        return {"title": title, "issue": bullets[0], "resolution": bullets[1], "result": one_liner}

    warnings.append(
        f"자동 변환 실패: {path} — **문제/해결/결과** 3단도 아니고, "
        f"'## story' 불릿 정확히 2개도 아님(불릿 {len(bullets)}개). 수동으로 옮길 것."
    )
    return None


def migrate(project_path: str, achievement_dir: str, out_dir: str, warnings: list[str]) -> tuple[str, dict[str, str]]:
    """(role_root_yaml_text, {filename: problem_yaml_text}) 를 돌려준다. 파일은 안 쓴다."""
    with open(project_path, encoding="utf-8") as f:
        text = f.read()
    fm, body = ex._split_frontmatter(text)

    title = ex._extract_h1(body) or os.path.basename(project_path)[:-3]
    period = fm.get("period")
    tags = fm.get("tags") or []

    one_liner_section = ex._extract_section(body, "one-liner")
    one_liner_bullets = ex._extract_bullets(one_liner_section)
    one_liner = "; ".join(one_liner_bullets) if one_liner_bullets else (one_liner_section or "")

    summary = ex._extract_section(body, "summary")
    full_section = ex._extract_section(body, "full") or ""
    headcount_m = re.search(r"투입인원\s*\|\s*([^|]+?)\s*\|", full_section)
    headcount_raw = headcount_m.group(1).strip() if headcount_m else None
    headcount = int(headcount_raw) if headcount_raw and headcount_raw.isdigit() else None
    stack = _split_by_comma(ex._match_bold_field(full_section, "기술스택"))
    key_results = _split_by_comma(ex._match_bold_field(full_section, "주요 성과"))
    responsibilities = ex._extract_bullets(_extract_h4_section(full_section, "주요 업무"))
    if not responsibilities:
        warnings.append(f"{project_path}: '#### 주요 업무' 불릿을 못 찾음 — role root.yaml의 responsibilities가 비어있음, 수동 확인 필요")

    achv_section = ex._extract_section(body, "업적")
    achv_ids = ex._extract_wikilink_ids(achv_section)

    role_yaml = (
        'type: role\n'
        f'title: {_yaml_scalar(title)}\n'
        f'period: {_yaml_scalar(period or "")}\n'
        + (f'headcount: {headcount}\n' if headcount is not None else '')
        + _yaml_list("tags", tags)
        + _yaml_folded("one_liner", one_liner)
        + _yaml_folded("summary", summary)
        + _yaml_list("stack", stack)
        + _yaml_list("key_results", key_results)
        + _yaml_list("responsibilities", responsibilities)
        + "attachments: []\n"
    )

    problems: dict[str, str] = {}
    for aid in achv_ids:
        apath = os.path.join(achievement_dir, f"{aid}.md")
        if not os.path.isfile(apath):
            warnings.append(f"{project_path}의 [[{aid}]]가 가리키는 {apath} 없음 — 건너뜀")
            continue
        parsed = parse_achievement(apath, warnings)
        if parsed is None:
            continue
        problem_yaml = (
            'type: problem\n'
            f'title: {_yaml_scalar(parsed["title"])}\n'
            + _yaml_folded("issue", parsed["issue"])
            + _yaml_folded("resolution", parsed["resolution"])
            + _yaml_folded("result", parsed["result"])
            + "attachments: []\n"
        )
        problems[f"{aid}.yaml"] = problem_yaml

    return role_yaml, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--achievement-dir", required=True)
    ap.add_argument("--out", required=True, help="생성할 role 디렉터리")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    warnings: list[str] = []
    role_yaml, problems = migrate(args.project, args.achievement_dir, args.out, warnings)

    if args.dry_run:
        print(f"=== {args.out}/root.yaml ===")
        print(role_yaml)
        for fname, content in problems.items():
            print(f"=== {args.out}/{fname} ===")
            print(content)
    else:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "root.yaml"), "w", encoding="utf-8") as f:
            f.write(role_yaml)
        for fname, content in problems.items():
            with open(os.path.join(args.out, fname), "w", encoding="utf-8") as f:
                f.write(content)
        print(f"생성: {args.out}/root.yaml + problem {len(problems)}개")

    if warnings:
        print(f"\n❓ 확인 필요 — {len(warnings)}건:", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
