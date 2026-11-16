#!/usr/bin/env bash
# career-tree 스킬 하네스. 외부 의존성 없이 python3 stdlib(unittest)만 쓴다.
# 이 스킬의 스크립트를 고칠 때마다 돌려서, 조용히 깨진 걸 못 보고 넘어가지 않게 한다.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m unittest discover -s . -p "test_*.py" -v
