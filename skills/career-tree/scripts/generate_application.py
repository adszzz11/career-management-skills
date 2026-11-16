#!/usr/bin/env python3
"""
지원 회사 하나에 대해 이력서·경력기술서·커버레터 3종을 만든다.

**2단계 흐름**: 먼저 HTML 3개만 만들어서 사람이 확인하게 하고, 사람이 "됐다"고
하면(`--confirm-pdf`) 그제서야 같은 파일들을 PDF로도 내보낸다. HTML을 안
보여주고 바로 PDF부터 만들지 않는다 — 커버레터는 특히 TODO(지원 동기)가
비어있는 채로 나가기 쉬워서, PDF로 굳히기 전에 사람이 먼저 봐야 한다.

사용법:
  # 1단계 — HTML만
  python3 generate_application.py --data career-data.json --company "회사명" \
    [--role "직무명"] [--jd-file jd.txt] --out-dir applications/회사명

  # 2단계 — 확인 후 PDF까지
  python3 generate_application.py --data career-data.json --company "회사명" \
    --out-dir applications/회사명 --confirm-pdf
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import render_docs as rd

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_chrome() -> str | None:
    for path in CHROME_CANDIDATES:
        if os.path.isfile(path):
            return path
    return shutil.which("chromium") or shutil.which("google-chrome")


def html_to_pdf(chrome: str, html_path: str, pdf_path: str):
    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--print-to-pdf-no-header",
         f"--print-to-pdf={pdf_path}", f"file://{os.path.abspath(html_path)}"],
        check=True, capture_output=True,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--profile", default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "design", "profile.yaml"))
    ap.add_argument("--company", required=True)
    ap.add_argument("--role", default=None)
    ap.add_argument("--jd-file", default=None, help="JD 원문이 담긴 텍스트 파일")
    ap.add_argument("--jd-url", default=None, help="JD 공고 링크 — JD.md에 같이 기록만 한다(내용을 대신 가져오지 않음)")
    ap.add_argument("--resume-role-budget", type=int, default=12)
    ap.add_argument(
        "--roles", default=None,
        help="쉼표로 구분한 role id 목록 — 주면 자동 JD 매칭을 건너뛰고 이 role들만 이력서에 쓴다. "
             "매칭-근거.md를 먼저 사람이 읽고 이상할 때 쓰는 수동 오버라이드",
    )
    ap.add_argument(
        "--design-template", default=rd.DEFAULT_TEMPLATE, choices=sorted(rd.DESIGN_TEMPLATES),
        help="design/templates.md 참고. 기본값은 확정된 디자인시스템(변경 없이 유지)",
    )
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--confirm-pdf", action="store_true", help="이미 만든 HTML을 사람이 확인했다는 뜻 — PDF까지 만든다")
    args = ap.parse_args()

    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)
    profile = rd.load_profile(args.profile)

    jd_text = None
    if args.jd_file:
        with open(args.jd_file, encoding="utf-8") as f:
            jd_text = f.read()

    os.makedirs(args.out_dir, exist_ok=True)
    resume_html = os.path.join(args.out_dir, "이력서.html")
    detail_html = os.path.join(args.out_dir, "경력기술서.html")
    cover_html = os.path.join(args.out_dir, "커버레터.html")
    jd_md = os.path.join(args.out_dir, "JD.md")
    rationale_md = os.path.join(args.out_dir, "매칭-근거.md")

    if args.roles:
        resume_data = rd.filter_roles_by_id(data, [r.strip() for r in args.roles.split(",") if r.strip()])
    else:
        resume_data = rd.select_roles_for_resume(data, jd_text, args.resume_role_budget)

    with open(resume_html, "w", encoding="utf-8") as f:
        f.write(rd.render_resume_html(resume_data, args.design_template))
    with open(detail_html, "w", encoding="utf-8") as f:
        f.write(rd.render_detail_html(data, args.design_template))
    with open(cover_html, "w", encoding="utf-8") as f:
        f.write(rd.render_cover_letter_html(resume_data, profile, args.company, args.role, args.design_template))

    # JD.md — 링크 + 원문을 그대로 남긴다(요약하거나 고쳐 쓰지 않음, 나중에
    # "왜 이렇게 매칭했는지" 다시 볼 때 원본이 있어야 검증 가능하다)
    jd_lines = [f"# {args.company} — JD\n"]
    if args.jd_url:
        jd_lines.append(f"링크: {args.jd_url}\n")
    if args.role:
        jd_lines.append(f"직무: {args.role}\n")
    jd_lines.append("## 원문\n")
    jd_lines.append(jd_text if jd_text else "(JD 원문 없이 진행 — 최근 회사/최신 role 우선 기본값 적용됨)")
    with open(jd_md, "w", encoding="utf-8") as f:
        f.write("\n".join(jd_lines) + "\n")

    with open(rationale_md, "w", encoding="utf-8") as f:
        if args.roles:
            chosen = [r.get("title") or r.get("id") for c in resume_data["companies"] for r in c["roles"]]
            f.write(
                f"# {args.company} 지원 — 이력서 role 매칭 근거\n\n"
                f"**수동 오버라이드** — 자동 JD 매칭 결과가 부적절해서(키워드 겹침만 보는 얕은 "
                f"매칭이 개념적으로 관련된 role을 놓침) 사람이 직접 골랐다.\n\n"
                f"## 채택된 role(수동 선택)\n\n" + "\n".join(f"- {t}" for t in chosen) + "\n"
            )
        else:
            f.write(rd.render_match_rationale_md(data, jd_text, args.resume_role_budget, args.company))

    print(f"생성 완료: {args.out_dir}/")
    print("  - JD.md              (링크 + 원문)")
    print("  - 매칭-근거.md         (왜 이 role들을 골랐는지)")
    print("  - 이력서.html")
    print("  - 경력기술서.html")
    print("  - 커버레터.html        (지원 동기 TODO는 사람이 채워야 함)")

    if not args.confirm_pdf:
        print("\n확인 후 --confirm-pdf 로 같은 명령을 다시 실행하면 PDF도 만듭니다.")
        return

    chrome = find_chrome()
    if not chrome:
        print("Chrome을 못 찾아서 PDF는 못 만들었습니다. Chrome 경로를 확인해주세요.", file=sys.stderr)
        sys.exit(1)

    for html_path in (resume_html, detail_html, cover_html):
        pdf_path = html_path[:-len(".html")] + ".pdf"
        html_to_pdf(chrome, html_path, pdf_path)
        print(f"  PDF: {pdf_path}")


if __name__ == "__main__":
    main()
