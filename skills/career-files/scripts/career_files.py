#!/usr/bin/env python3
"""취업 서류 디렉터리(as-candidate/) 관리 도구. 구조는 as-candidate/README.md 참고.

  career_files.py promote [--subdir 강사이력서] <새 파일…>
      새 버전을 current/(하위 폴더)로 옮긴다. 같은 종류의 이전 날짜 버전은 archive/<그 날짜>/로 보낸다.
  career_files.py submit <회사 폴더명> [--date YYYY-MM-DD] [--position 직무] [--note 메모] <파일…>
      applications/<회사>/제출_YYYYMMDD/로 복사하고 applications/지원기록.md에 한 줄 추가한다.
  career_files.py status      최신본, 회사별 마지막 제출, 플랫폼별 마지막 작업일
  career_files.py check       구조 위반 점검 (위반 있으면 종료 코드 1)

파일 이름 규칙: <종류>_YYYYMMDD.<확장자>  (예: 홍길동_이력서_20361030.pdf). 종류 = 날짜 앞부분.
"""
import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import sys

DEFAULT_ROOT = pathlib.Path.cwd() / "career-data"
DATED = re.compile(r"^(?P<kind>.+?)_(?P<date>\d{8})$")
LOG_HEADER = "# 지원 기록\n\n어디에 무엇을 언제 냈는지 한 곳에 남긴다. `career_files.py submit`이 줄을 추가한다.\n\n| 날짜 | 회사 | 포지션 | 낸 파일 | 메모 |\n|---|---|---|---|---|\n"
SKIP = {".DS_Store"}


def parse(name):
    """'홍길동_이력서_20361030.pdf' -> ('홍길동_이력서', '20361030'); 규칙에 안 맞으면 None."""
    m = DATED.match(pathlib.Path(name).stem)
    return (m.group("kind"), m.group("date")) if m else None


def move(src, dst):
    """git이 추적하는 파일이면 git mv, 아니면 일반 이동."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(src)], cwd=src.parent,
                             capture_output=True).returncode == 0
    if tracked and subprocess.run(["git", "mv", str(src), str(dst)], cwd=src.parent,
                                  capture_output=True).returncode == 0:
        return
    shutil.move(str(src), str(dst))


def cmd_promote(root, a):
    target = root / "current" / (a.subdir or "")
    for f in map(pathlib.Path, a.files):
        info = parse(f.name)
        if not info:
            sys.exit(f"날짜가 없는 파일 이름: {f.name} (<종류>_YYYYMMDD.<확장자>)")
        kind, date = info
        if target.exists():
            for old in sorted(target.iterdir()):
                oi = parse(old.name) if old.is_file() else None
                if oi and oi[0] == kind and oi[1] != date:
                    dst = root / "archive" / oi[1] / (a.subdir or "") / old.name
                    move(old, dst)
                    print(f"archive  {old.relative_to(root)} -> {dst.relative_to(root)}")
        dst = target / f.name
        if f.resolve() != dst.resolve():
            move(f.resolve(), dst)
        print(f"current  {dst.relative_to(root)}")


def cmd_submit(root, a):
    date = a.date or datetime.date.today().isoformat()
    dest = root / "applications" / a.company / f"제출_{date.replace('-', '')}"
    dest.mkdir(parents=True, exist_ok=True)
    names = []
    for f in map(pathlib.Path, a.files):
        shutil.copy2(f, dest / f.name)
        names.append(f.name)
        print(f"copy     {f.name} -> {(dest / f.name).relative_to(root)}")
    log = root / "applications" / "지원기록.md"
    if not log.exists():
        log.write_text(LOG_HEADER)
    row = f"| {date} | {a.company} | {a.position or ''} | {', '.join(names)} | {a.note or ''} |\n"
    lines = log.read_text().splitlines(keepends=True)
    # 첫 번째 표(회사 지원)의 마지막 행 뒤에 넣는다. 아래의 "플랫폼 동기화" 표와 섞이지 않게.
    start = next(i for i, l in enumerate(lines) if l.startswith("| 날짜 |"))
    end = start
    while end + 1 < len(lines) and lines[end + 1].startswith("|"):
        end += 1
    lines.insert(end + 1, row)
    log.write_text("".join(lines))
    print(f"log      {log.relative_to(root)}")


def current_files(root):
    cur = root / "current"
    return sorted(p for p in cur.rglob("*") if p.is_file() and p.name not in SKIP) if cur.exists() else []


def platform_dates(root):
    out = {}
    base = root / "applications" / "platforms"
    if not base.exists():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        dates = [parse(f.name)[1] for f in d.rglob("*") if f.is_file() and parse(f.name)]
        out[d.name] = max(dates) if dates else None
    return out


def fmt(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if d else "-"


def cmd_status(root, a):
    print("[최신본 current/]")
    for f in current_files(root):
        print(f"  {f.relative_to(root / 'current')}")
    print("\n[회사별 마지막 제출 applications/<회사>/제출_*]")
    apps = root / "applications"
    for d in sorted(p for p in apps.iterdir() if p.is_dir() and p.name != "platforms") if apps.exists() else []:
        subs = sorted(s.name for s in d.iterdir() if s.is_dir() and s.name.startswith("제출_"))
        print(f"  {d.name:35} {fmt(subs[-1][3:]) if subs else '(제출 폴더 없음)'}")
    print("\n[플랫폼별 마지막 작업 applications/platforms/]")
    for name, d in platform_dates(root).items():
        print(f"  {name:12} {fmt(d)}")


def cmd_check(root, a):
    problems = []
    kinds = {}
    for f in current_files(root):
        info = parse(f.name)
        if not info:
            continue
        key = (f.parent, info[0])
        kinds.setdefault(key, set()).add(info[1])
    for (folder, kind), dates in kinds.items():
        if len(dates) > 1:
            problems.append(f"current/에 같은 종류 여러 날짜: {kind} {sorted(dates)} ({folder.relative_to(root)})")
    for f in root.iterdir():
        if f.is_file() and parse(f.name):
            problems.append(f"구역 밖 날짜 파일: {f.name} -> current/ 또는 archive/로")
    latest = max((parse(f.name)[1] for f in current_files(root) if parse(f.name) and
                  any(k in f.name for k in ("이력서", "경력기술서"))), default=None)
    for name, d in platform_dates(root).items():
        if latest and d and d < latest:
            problems.append(f"플랫폼 {name}: 마지막 작업 {fmt(d)} < 최신 서류 {fmt(latest)} (다시 동기화 필요)")
    for p in problems:
        print("WARN", p)
    print(f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("promote")
    p.add_argument("--subdir")
    p.add_argument("files", nargs="+")
    s = sub.add_parser("submit")
    s.add_argument("company")
    s.add_argument("--date")
    s.add_argument("--position")
    s.add_argument("--note")
    s.add_argument("files", nargs="+")
    sub.add_parser("status")
    sub.add_parser("check")
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    {"promote": cmd_promote, "submit": cmd_submit, "status": cmd_status, "check": cmd_check}[a.cmd](root, a)


if __name__ == "__main__":
    main()
