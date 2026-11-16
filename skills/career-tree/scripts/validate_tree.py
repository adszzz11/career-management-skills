#!/usr/bin/env python3
"""
career-tree 구조 검증기. schema.md의 필수 필드를 실제로 지키는지 확인한다.
문제를 발견해도 고치지 않는다 — 에러 목록만 출력하고 마지막에 exit code로
성공/실패를 알린다 (있음직한 자동수정 대신, 사람이 보고 고치게 함).
"""
from __future__ import annotations
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import minimal_yaml as yml

REQUIRED = {
    "company": ["type", "title"],
    "group": ["type", "title"],
    "role": ["type", "title", "period"],
    "problem": ["type", "title", "issue", "resolution", "result"],
}


def check_node(root_yaml_path: str, errors: list[str]):
    try:
        data = yml.load_file(root_yaml_path)
    except Exception as e:
        errors.append(f"{root_yaml_path}: YAML 파싱 실패 — {e}")
        return None
    node_type = data.get("type")
    if node_type not in REQUIRED:
        errors.append(f"{root_yaml_path}: type이 company/group/role/problem 중 하나가 아님 ({node_type!r})")
        return data
    for field in REQUIRED[node_type]:
        if not data.get(field):
            errors.append(f"{root_yaml_path}: 필수 필드 '{field}' 누락 (type={node_type})")
    return data


def walk(dir_path: str, errors: list[str], depth: str = "company"):
    root_yaml = os.path.join(dir_path, "root.yaml")
    if not os.path.isfile(root_yaml):
        errors.append(f"{dir_path}: root.yaml 없음")
        return
    data = check_node(root_yaml, errors)
    if data is None:
        return
    node_type = data.get("type")

    if node_type == "role":
        problem_files = [f for f in os.listdir(dir_path) if f.endswith(".yaml") and f != "root.yaml"]
        if not problem_files:
            errors.append(f"{dir_path}: role인데 problem yaml이 하나도 없음")
        for fname in problem_files:
            check_node(os.path.join(dir_path, fname), errors)
        return  # role 밑으로는 더 들어가지 않음

    for name in sorted(os.listdir(dir_path)):
        sub = os.path.join(dir_path, name)
        if os.path.isdir(sub) and os.path.isfile(os.path.join(sub, "root.yaml")):
            walk(sub, errors)


def collect_errors(tree_dir: str) -> list[str]:
    """tree_dir 아래 트리 전체를 검증해 에러 문자열 리스트를 돌려준다.
    (테스트에서 sys.exit 없이 직접 호출할 수 있도록 main()에서 분리)"""
    errors: list[str] = []
    if not os.path.isdir(tree_dir):
        return [f"디렉터리 없음: {tree_dir}"]
    for company_name in sorted(os.listdir(tree_dir)):
        company_path = os.path.join(tree_dir, company_name)
        if os.path.isdir(company_path) and os.path.isfile(os.path.join(company_path, "root.yaml")):
            walk(company_path, errors)
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tree_dir")
    args = ap.parse_args()

    errors = collect_errors(args.tree_dir)

    if errors:
        print(f"검증 실패: {len(errors)}건")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("검증 통과: 모든 노드가 스키마를 만족함")


if __name__ == "__main__":
    main()
