import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import migrate_role as mr
import minimal_yaml as yml

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestSplitByComma(unittest.TestCase):
    def test_comma_inside_parens_is_not_a_split_point(self):
        """회귀 테스트: "JavaScript(Node.js, type:module)"가 콤마 분리 기술스택
        항목 하나로 남아야 한다 — 괄호를 무시하고 그냥 split(',')했더니
        "JavaScript(Node.js" / "type:module)"로 두 동강 났던 실제 버그."""
        result = mr._split_by_comma("JavaScript(Node.js, type:module), Python, Dolt(branch 격리)")
        self.assertEqual(result, ["JavaScript(Node.js, type:module)", "Python", "Dolt(branch 격리)"])

    def test_plain_comma_list_still_works(self):
        self.assertEqual(mr._split_by_comma("a, b, c"), ["a", "b", "c"])

    def test_empty_and_none(self):
        self.assertEqual(mr._split_by_comma(None), [])
        self.assertEqual(mr._split_by_comma(""), [])


class TestMigrateRole(unittest.TestCase):
    def setUp(self):
        self.warnings: list[str] = []
        self.role_yaml, self.problems = mr.migrate(
            os.path.join(FIXTURES, "legacy", "project", "roley.md"),
            os.path.join(FIXTURES, "legacy", "achievement"),
            "/unused",
            self.warnings,
        )

    def test_role_yaml_parses_and_has_expected_fields(self):
        d = yml.parse(self.role_yaml)
        self.assertEqual(d["type"], "role")
        self.assertEqual(d["title"], "Role Y")
        self.assertEqual(d["period"], "2029.01 ~ 2030.12")
        self.assertEqual(d["tags"], ["legacy", "fixture"])
        self.assertEqual(d["stack"], ["Java", "Spring"])
        self.assertEqual(d["key_results"], ["성과1", "성과2"])

    def test_h4_responsibilities_nested_under_h2_full_is_extracted(self):
        """회귀 테스트: '#### 주요 업무'가 '## full' 섹션 안에 중첩돼 있을 때
        (실제 vault의 모든 project 파일이 이 구조) responsibilities가 비어있으면 안 된다."""
        d = yml.parse(self.role_yaml)
        self.assertEqual(d["responsibilities"], ["업무1", "업무2"])

    def test_broken_wikilink_is_skipped_with_warning_not_crash(self):
        # roley.md는 [[roley-problem-missing]]도 참조하는데 그 파일이 없다 —
        # 이건 결측이지 새 problem 필드가 없는 것과는 다른 경고여야 한다.
        joined = "\n".join(self.warnings)
        self.assertIn("roley-problem-missing", joined)
        self.assertIn("없음", joined)

    def test_only_the_resolvable_problem_is_migrated(self):
        self.assertEqual(list(self.problems.keys()), ["roley-problem-two.yaml"])
        parsed = yml.parse(self.problems["roley-problem-two.yaml"])
        self.assertEqual(parsed["type"], "problem")
        self.assertEqual(parsed["title"], "Problem Two")
        self.assertEqual(parsed["issue"], "레거시 문제 상황")
        self.assertEqual(parsed["resolution"], "레거시 해결 방법")
        self.assertEqual(parsed["result"], "레거시 결과")

    def test_old_story_format_uses_one_liner_as_result(self):
        """story 포맷(문제/해결 불릿 2개)만 있는 achievement는 '## one-liner'를
        result로 대신 쓴다 — schema가 요구하는 result 필드를 비워두지 않기 위한
        의도적 선택이다."""
        warnings: list[str] = []
        parsed = mr.parse_achievement(
            os.path.join(FIXTURES, "story_format_achievement.md"), warnings
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["issue"], "문제 상황 불릿")
        self.assertEqual(parsed["resolution"], "해결 방법 불릿")
        self.assertEqual(parsed["result"], "한 줄 요약이 결과로 쓰인다")
        self.assertEqual(warnings, [])

    def test_unresolvable_story_shape_is_warned_not_guessed(self):
        """불릿이 1개거나 3개면(2개가 아니면) 추측하지 않고 경고만 남긴다."""
        warnings: list[str] = []
        parsed = mr.parse_achievement(
            os.path.join(FIXTURES, "ambiguous_story_achievement.md"), warnings
        )
        self.assertIsNone(parsed)
        self.assertEqual(len(warnings), 1)
        self.assertIn("자동 변환 실패", warnings[0])


if __name__ == "__main__":
    unittest.main()
