#!/usr/bin/env python3
"""career_files.py 테스트. 실행: python3 tests/test_career_files.py"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "career_files.py"


def run(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True)


def touch(p, text="x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


class CareerFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        for d in ("current", "archive", "applications/platforms", "components"):
            (self.root / d).mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_promote_moves_previous_version_to_archive(self):
        old_pdf = touch(self.root / "current/홍길동_이력서_20361030.pdf")
        old_md = touch(self.root / "current/홍길동_이력서_20361030.md")
        other = touch(self.root / "current/홍길동_경력기술서_20361030.pdf")
        new = touch(self.root / "draft/홍길동_이력서_20361103.pdf", "new")
        r = run(self.root, "promote", str(new))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "current/홍길동_이력서_20361103.pdf").exists())
        self.assertFalse(old_pdf.exists())
        self.assertFalse(old_md.exists())
        self.assertTrue((self.root / "archive/20361030/홍길동_이력서_20361030.pdf").exists())
        self.assertTrue((self.root / "archive/20361030/홍길동_이력서_20361030.md").exists())
        self.assertTrue(other.exists(), "different kind must stay")
        self.assertFalse(new.exists(), "source is moved, not copied")

    def test_promote_keeps_same_date_siblings(self):
        touch(self.root / "current/홍길동_이력서_20361103.md")
        new = touch(self.root / "draft/홍길동_이력서_20361103.pdf")
        r = run(self.root, "promote", str(new))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "current/홍길동_이력서_20361103.md").exists())
        self.assertTrue((self.root / "current/홍길동_이력서_20361103.pdf").exists())

    def test_promote_subdir(self):
        touch(self.root / "current/강사이력서/홍길동_메인강사이력서_20361014.pdf")
        new = touch(self.root / "draft/홍길동_메인강사이력서_20361120.pdf")
        r = run(self.root, "promote", "--subdir", "강사이력서", str(new))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.root / "current/강사이력서/홍길동_메인강사이력서_20361120.pdf").exists())
        self.assertTrue((self.root / "archive/20361014/강사이력서/홍길동_메인강사이력서_20361014.pdf").exists())

    def test_promote_rejects_undated_name(self):
        new = touch(self.root / "draft/resume.pdf")
        r = run(self.root, "promote", str(new))
        self.assertNotEqual(r.returncode, 0)

    def test_submit_copies_and_logs(self):
        cur = touch(self.root / "current/홍길동_이력서_20361030.pdf")
        r = run(self.root, "submit", "example-company", "--date", "2036-10-30", "--position", "Server Developer",
                "--note", "커버레터 포함", str(cur))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(cur.exists(), "submit copies")
        self.assertTrue((self.root / "applications/example-company/제출_20361030/홍길동_이력서_20361030.pdf").exists())
        log = (self.root / "applications/지원기록.md").read_text()
        self.assertIn("| 2036-10-30 | example-company | Server Developer |", log)
        self.assertIn("홍길동_이력서_20361030.pdf", log)

    def test_submit_inserts_into_first_table(self):
        (self.root / "applications").mkdir(exist_ok=True)
        (self.root / "applications/지원기록.md").write_text(
            "# 지원 기록\n\n| 날짜 | 회사 | 포지션 | 낸 파일 | 메모 |\n|---|---|---|---|---|\n| 2036-10-30 | a | | x | |\n\n"
            "## 플랫폼 동기화\n\n| 날짜 | 플랫폼 | 방식 | 올린 기준 | 메모 |\n|---|---|---|---|---|\n| 2036-11-01 | example-platform | | | |\n")
        cur = touch(self.root / "current/홍길동_이력서_20361030.pdf")
        r = run(self.root, "submit", "b", "--date", "2036-11-03", str(cur))
        self.assertEqual(r.returncode, 0, r.stderr)
        log = (self.root / "applications/지원기록.md").read_text()
        self.assertLess(log.index("| 2036-11-03 | b |"), log.index("## 플랫폼 동기화"))

    def test_check_flags_duplicate_kinds_and_stray_files(self):
        touch(self.root / "current/홍길동_이력서_20361030.pdf")
        touch(self.root / "current/홍길동_이력서_20361103.pdf")
        touch(self.root / "홍길동_경력기술서_20361001.pdf")
        r = run(self.root, "check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("홍길동_이력서", r.stdout)
        self.assertIn("홍길동_경력기술서_20361001.pdf", r.stdout)

    def test_check_flags_stale_platform(self):
        touch(self.root / "current/홍길동_이력서_20361103.pdf")
        touch(self.root / "applications/platforms/example-platform/example-platform_payload_20361101.json")
        r = run(self.root, "check")
        self.assertIn("example-platform", r.stdout)

    def test_check_clean(self):
        touch(self.root / "current/홍길동_이력서_20361030.pdf")
        touch(self.root / "applications/platforms/example-platform/example-platform_payload_20361101.json")
        r = run(self.root, "check")
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_status_lists_current_and_platforms(self):
        touch(self.root / "current/홍길동_이력서_20361030.pdf")
        touch(self.root / "applications/platforms/other-platform/other-platform_payload_20361102.json")
        r = run(self.root, "status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("홍길동_이력서_20361030.pdf", r.stdout)
        self.assertIn("other-platform", r.stdout)
        self.assertIn("2036-11-02", r.stdout)


if __name__ == "__main__":
    unittest.main()
