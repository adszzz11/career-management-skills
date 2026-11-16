import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import extract

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestExtractBullets(unittest.TestCase):
    def test_nested_bullet_dash_is_stripped(self):
        """회귀 테스트: 2단 중첩 불릿("  - Core 로직 개발...")에서 앞의 '- '가
        안 지워지고 텍스트에 남던 버그. 실제 example-payment-service에서
        발견됨."""
        text = "- 샘플 재고 관리 서비스 개발\n  - Core 로직 개발: 검색, 정렬\n  - 목록 집계 Batch 개발\n"
        self.assertEqual(
            extract._extract_bullets(text),
            ["샘플 재고 관리 서비스 개발", "Core 로직 개발: 검색, 정렬", "목록 집계 Batch 개발"],
        )

    def test_flat_bullets_unaffected(self):
        text = "- one\n- two\n"
        self.assertEqual(extract._extract_bullets(text), ["one", "two"])


class TestLoadTree(unittest.TestCase):
    def test_loads_company_role_problem(self):
        companies = extract.load_tree(os.path.join(FIXTURES, "tree"))
        by_id = {c["id"]: c for c in companies}
        self.assertIn("companyA", by_id)
        self.assertIn("companyA_broken", by_id)  # 검증은 validate_tree의 몫, extract는 있는 그대로 읽는다

        a = by_id["companyA"]
        self.assertEqual(a["title"], "Company A")
        self.assertEqual(len(a["roles"]), 1)
        role = a["roles"][0]
        self.assertEqual(role["id"], "roleX")
        self.assertEqual(role["source"], "tree")
        self.assertEqual(len(role["problems"]), 1)
        self.assertEqual(role["problems"][0]["title"], "Problem One")


class TestLoadLegacyWithAliases(unittest.TestCase):
    def setUp(self):
        self.aliases = extract.load_company_aliases(os.path.join(FIXTURES, "company-aliases.yaml"))
        self.known_ids = {"companyA"}

    def test_alias_resolves_company_id_and_no_warning(self):
        warnings: list[str] = []
        companies = extract.load_legacy(
            os.path.join(FIXTURES, "legacy"), self.aliases, self.known_ids, warnings
        )
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["id"], "companyA")  # org='회사A' -> alias -> companyA
        self.assertEqual(companies[0]["title"], "회사A")  # 표시 이름은 원문 org 그대로

        mapping_warnings = [w for w in warnings if "미해결 회사 매핑" in w]
        self.assertEqual(mapping_warnings, [], "alias가 있으면 회사 매핑 경고가 없어야 한다")

    def test_broken_wikilink_is_warned(self):
        warnings: list[str] = []
        extract.load_legacy(os.path.join(FIXTURES, "legacy"), self.aliases, self.known_ids, warnings)
        broken = [w for w in warnings if "끊어진 링크" in w]
        self.assertEqual(len(broken), 1)
        self.assertIn("roley-problem-missing", broken[0])

    def test_orphan_achievement_is_warned(self):
        warnings: list[str] = []
        extract.load_legacy(os.path.join(FIXTURES, "legacy"), self.aliases, self.known_ids, warnings)
        orphans = [w for w in warnings if "고아 achievement" in w]
        self.assertEqual(len(orphans), 1)
        self.assertIn("orphan-problem", orphans[0])

    def test_referenced_problem_is_included(self):
        warnings: list[str] = []
        companies = extract.load_legacy(
            os.path.join(FIXTURES, "legacy"), self.aliases, self.known_ids, warnings
        )
        problems = companies[0]["roles"][0]["problems"]
        self.assertEqual([p["title"] for p in problems], ["Problem Two"])


class TestLoadLegacyWithoutAliases(unittest.TestCase):
    def test_unmapped_org_is_warned_and_deduped(self):
        """alias가 없을 때: 회사 매핑 경고가 뜨고(조용히 새 회사를 만들지 않고),
        같은 org를 쓰는 파일이 여러 개여도 경고는 한 번만 나와야 한다."""
        warnings: list[str] = []
        companies = extract.load_legacy(
            os.path.join(FIXTURES, "legacy"),
            aliases={},
            known_company_ids={"companyA"},
            warnings=warnings,
        )
        mapping_warnings = [w for w in warnings if "미해결 회사 매핑" in w]
        self.assertEqual(len(mapping_warnings), 1)
        self.assertIn("회사A", mapping_warnings[0])
        # alias 없이도 데이터 자체는 잃지 않는다 — 그냥 별도 회사로 잡힐 뿐
        self.assertEqual(len(companies), 1)


class TestDetectDuplicateRoles(unittest.TestCase):
    def test_same_title_in_tree_and_legacy_is_flagged(self):
        companies = [{
            "id": "companyA",
            "roles": [
                {"id": "roleX", "title": "Role X", "source": "tree"},
                {"id": "companya-rolex", "title": "Role X", "source": "legacy"},
            ],
        }]
        warnings = extract.detect_duplicate_roles(companies)
        self.assertEqual(len(warnings), 1)
        self.assertIn("roleX", warnings[0])
        self.assertIn("companya-rolex", warnings[0])

    def test_different_titles_not_flagged(self):
        companies = [{
            "id": "companyA",
            "roles": [
                {"id": "roleX", "title": "Role X", "source": "tree"},
                {"id": "roleY", "title": "Role Y (완전히 다른 일)", "source": "legacy"},
            ],
        }]
        self.assertEqual(extract.detect_duplicate_roles(companies), [])

    def test_migration_fixture_end_to_end_has_no_leftover_duplicate(self):
        """실제 워크플로 재현: tree 픽스처와 legacy 픽스처는 서로 다른 회사/역할이므로
        중복 경고가 없어야 한다 (참고: 실제 migration 중엔 tree/legacy에 같은 역할이
        남아있는 동안만 이 경고가 뜨고, legacy 원본을 지우면 사라진다)."""
        tree = extract.load_tree(os.path.join(FIXTURES, "tree"))
        aliases = extract.load_company_aliases(os.path.join(FIXTURES, "company-aliases.yaml"))
        known_ids = {c["id"] for c in tree}
        legacy = extract.load_legacy(os.path.join(FIXTURES, "legacy"), aliases, known_ids, [])
        merged = extract.merge(tree, legacy)
        self.assertEqual(extract.detect_duplicate_roles(merged), [])


class TestMerge(unittest.TestCase):
    def test_merge_combines_roles_under_same_id(self):
        tree = [{"id": "companyA", "title": "Company A", "roles": [{"id": "roleX"}]}]
        legacy = [{"id": "companyA", "title": "회사A", "roles": [{"id": "roleY"}]}]
        merged = extract.merge(tree, legacy)
        self.assertEqual(len(merged), 1)
        role_ids = {r["id"] for r in merged[0]["roles"]}
        self.assertEqual(role_ids, {"roleX", "roleY"})
        self.assertEqual(merged[0]["title"], "Company A", "트리 쪽 title이 우선되어야 한다")

    def test_merge_keeps_unmatched_legacy_company_separate(self):
        tree = [{"id": "companyA", "title": "Company A", "roles": []}]
        legacy = [{"id": "회사A", "title": "회사A", "roles": [{"id": "roleY"}]}]
        merged = extract.merge(tree, legacy)
        self.assertEqual({c["id"] for c in merged}, {"companyA", "회사A"})


if __name__ == "__main__":
    unittest.main()
