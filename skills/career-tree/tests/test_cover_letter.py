import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import render_docs as rd

SKILL_DIR = os.path.join(os.path.dirname(__file__), "..")


def _sample_data():
    return {
        "companies": [
            {
                "id": "acme", "title": "Acme Inc.", "period": "2036.02 ~ 현재",
                "description": "", "roles": [
                    {
                        "id": "sample-project", "title": "Payment Gateway", "period": "2036.02 ~ 현재",
                        "one_liner": "Sample monitoring service", "summary": "", "tags": [],
                        "stack": [], "key_results": [], "responsibilities": [], "attachments": [],
                        "problems": [
                            {"id": "p1", "title": "검색 결과 정렬 개선", "issue": "결과 순서가 일정하지 않았다.",
                             "resolution": "정렬 기준을 추가했다.", "result": "결과가 일관되게 표시됐다."}
                        ],
                    }
                ],
            }
        ]
    }


def _many_roles_data(n_roles=8, n_problems=6):
    roles = []
    for i in range(n_roles):
        roles.append({
            "id": f"role{i}", "title": f"Role {i}", "period": "2036.01 ~ 현재",
            "one_liner": f"설명 {i}", "summary": "", "tags": [], "stack": [], "key_results": [],
            "responsibilities": [], "attachments": [],
            "problems": [
                {"id": f"p{i}-{j}", "title": f"문제 {i}-{j}", "issue": "이슈", "resolution": "해결", "result": "결과"}
                for j in range(n_problems)
            ],
        })
    return {"companies": [{"id": "acme", "title": "Acme Inc.", "period": "2036.01 ~ 현재", "description": "", "roles": roles}]}


class TestCoverLetterHighlightCap(unittest.TestCase):
    def test_does_not_dump_every_role_and_every_problem(self):
        """회귀 테스트: 이력서용으로 고른 role 8개(role당 problem 여러 개)를
        커버레터에 전부 다 썼더니 실질적으로 이력서 재탕이 된 적이 있다
        (실제 지원서에서 발견). 기본값(max_roles=3,
        max_problems_per_role=2)으로 줄여야 한다."""
        data = _many_roles_data(n_roles=8, n_problems=6)
        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        html = rd.render_cover_letter_html(data, profile, "테스트회사")
        self.assertIn("Role 0", html)
        self.assertIn("Role 2", html)
        self.assertNotIn("Role 3", html, "기본 max_roles=3을 넘는 role은 안 나와야 한다")
        self.assertIn("문제 0-0", html)
        self.assertIn("문제 0-1", html)
        self.assertNotIn("문제 0-2", html, "기본 max_problems_per_role=2를 넘는 problem은 안 나와야 한다")

    def test_limits_are_configurable(self):
        data = _many_roles_data(n_roles=8, n_problems=6)
        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        html = rd.render_cover_letter_html(data, profile, "테스트회사", max_roles=1, max_problems_per_role=1)
        self.assertIn("Role 0", html)
        self.assertNotIn("Role 1", html)
        self.assertIn("문제 0-0", html)
        self.assertNotIn("문제 0-1", html)


class TestCoverLetterCompanyOrder(unittest.TestCase):
    def test_current_company_roles_are_highlighted_first(self):
        """회귀 테스트: filter_roles_by_id()가 원본 트리 순서(회사 알파벳/
        디렉터리 순)를 보존하다 보니, 이전 회사가 현재 회사보다 먼저 나와서
        max_roles 컷오프에서 현재 회사 role이 전부 잘려나간 적이 있다
        (실제 지원서에서 발견). 커버레터도 이력서와 똑같이 최근 회사
        먼저 정렬해야 한다."""
        data = {
            "companies": [
                {"id": "old", "title": "Old Co", "period": "2030.01 ~ 2033.12", "description": "", "roles": [
                    {"id": "old-role", "title": "Old Role", "period": "2030.01 ~ 2033.12",
                     "one_liner": "옛날 업무", "summary": "", "tags": [], "stack": [], "key_results": [],
                     "responsibilities": [], "attachments": [], "problems": []},
                ]},
                {"id": "current", "title": "Current Co", "period": "2034.01 ~ 현재", "description": "", "roles": [
                    {"id": "current-role", "title": "Current Role", "period": "2034.01 ~ 현재",
                     "one_liner": "지금 업무", "summary": "", "tags": [], "stack": [], "key_results": [],
                     "responsibilities": [], "attachments": [], "problems": []},
                ]},
            ],
        }
        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        html = rd.render_cover_letter_html(data, profile, "테스트회사", max_roles=1)
        self.assertIn("Current Role", html)
        self.assertNotIn("Old Role", html)


