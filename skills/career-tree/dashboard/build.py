#!/usr/bin/env python3
"""template.html의 __CAREER_DATA_JSON__ 자리에 career-data.json을 그대로 박아
넣어 최종 대시보드 HTML을 만든다. Artifact로 publish하는 건 별도(이 스크립트는
파일만 만든다)."""
import argparse
import html
import os
import sys

HERE = os.path.dirname(__file__)
SKILL_DIR = os.path.dirname(HERE)
DEFAULT_PROFILE = os.path.join(SKILL_DIR, "design", "profile.yaml")

sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))


def _load_user_name(profile_path: str) -> str:
    """design/profile.yaml은 인스턴스 데이터(사람마다 다름) — 대시보드
    타이틀에 하드코딩하면 다른 사람이 이 스킬을 그대로 가져왔을 때도
    이전 사용자 이름이 남는다(실제로 특정 사용자 이름이 template.html에
    박혀있던 버그가 있었다). profile.yaml이 없으면(스킬을 처음 쓰는 사람)
    플레이스홀더로 대체한다."""
    if not os.path.isfile(profile_path):
        return "(design/profile.yaml 없음)"
    import minimal_yaml as yml
    profile = yml.load_file(profile_path)
    return profile.get("name") or "(이름 미설정)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="career-data.json 경로")
    ap.add_argument("--out", required=True, help="생성할 dashboard html 경로")
    ap.add_argument("--profile", default=DEFAULT_PROFILE, help="design/profile.yaml 경로")
    args = ap.parse_args()

    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
        template = f.read()
    with open(args.data, encoding="utf-8") as f:
        data_json = f.read()

    user_name = html.escape(_load_user_name(args.profile))
    fragment = template.replace("__CAREER_DATA_JSON__", data_json).replace("__USER_NAME__", user_name)

    # template.html은 Artifact 배포용 조각(HTML fragment) 형태로 되어 있다
    # (<!doctype>/<html>/<head>/<body> 없음). 로컬 file://로 그냥 열면 브라우저가
    # 인코딩을 못 알아채 한글이 깨지므로(실제로 겪은 문제), 여기서 제대로 된
    # 문서로 감싼다. Artifact로 배포할 땐 이 wrapper 없이 fragment를 그대로 쓴다.
    marker = '<div class="wrap">'
    head_part, body_part = fragment.split(marker, 1)
    full_html = (
        "<!doctype html>\n"
        '<html lang="ko">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        f"{head_part}"
        "</head>\n"
        "<body>\n"
        f"{marker}{body_part}"
        "</body>\n"
        "</html>\n"
    )
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"built {args.out} ({len(full_html)} bytes)")


if __name__ == "__main__":
    main()
