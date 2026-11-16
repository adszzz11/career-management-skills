import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import minimal_yaml as yml


class TestMinimalYaml(unittest.TestCase):
    def test_flat_mapping(self):
        d = yml.parse('type: role\ntitle: "Hello World"\nheadcount: 3\n')
        self.assertEqual(d, {"type": "role", "title": "Hello World", "headcount": 3})

    def test_inline_list(self):
        d = yml.parse("tags: [a, b, c]\nempty: []\n")
        self.assertEqual(d["tags"], ["a", "b", "c"])
        self.assertEqual(d["empty"], [])

    def test_folded_scalar_joins_with_space(self):
        text = 'summary: >-\n  line one\n  line two\n  line three\n'
        d = yml.parse(text)
        self.assertEqual(d["summary"], "line one line two line three")

    def test_block_list_of_strings(self):
        text = "stack:\n  - \"Python\"\n  - Bash\n"
        d = yml.parse(text)
        self.assertEqual(d["stack"], ["Python", "Bash"])

    def test_plain_string_with_colon_stays_a_string_not_a_mapping(self):
        """회귀 테스트: "JavaScript(Node.js, type:module)"처럼 평범한 문자열
        안에 콜론이 있을 뿐인 리스트 항목이 nested mapping으로 잘못 쪼개지면
        안 된다. 실제 sample-workflow stack 필드에서 발생한 버그 —
        {'JavaScript(Node.js, type': 'module)'}가 되어버렸었다."""
        text = "stack:\n  - JavaScript(Node.js, type:module)\n  - Python\n"
        d = yml.parse(text)
        self.assertEqual(d["stack"], ["JavaScript(Node.js, type:module)", "Python"])
        self.assertIsInstance(d["stack"][0], str)

    def test_block_list_of_mappings(self):
        text = (
            "attachments:\n"
            "  - label: \"link one\"\n"
            "    type: link\n"
            "    url: \"https://example.com\"\n"
            "  - label: \"link two\"\n"
            "    type: image\n"
            "    path: \"../assets/x.png\"\n"
        )
        d = yml.parse(text)
        self.assertEqual(len(d["attachments"]), 2)
        self.assertEqual(d["attachments"][0]["label"], "link one")
        self.assertEqual(d["attachments"][0]["url"], "https://example.com")
        self.assertEqual(d["attachments"][1]["type"], "image")

    def test_hash_inside_backticks_is_not_a_comment(self):
        """회귀 테스트: `#{value}`처럼 백틱으로 감싼 인라인 코드 안의 #이
        주석으로 잘려서 뒤 텍스트가 통째로 사라지면 안 된다. 실제
        알리미/html-template.yaml에서 "HTML Template 기반 전송을 설계하고,
        `#{value}` 형식의 치환 파싱 처리를 구현했다."의 뒷부분이 통째로
        잘려나갔던 버그."""
        text = 'resolution: >-\n  전송을 설계하고, `#{value}` 형식의 치환 파싱 처리를 구현했다.\n'
        d = yml.parse(text)
        self.assertIn("치환 파싱 처리를 구현했다", d["resolution"])
        self.assertIn("#{value}", d["resolution"])

    def test_hash_after_whitespace_outside_quotes_is_a_comment(self):
        d = yml.parse("title: hello # this is a real comment\n")
        self.assertEqual(d["title"], "hello")

    def test_comment_and_blank_lines_ignored(self):
        text = "# a comment\ntype: role\n\n# another\ntitle: \"X\"\n"
        d = yml.parse(text)
        self.assertEqual(d, {"type": "role", "title": "X"})

    def test_dotted_number_like_period_stays_a_string(self):
        """회귀 테스트: period: 2031.10 처럼 마침표로 구분된 날짜값이 float로
        캐스팅되면 안 된다 — float(2031.10)은 2031.1이 되어 10월이 1월로
        둔갑한다(trailing zero 소실). 실제 마이그레이션 중 이 버그로 스크립트가
        죽었다."""
        d = yml.parse("period: 2031.10\n")
        self.assertEqual(d["period"], "2031.10")
        self.assertIsInstance(d["period"], str)

    def test_plain_integer_still_parses_as_int(self):
        d = yml.parse("headcount: 3\n")
        self.assertEqual(d["headcount"], 3)
        self.assertIsInstance(d["headcount"], int)

    def test_bad_indentation_raises(self):
        text = "type: role\n   title: \"X\"\n"  # 3칸 들여쓰기는 어느 규칙에도 안 맞음
        with self.assertRaises(ValueError):
            yml.parse(text)

    def test_load_real_fixture_file(self):
        fixture = os.path.join(os.path.dirname(__file__), "fixtures", "tree", "companyA", "roleX", "root.yaml")
        d = yml.load_file(fixture)
        self.assertEqual(d["type"], "role")
        self.assertEqual(d["title"], "Role X")
        self.assertEqual(d["stack"], ["Python", "Bash"])
        self.assertEqual(d["attachments"][0]["url"], "https://example.com/roleX")


if __name__ == "__main__":
    unittest.main()