class TestLoadProfile(unittest.TestCase):
    def test_example_profile_yaml_loads(self):
        """design/profile.yaml(실제 개인정보)은 .gitignore 대상이라 공개
        레포를 새로 받은 사람에게는 없다 — 항상 존재하는 .example로 테스트한다."""
        profile = rd.load_profile(os.path.join(SKILL_DIR, "design", "profile.yaml.example"))
        self.assertTrue(profile.get("name"))
        self.assertTrue(profile.get("email"))
        self.assertIsInstance(profile.get("links"), list)

    def test_real_profile_yaml_loads_if_present(self):
        """실제 profile.yaml이 있는 환경(본인 vault)에서는 그것도 검증한다 —
        없으면(공개 레포를 막 받은 사람) 조용히 건너뛴다."""
        real_profile = os.path.join(SKILL_DIR, "design", "profile.yaml")
        if not os.path.isfile(real_profile):
            self.skipTest("design/profile.yaml 없음 — 이 레포를 새로 받은 상태로 보고 건너뜀")
        profile = rd.load_profile(real_profile)
        self.assertTrue(profile.get("name"))


class TestCoverLetter(unittest.TestCase):
    def test_mentions_company_name_and_does_not_fabricate_motivation(self):
        data = _sample_data()
        profile = {"name": "테스트", "email": "t@example.com", "phone": "010-0000-0000", "links": []}
        html = rd.render_cover_letter_html(data, profile, "테스트회사", role_name="AI Engineer")
        self.assertIn("테스트회사", html)
        self.assertIn("AI Engineer", html)
        self.assertIn("TODO", html, "지원 동기는 지어내지 않고 TODO로 남겨야 한다")

    def test_includes_role_highlight_from_data(self):
        data = _sample_data()
        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        html = rd.render_cover_letter_html(data, profile, "테스트회사")
        self.assertIn("Payment Gateway", html)
        self.assertIn("검색 결과 정렬 개선", html)

    def test_does_not_glue_issue_and_resolution_into_a_run_on_sentence(self):
        """회귀 테스트: "대표적으로 {title} 과정에서, {issue} {resolution}"처럼
        문장부호 없이 이어붙여 비문이 나오던 버그. 실제 지원서 커버레터에서
        발견됨 — 이제 issue/resolution/result는 화살표로 명확히 구분된 사실
        나열이어야 하고, 문장으로 엮는 척하지 않는다."""
        data = _sample_data()
        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        html = rd.render_cover_letter_html(data, profile, "테스트회사")
        self.assertNotIn("과정에서,", html)
        self.assertIn("결과 순서가 일정하지 않았다. → 정렬 기준을 추가했다. → 결과가 일관되게 표시됐다.", html)

    def test_uses_exactly_the_roles_passed_in_not_its_own_jd_matching(self):
        """회귀 테스트: 예전엔 이 함수가 내부에서 select_roles_for_resume()를
        다시 돌려서, 이력서에 쓴 role 선택과 커버레터가 강조하는 role이 서로
        달랐다(실제 지원서에서 발견 — 이력서는 Sample Project/Sample Workflow를 강조하는데
        커버레터는 전혀 다른 role을 강조). 이제 인자로 받은 resume_data를
        그대로 쓴다."""
        custom_data = {
            "companies": [{
                "id": "acme", "title": "Acme Inc.", "period": "2036.02 ~ 현재",
                "description": "", "roles": [{
                    "id": "only-this-one", "title": "Exactly This Role", "period": "2036.01 ~ 현재",
                    "one_liner": "정확히 이것만 강조되어야 한다", "summary": "", "tags": [],
                    "stack": [], "key_results": [], "responsibilities": [], "attachments": [],
                    "problems": [],
                }],
            }],
        }
        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        html = rd.render_cover_letter_html(custom_data, profile, "테스트회사")
        self.assertIn("Exactly This Role", html)
        self.assertNotIn("Payment Gateway", html)


if __name__ == "__main__":
    unittest.main()
