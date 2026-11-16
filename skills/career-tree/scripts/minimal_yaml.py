"""
아주 작은 YAML 서브셋 파서. 외부 의존성(PyYAML) 없이 이 스킬이 실제로 쓰는
문법만 지원한다. 지원 범위 밖의 문법을 쓰면 parse()가 예외를 던진다 —
"조용히 잘못 파싱"보다 "바로 에러"가 낫다.

지원하는 것:
  - 최상위 flat mapping: `key: value`
  - 인용 문자열 "..." / 그냥 스칼라 (숫자 포함)
  - 인라인 flow list: `key: [a, b, c]` 또는 `key: []`
  - block scalar `>-` (folded, 개행은 공백으로 합쳐짐)
  - block list:
        key:
          - "item"
          - item2
    또는 nested mapping을 담은 block list:
        key:
          - label: "..."
            type: image
            path: "..."
  - 주석(#으로 시작하는 줄)과 빈 줄은 무시

지원하지 않는 것: 앵커/별칭, multi-doc, flow mapping({...}), 깊이 3단 이상
중첩된 list-of-list 등. 이 스킬의 root.yaml/leaf yaml은 이 범위를 넘지 않는다.
"""
from __future__ import annotations
import re


def _strip_comment(line: str) -> str:
    """줄 끝 주석만 자른다. 두 가지를 지킨다:
    1. 큰따옴표나 백틱(`) 안의 #은 보존한다 — `#{value}`처럼 인라인 코드에
       # 이 들어간 실제 문서 텍스트가 있었는데, 이걸 주석으로 오인해서
       뒤를 통째로 잘라먹은 적이 있다(알리미/html-template.yaml에서 발견).
    2. YAML 관례대로, #이 공백 뒤(또는 줄 맨 앞)에 와야만 주석으로 본다 —
       "전송률70%#3위" 같은 식별자 중간의 #까지 주석으로 자르지 않기 위함.
    """
    in_dquote = False
    in_backtick = False
    for i, ch in enumerate(line):
        if ch == '"' and not in_backtick:
            in_dquote = not in_dquote
        elif ch == "`" and not in_dquote:
            in_backtick = not in_backtick
        elif ch == "#" and not in_dquote and not in_backtick:
            if i == 0 or line[i - 1].isspace():
                return line[:i]
    return line


def _parse_scalar(raw: str):
    raw = raw.strip()
    if raw == "" or raw == "~" or raw == "null":
        return None
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return raw[1:-1]
    if raw == "[]":
        return []
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in inner.split(",")]
    if raw in ("true", "false"):
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    # 의도적으로 float 변환은 하지 않는다: 이 스킬의 스키마엔 실수 필드가 하나도
    # 없고, "2031.10"처럼 날짜/기간을 나타내는 마침표 구분 값이 훨씬 많다.
    # float()에 넣으면 trailing zero가 사라져(2031.10 -> 2031.1) 10월이 1월로
    # 둔갑하는 등 조용히 데이터가 깨진다 — 실제로 이 버그로 마이그레이션이 한 번
    # 죽고 나서 고친 것. 숫자처럼 보이는 값도 항상 원본 문자열 그대로 둔다.
    return raw


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parse(text: str) -> dict:
    lines = [_strip_comment(l.rstrip("\n")) for l in text.split("\n")]
    lines = [l for l in lines if l.strip() != ""]
    return _parse_block(lines, 0, 0)[0]


def _parse_block(lines: list[str], start: int, indent: int):
    """indent 레벨의 mapping을 파싱. (dict, 다음_인덱스)를 반환."""
    result: dict = {}
    i = start
    while i < len(lines):
        line = lines[i]
        cur_indent = _indent(line)
        if cur_indent < indent:
            break
        if cur_indent > indent:
            raise ValueError(f"예상치 못한 들여쓰기: {line!r}")
        stripped = line.strip()
        if stripped.startswith("- "):
            break  # 이 레벨은 mapping이 아니라 list의 항목들
        if ":" not in stripped:
            raise ValueError(f"'key: value' 형식이 아님: {line!r}")
        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()

        if rest == ">-" or rest == ">":
            value, i = _parse_folded_scalar(lines, i + 1, indent)
            result[key] = value
            continue

        if rest == "":
            # 다음 줄이 더 깊은 들여쓰기의 list거나 mapping
            if i + 1 < len(lines) and _indent(lines[i + 1]) > indent:
                next_indent = _indent(lines[i + 1])
                if lines[i + 1].strip().startswith("- "):
                    value, i = _parse_list(lines, i + 1, next_indent)
                else:
                    value, i = _parse_block(lines, i + 1, next_indent)
                result[key] = value
                continue
            else:
                result[key] = None
                i += 1
                continue

        result[key] = _parse_scalar(rest)
        i += 1
    return result, i


def _parse_folded_scalar(lines: list[str], start: int, parent_indent: int):
    parts = []
    i = start
    while i < len(lines) and _indent(lines[i]) > parent_indent:
        parts.append(lines[i].strip())
        i += 1
    return " ".join(parts), i


def _parse_list(lines: list[str], start: int, indent: int):
    items = []
    i = start
    while i < len(lines):
        line = lines[i]
        cur_indent = _indent(line)
        if cur_indent != indent or not line.strip().startswith("- "):
            break
        after_dash = line.strip()[2:]
        # nested mapping 판정: 줄이 "key: ..." 형태로 *시작*해야 한다(key는 평범한
        # 식별자). 예전엔 "':' in after_dash"만 봤는데, "JavaScript(Node.js,
        # type:module)"처럼 평범한 문자열 안에 콜론이 있는 값도 걸려서
        # {'JavaScript(Node.js, type': 'module)'}로 잘못 쪼개졌다(실제
        # sample-workflow stack에서 발생). 이제 맨 앞이 "식별자:"로
        # 시작할 때만 mapping으로 본다.
        if re.match(r'^[A-Za-z_][A-Za-z0-9_\-]*:(\s|$)', after_dash) and not after_dash.startswith('"'):
            # nested mapping list item: `- label: "..."` 형태
            # "- " 두 글자만큼, 이어지는 줄들의 들여쓰기와 맞춰준다
            item_indent = indent + 2
            fake_first_line = " " * item_indent + after_dash
            sub_lines = [fake_first_line]
            j = i + 1
            while j < len(lines) and _indent(lines[j]) > indent:
                sub_lines.append(lines[j])
                j += 1
            sub_dict, _ = _parse_block(sub_lines, 0, item_indent)
            items.append(sub_dict)
            i = j
        else:
            items.append(_parse_scalar(after_dash))
            i += 1
    return items, i


def load_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return parse(f.read())
