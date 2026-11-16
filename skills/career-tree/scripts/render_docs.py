#!/usr/bin/env python3
"""
career-data.json(company/role/problem 트리를 추출한 결과)에서 이력서(요약)와
경력기술서(상세) 마크다운을 생성한다.

**주의**: 이 트리에는 활동/자격/학력(profile, mentoring, talk 컴포넌트) 같은
career 외 정보가 없다 — 이 스크립트는 "경력기술 요약"/"경력기술 상세" 섹션만
만든다. 최종 문서에는 그 앞뒤에 자격/활동 섹션을 사람이 붙여야 한다(또는
나중에 이 스킬을 profile/mentoring/talk까지 확장한다).

사용법:
  python3 render_docs.py --data career-data.json \
    --resume-out resume-generated.md \
    --detail-out career-description-generated.md
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys


def _current_first_sort_key(company: dict):
    period = company.get("period") or ""
    is_current = "현재" in period
    m = re.search(r"(\d{4})", period)
    start_year = int(m.group(1)) if m else 0
    return (0 if is_current else 1, -start_year)


_STOPWORDS = {
    "the", "and", "for", "with", "you", "our", "are", "이상", "업무", "경력",
    "개발", "회사", "우대", "지원", "포함", "이상의", "관련",
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z가-힣0-9][a-zA-Z가-힣0-9+.#/_-]*", (text or "").lower())
    return {t for t in tokens if len(t) >= 2 and t not in _STOPWORDS}


def _role_text_blob(role: dict) -> str:
    parts = [
        role.get("title") or "",
        role.get("one_liner") or "",
        role.get("summary") or "",
        " ".join(role.get("tags") or []),
        " ".join(role.get("stack") or []),
    ]
    return " ".join(parts)


def _role_start_year(role: dict) -> int:
    m = re.search(r"(\d{4})", role.get("period") or "")
    return int(m.group(1)) if m else 0


def _score_roles(data: dict, jd_tokens: set[str]) -> list[dict]:
    """모든 role에 점수를 매긴 flat 리스트를 점수 내림차순으로 돌려준다.
    각 항목: {company_idx, role_idx, role, company, score, relevance,
    matched_tokens, excluded_reason(있으면 제외됨)}.
    select_roles_for_resume()와 매칭 근거 리포트(generate_application.py)가
    같은 점수 계산 로직을 공유하려고 분리했다 — 필터링 기준과 "왜 이 role을
    골랐는지" 설명이 서로 다른 코드에서 따로 계산되다 어긋나는 걸 막는다.
    """
    scored = []
    for ci, c in enumerate(data["companies"]):
        for ri, r in enumerate(c.get("roles", [])):
            role_tokens = _tokenize(_role_text_blob(r))
            matched = sorted(jd_tokens & role_tokens) if jd_tokens else []
            relevance = len(matched)
            recency = -ci * 1000 + _role_start_year(r)
            is_rnd = "r&d" in [t.lower() for t in (r.get("tags") or [])]
            excluded_reason = None
            if is_rnd and relevance == 0:
                excluded_reason = "r&d/미병합 태그 + JD 관련 키워드 없음"
            score = relevance * 10000 + recency
            scored.append({
                "company_idx": ci, "role_idx": ri, "role": r, "company": c,
                "score": score, "relevance": relevance, "matched_tokens": matched,
                "excluded_reason": excluded_reason,
            })
    scored.sort(key=lambda t: t["score"], reverse=True)
    return scored


def filter_roles_by_id(data: dict, role_ids: list[str]) -> dict:
    """자동 스코어링을 건너뛰고 지정한 role id만 남긴다(원래 순서 유지).

    실제로 키워드 겹침 개수만 보는 `select_roles_for_resume()`가 JD와
    "개념적으로" 잘 맞는 role(예: 분산 Control Plane인데 정작 JD엔 'Control
    Plane'이라는 단어가 없는 경우)을 놓치고, 흔한 단어 하나("spring" 등)만
    겹치는 role을 여러 개 우선 채택한 실제 사례가 있었다. 그런 걸 사람이
    보고 바로잡을 때 쓰는 수동 오버라이드 — `render_match_rationale_md()`로
    자동 결과를 먼저 보고, 이상하면 이걸로 직접 고른다."""
    wanted = set(role_ids)
    out_companies = []
    for c in data["companies"]:
        kept = [r for r in c.get("roles", []) if r.get("id") in wanted]
        if kept:
            out_companies.append({**c, "roles": kept})
    return {**data, "companies": out_companies}


def select_roles_for_resume(data: dict, jd_text: str | None = None, budget: int = 12) -> dict:
    """이력서 한 페이지에 들어갈 role만 골라, company 구조는 그대로 유지한 채
    돌려준다(순서는 원래 트리 순서를 지킴 — 점수순으로 재배열하지 않는다).

    - JD가 있으면: JD 토큰과 role의 title/one_liner/summary/tags/stack 겹침
      개수로 관련도를 매기고, 관련도 높은 role을 우선 채택한다. **이 방식은
      키워드 겹침 개수만 보는 얕은 매칭이라 개념적으로는 잘 맞아도 문구가
      안 겹치면 놓칠 수 있다** — 실제 지원 전에는 `매칭-근거.md`를 사람이
      한 번 읽고, 이상하면 `filter_roles_by_id()`로 직접 골라 덮어쓴다.
    - JD가 없거나 관련도가 낮은 role만 남으면: "최근 회사 위주로" — 회사
      최신순(현재 재직 중 먼저) → 같은 회사 안에서는 role 시작연도 최신순으로
      채택한다(사용자가 명시한 기본 방침).
    - `tags`에 `r&d`가 있는 role(예: 미병합 R&D)은 JD가 그 role과 뚜렷하게
      관련될 때만 포함하고, 기본적으로는 이력서에서 제외한다(경력기술서에는
      항상 남아있음 — 이 함수는 이력서 렌더링에만 쓴다).
    """
    jd_tokens = _tokenize(jd_text) if jd_text else set()
    scored = [s for s in _score_roles(data, jd_tokens) if s["excluded_reason"] is None]
    keep_keys = {(s["company_idx"], s["role_idx"]) for s in scored[:budget]}

    out_companies = []
    for ci, c in enumerate(data["companies"]):
        kept_roles = [r for ri, r in enumerate(c.get("roles", [])) if (ci, ri) in keep_keys]
        if kept_roles:
            out_companies.append({**c, "roles": kept_roles})
    return {**data, "companies": out_companies}


def render_match_rationale_md(data: dict, jd_text: str | None, budget: int, company_name: str) -> str:
    """"매칭-근거.md" — 왜 이 role들을 이력서에 넣었고 뭘 뺐는지 사람이 읽을
    문장으로 남긴다. generate_application.py가 JD별 산출 디렉터리에 같이 쓴다."""
    jd_tokens = _tokenize(jd_text) if jd_text else set()
    scored = _score_roles(data, jd_tokens)

    lines = [f"# {company_name} 지원 — 이력서 role 매칭 근거\n"]
    lines.append(f"JD 제공 여부: {'있음' if jd_text else '없음'} · role 예산: {budget}개\n")

    included = [s for s in scored if s["excluded_reason"] is None][:budget]
    excluded_by_budget = [s for s in scored if s["excluded_reason"] is None][budget:]
    excluded_by_rule = [s for s in scored if s["excluded_reason"] is not None]

    lines.append("## 채택된 role\n")
    for s in included:
        title = s["role"].get("title") or s["role"].get("id")
        reason = (
            f"JD 키워드 일치: {', '.join(s['matched_tokens'])}"
            if s["matched_tokens"] else "관련 키워드 없음 — 최근 회사/최신 role 우선 기본값으로 채택"
        )
        lines.append(f"- **{title}** ({s['company']['title']}, {s['role'].get('period','')}) — {reason}")

    if excluded_by_budget:
        lines.append("\n## 점수는 됐지만 예산 초과로 뺀 role\n")
        for s in excluded_by_budget[:10]:
            title = s["role"].get("title") or s["role"].get("id")
            lines.append(f"- {title} ({s['company']['title']})")

    if excluded_by_rule:
        lines.append("\n## 규칙으로 제외된 role\n")
        for s in excluded_by_rule:
            title = s["role"].get("title") or s["role"].get("id")
            lines.append(f"- {title} — {s['excluded_reason']}")

    return "\n".join(lines) + "\n"


def render_resume(data: dict) -> str:
    lines = ["# 이력서\n"]
    companies = sorted(data["companies"], key=_current_first_sort_key)
    for c in companies:
        lines.append(f"### {c['title']}({c.get('period', '')})\n")
        if c.get("description"):
            lines.append(f"{c['description']}\n")
        for r in c.get("roles", []):
            title = r.get("title") or r.get("id")
            period = r.get("period") or ""
            lines.append(f"**{title}({period})**\n")
            one_liner = r.get("one_liner") or r.get("summary") or ""
            if one_liner:
                lines.append(f"- {one_liner}\n")
        lines.append("")
    return "\n".join(lines)


def render_detail(data: dict) -> str:
    lines = ["# 경력기술서\n"]
    companies = sorted(data["companies"], key=_current_first_sort_key)
    for c in companies:
        lines.append(f"## {c['title']} — {c.get('period', '')}\n")
        if c.get("description"):
            lines.append(f"> {c['description']}\n")
        lines.append("---\n")
        for r in c.get("roles", []):
            title = r.get("title") or r.get("id")
            period = r.get("period") or ""
            headcount = r.get("headcount")
            lines.append(f"### {title}\n")
            lines.append(f"| 기간 | {period} | 투입인원 | {headcount if headcount is not None else '-'} |")
            lines.append("|---|---|---|---|\n")
            if r.get("stack"):
                lines.append(f"**기술스택**: {', '.join(r['stack'])}\n")
            if r.get("key_results"):
                lines.append(f"**주요 성과**: {', '.join(r['key_results'])}\n")
            if r.get("summary"):
                lines.append("#### 서비스 소개\n")
                lines.append(f"{r['summary']}\n")
            if r.get("responsibilities"):
                lines.append("#### 주요 업무\n")
                for item in r["responsibilities"]:
                    lines.append(f"- {item}")
                lines.append("")
            problems = r.get("problems") or []
            if problems:
                lines.append("#### 문제 해결\n")
                for p in problems:
                    lines.append(f"**{p.get('title', '')}**\n")
                    if p.get("issue"):
                        lines.append(f"- {p['issue']}")
                    if p.get("resolution"):
                        lines.append(f"- {p['resolution']}")
                    if p.get("result"):
                        lines.append(f"- {p['result']}")
                    lines.append("")
            lines.append("---\n")
    return "\n".join(lines)


def _esc(s: str | None) -> str:
    if s is None:
        return ""
    return (
        str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


# --------------------------------------------------------------------------
# 디자인 템플릿 — design/templates.md의 "디자인 방향" 옵션을 실제 코드로 구현.
# 색 팔레트만 다르고 구조(레이아웃/클래스명)는 셋 다 동일 — 템플릿을 늘릴 때도
# 여기 팔레트 dict만 추가하면 된다. 기본값은 항상 "blue"(design-system.md에
# 확정된 값과 일치) — 사용자가 명시적으로 --design-template을 안 넘기면 이걸
# 조용히 다른 걸로 바꾸지 않는다.
# --------------------------------------------------------------------------
DESIGN_TEMPLATES = {
    "blue": {  # design/templates.md ✅ 기본값 — 기존 손질 이력서 스타일
        "label": "기존 스타일(#1F4E79 블루)",
        "font": '"Malgun Gothic", "Apple SD Gothic Neo", sans-serif',
        "primary": "#1F4E79", "accent": "#2E74B5", "border": "#DEEBF7",
        "muted": "#666666", "text": "#333333", "heading_transform": "none", "heading_spacing": "normal",
    },
    "mono": {  # 검토했던 "미니멀 모노크롬" 옵션 — 흑백 + 포인트컬러 없음
        "label": "미니멀 모노크롬",
        "font": '"Apple SD Gothic Neo", "Malgun Gothic", sans-serif',
        "primary": "#111111", "accent": "#111111", "border": "#CCCCCC",
        "muted": "#666666", "text": "#222222", "heading_transform": "uppercase", "heading_spacing": ".03em",
    },
    "modern": {  # 세 번째 옵션 — 차콜 + 틸 포인트, 좀 더 현대적인 톤
        "label": "모던 차콜·틸",
        "font": '"Apple SD Gothic Neo", "Malgun Gothic", sans-serif',
        "primary": "#1F2A24", "accent": "#0E7C7B", "border": "#D8E6E4",
        "muted": "#5B6B66", "text": "#26312C", "heading_transform": "none", "heading_spacing": "normal",
    },
}
DEFAULT_TEMPLATE = "blue"


def _template(name: str | None) -> dict:
    return DESIGN_TEMPLATES.get(name or DEFAULT_TEMPLATE, DESIGN_TEMPLATES[DEFAULT_TEMPLATE])


def _resume_css(t: dict) -> str:
    return f"""
  @page {{ size: A4; margin: 14mm 16mm; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: {t['font']}; color: {t['text']}; font-size: 9.5pt; line-height: 1.5; }}
  h1 {{ color: {t['primary']}; font-size: 16pt; margin-bottom: 4px; text-transform: {t['heading_transform']}; letter-spacing: {t['heading_spacing']}; }}
  h2 {{ color: {t['accent']}; font-size: 12pt; margin: 14px 0 6px; border-bottom: 1.5px solid {t['border']}; padding-bottom: 2px; text-transform: {t['heading_transform']}; letter-spacing: {t['heading_spacing']}; }}
  h3 {{ font-size: 10.5pt; color: {t['text']}; margin: 8px 0 3px; }}
  h4 {{ font-size: 9.5pt; color: {t['text']}; margin: 7px 0 1px; }}
  .co-desc {{ font-size: 8.5pt; color: {t['muted']}; margin-bottom: 2px; }}
  ul {{ list-style: none; margin: 1px 0 2px; }}
  li {{ padding-left: 10px; position: relative; }}
  li::before {{ content: "-"; position: absolute; left: 0; color: {t['muted']}; }}
"""


def _detail_css(t: dict) -> str:
    return f"""
  @page {{ size: A4; margin: 14mm 16mm; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: {t['font']}; color: {t['text']}; font-size: 9.5pt; line-height: 1.5; }}
  h1 {{ color: {t['primary']}; font-size: 16pt; margin-bottom: 10px; text-transform: {t['heading_transform']}; letter-spacing: {t['heading_spacing']}; }}
  .card {{ border: 1px solid {t['border']}; border-radius: 6px; padding: 10px 14px; margin-bottom: 10px; page-break-inside: avoid; }}
  .card-head {{ display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid {t['border']}; padding-bottom: 4px; margin-bottom: 6px; }}
  .card-head span:first-child {{ font-weight: bold; font-size: 11pt; color: {t['primary']}; }}
  .card-head .meta {{ font-size: 8.5pt; color: {t['muted']}; }}
  .stack {{ font-size: 8.5pt; color: {t['muted']}; margin-bottom: 3px; }}
  .achv {{ font-size: 8.5pt; color: {t['text']}; margin-bottom: 4px; }}
  .achv b {{ color: {t['accent']}; }}
  h3 {{ font-size: 9.5pt; color: {t['text']}; margin: 6px 0 2px; }}
  h4 {{ font-size: 9pt; color: {t['accent']}; margin: 5px 0 1px; }}
  .body {{ font-size: 8.7pt; color: {t['muted']}; margin-bottom: 3px; }}
  ul {{ list-style: none; margin: 1px 0 2px; }}
  li {{ padding-left: 10px; position: relative; font-size: 8.7pt; color: {t['muted']}; }}
  li::before {{ content: "-"; position: absolute; left: 0; color: {t['muted']}; }}
"""


def render_resume_html(data: dict, template: str = DEFAULT_TEMPLATE) -> str:
    t = _template(template)
    companies = sorted(data["companies"], key=_current_first_sort_key)
    body = []
    for c in companies:
        body.append(f"<h2>{_esc(c['title'])}({_esc(c.get('period', ''))})</h2>")
        if c.get("description"):
            body.append(f'<p class="co-desc">{_esc(c["description"])}</p>')
        for r in c.get("roles", []):
            title = r.get("title") or r.get("id")
            period = r.get("period") or ""
            body.append(f"<h4>{_esc(title)}({_esc(period)})</h4>")
            one_liner = r.get("one_liner") or r.get("summary") or ""
            if one_liner:
                body.append(f"<ul><li>{_esc(one_liner)}</li></ul>")
    return (
        '<!doctype html><html lang="ko"><head><meta charset="UTF-8">'
        "<title>이력서</title>"
        f"<style>{_resume_css(t)}</style></head><body>"
        "<h1>이력서</h1>"
        + "".join(body)
        + "</body></html>"
    )


def render_detail_html(data: dict, template: str = DEFAULT_TEMPLATE) -> str:
    t = _template(template)
    companies = sorted(data["companies"], key=_current_first_sort_key)
    body = []
    for c in companies:
        body.append(f"<h1>{_esc(c['title'])} — {_esc(c.get('period', ''))}</h1>")
        if c.get("description"):
            body.append(f'<p class="co-desc">{_esc(c["description"])}</p>')
        for r in c.get("roles", []):
            title = r.get("title") or r.get("id")
            period = r.get("period") or ""
            headcount = r.get("headcount")
            body.append('<div class="card">')
            body.append(
                f'<div class="card-head"><span>{_esc(title)}</span>'
                f'<span class="meta">{_esc(period)} · 투입인원 {headcount if headcount is not None else "-"}</span></div>'
            )
            if r.get("stack"):
                body.append(f'<div class="stack"><b>기술스택</b> {_esc(", ".join(r["stack"]))}</div>')
            if r.get("key_results"):
                body.append(f'<div class="achv"><b>주요 성과</b> {_esc(", ".join(r["key_results"]))}</div>')
            if r.get("summary"):
                body.append("<h3>서비스 소개</h3>")
                body.append(f'<p class="body">{_esc(r["summary"])}</p>')
            if r.get("responsibilities"):
                body.append("<h3>주요 업무</h3><ul>")
                for item in r["responsibilities"]:
                    body.append(f"<li>{_esc(item)}</li>")
                body.append("</ul>")
            problems = r.get("problems") or []
            if problems:
                body.append("<h3>문제 해결</h3>")
                for p in problems:
                    body.append(f"<h4>{_esc(p.get('title', ''))}</h4><ul>")
                    if p.get("issue"):
                        body.append(f"<li>{_esc(p['issue'])}</li>")
                    if p.get("resolution"):
                        body.append(f"<li>{_esc(p['resolution'])}</li>")
                    if p.get("result"):
                        body.append(f"<li>{_esc(p['result'])}</li>")
                    body.append("</ul>")
            body.append("</div>")
    return (
        '<!doctype html><html lang="ko"><head><meta charset="UTF-8">'
        "<title>경력기술서</title>"
        f"<style>{_detail_css(t)}</style></head><body>"
        + "".join(body)
        + "</body></html>"
    )


def load_profile(path: str) -> dict:
    sys.path.insert(0, os.path.dirname(__file__))
    import minimal_yaml as yml
    return yml.load_file(path)


def _cover_letter_css(t: dict) -> str:
    return f"""
  @page {{ size: A4; margin: 20mm 22mm; }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: {t['font']}; color: {t['text']}; font-size: 10.5pt; line-height: 1.8; }}
  h1 {{ color: {t['primary']}; font-size: 15pt; margin-bottom: 4px; text-transform: {t['heading_transform']}; letter-spacing: {t['heading_spacing']}; }}
  h2 {{ color: {t['accent']}; font-size: 11pt; margin: 16px 0 4px; }}
  .meta {{ font-size: 9pt; color: {t['muted']}; margin-bottom: 18px; }}
  p {{ margin-bottom: 12px; text-align: justify; }}
  .fact {{ border-left: 2px solid {t['border']}; padding: 4px 10px; margin-bottom: 8px; font-size: 9.5pt; color: {t['muted']}; }}
  .fact b {{ color: {t['text']}; }}
  .todo {{ background: #FFF3CD; color: #B45309; padding: 6px 10px; border-radius: 3px; font-size: 9.5pt; margin-bottom: 10px; }}
"""


def render_cover_letter_html(
    resume_data: dict, profile: dict, company: str, role_name: str | None = None,
    template: str = DEFAULT_TEMPLATE, max_roles: int = 3, max_problems_per_role: int = 2,
) -> str:
    """커버레터 초안을 만든다. **자연스러운 문장을 흉내 내지 않는다** — 그걸
    Python f-string 템플릿으로 하려다가 "대표적으로 {title} 과정에서, {issue}
    {resolution}"처럼 문장부호도 없이 사실만 이어붙인 비문이 나온 적이 있다
    (실제 지원서에서 발견). 그 대신 이 함수는:
    - 이력서와 **똑같은 role 선택**(`resume_data`를 그대로 받는다 — 내부에서
      다시 JD 매칭을 돌리지 않는다. 예전엔 따로 돌려서 이력서랑 커버레터가
      서로 다른 프로젝트를 강조하는 모순이 있었다)
    - 각 role의 사실(제목/one_liner/problem의 issue·resolution·result)을
      **글머리 기호로만** 나열한다. 이걸 실제 문장으로 엮는 건 사람이나
      에이전트(대화 중인 Claude)가 이 사실들을 보고 직접 쓴다.
    - 오프닝/동기/클로징 문단은 전부 TODO로 비워둔다.
    """
    t = _template(template)
    # 이력서용으로 고른 role 전부(예: 8개)를 커버레터에도 그대로 쓰면 하이라이트가
    # 아니라 이력서 재탕이 된다 — 커버레터는 상위 max_roles개, role당
    # max_problems_per_role개 problem만 뽑는다(실제로 8 role × 문제 전부를
    # 덤프했다가 발견한 문제).
    # render_resume_html()과 똑같이 최근 회사 먼저 정렬한다 — 안 그러면
    # filter_roles_by_id()가 보존하는 원본 트리 순서(회사 알파벳/디렉터리
    # 순)를 따라가서, 정작 현재 회사의 role이 뒤로 밀려 하이라이트에서
    # 잘려나갈 수 있다(실제 지원서에서 최근 회사 Example Company가 아니라
    # 이전 회사 항목이 먼저 뽑혔던 버그).
    sorted_companies = sorted(resume_data["companies"], key=_current_first_sort_key)
    highlight_roles = [r for c in sorted_companies for r in c.get("roles", [])][:max_roles]

    role_line = f" {role_name} 직무" if role_name else ""
    body = [
        f'<p class="todo">TODO(오프닝): "안녕하십니까, {_esc(company)}{role_line}에 지원하는 '
        f'{_esc(profile.get("name", ""))}입니다" 같은 정형 문구로 시작해도 되고, 공고 내용과 연결되는 '
        f"한두 문장으로 시작해도 된다 — 아래 사실을 바탕으로 사람/에이전트가 직접 쓴다.</p>",
        f'<p class="todo">TODO(지원 동기): "{_esc(company)}에 지원하는 이유"는 회사·공고를 실제로 보고 '
        f"직접 채운다 — 이 생성기는 지어내지 않는다.</p>",
        "<h2>강조할 만한 사실 (문장으로 엮는 건 직접)</h2>",
    ]

    for r in highlight_roles:
        title = r.get("title") or r.get("id")
        one_liner = r.get("one_liner") or r.get("summary") or ""
        body.append(f'<div class="fact"><b>{_esc(title)}</b> — {_esc(one_liner)}')
        for p in (r.get("problems") or [])[:max_problems_per_role]:
            body.append(f'<div class="fact" style="margin-left:14px">{_esc(p.get("title",""))}: '
                        f'{_esc(p.get("issue",""))} → {_esc(p.get("resolution",""))} → {_esc(p.get("result",""))}</div>')
        body.append("</div>")

    body.append(
        f'<p class="todo">TODO(클로징): 정해진 문구를 쓰지 말고, 이 role들과 {_esc(company)}가 실제로 '
        f"어떻게 연결되는지 한두 문장으로 직접 마무리한다.</p>"
    )

    return (
        '<!doctype html><html lang="ko"><head><meta charset="UTF-8">'
        "<title>커버레터</title>"
        f"<style>{_cover_letter_css(t)}</style></head><body>"
        f"<h1>{_esc(profile.get('name',''))} — {_esc(company)} 지원서</h1>"
        f'<div class="meta">{_esc(profile.get("email",""))} · {_esc(profile.get("phone",""))}</div>'
        + "".join(body)
        + "</body></html>"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--resume-out", required=True, help=".md 경로 — 같은 이름으로 .html도 만든다")
    ap.add_argument("--detail-out", required=True, help=".md 경로 — 같은 이름으로 .html도 만든다")
    ap.add_argument("--jd-file", default=None, help="채용공고(JD) 텍스트 파일 — 있으면 관련도 기준으로 이력서 role을 고른다")
    ap.add_argument("--resume-role-budget", type=int, default=12, help="이력서에 넣을 최대 role 개수(1페이지 기준 경험치)")
    ap.add_argument(
        "--design-template", default=DEFAULT_TEMPLATE, choices=sorted(DESIGN_TEMPLATES),
        help=f"디자인 템플릿(design/templates.md 참고). 기본값 {DEFAULT_TEMPLATE!r} — 명시적으로 안 바꾸면 안 바뀐다",
    )
    args = ap.parse_args()

    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)

    jd_text = None
    if args.jd_file:
        with open(args.jd_file, encoding="utf-8") as f:
            jd_text = f.read()

    resume_data = select_roles_for_resume(data, jd_text, args.resume_role_budget)

    resume_html_out = re.sub(r"\.md$", ".html", args.resume_out)
    detail_html_out = re.sub(r"\.md$", ".html", args.detail_out)

    with open(args.resume_out, "w", encoding="utf-8") as f:
        f.write(render_resume(resume_data))
    with open(args.detail_out, "w", encoding="utf-8") as f:
        f.write(render_detail(data))
    with open(resume_html_out, "w", encoding="utf-8") as f:
        f.write(render_resume_html(resume_data, args.design_template))
    with open(detail_html_out, "w", encoding="utf-8") as f:
        f.write(render_detail_html(data, args.design_template))

    print(f"생성: {args.resume_out}, {args.detail_out}, {resume_html_out}, {detail_html_out}")
    n_roles = sum(len(c["roles"]) for c in resume_data["companies"])
    print(f"이력서에 포함된 role: {n_roles}개 (budget={args.resume_role_budget}, jd={'있음' if jd_text else '없음'})")


if __name__ == "__main__":
    main()
