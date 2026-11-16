import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import render_docs as rd


def _role(id_, title, period, tags=None, one_liner="", stack=None):
    return {
        "id": id_, "title": title, "period": period, "one_liner": one_liner,
        "summary": "", "tags": tags or [], "stack": stack or [], "key_results": [],
        "responsibilities": [], "problems": [], "attachments": [],
    }


def _sample_data():
    return {
        "companies": [
            {
                "id": "acme", "title": "Acme Inc.", "period": "2036.02 ~ 현재",
                "description": "", "roles": [
                    _role("payment-gw", "Payment Gateway", "2036.02 ~ 현재", tags=["control-plane"], one_liner="Sample monitoring service"),
                    _role("sample-workflow", "Sample Workflow", "2036.07 ~ 현재", tags=["self-healing"], one_liner="샘플 복원 기능"),
                    _role("sample-research", "Sample Research", "2036.09", tags=["r&d", "compression"], one_liner="압축 알고리즘 연구"),
                ],
            },
            {
                "id": "globex", "title": "Globex Corp", "period": "2031.10 ~ 2036.01",
                "description": "", "roles": [
                    _role("search-index", "검색 인덱스", "2035.04 ~ 2036.01", tags=["검색", "lucene"], one_liner="검색 인덱스 개발"),
                    _role("문서 검색", "문서 검색 운영", "2031.10 ~ 2033.12", tags=["검색"], one_liner="문서 검색 운영 관리"),
                ],
            },
        ]
    }


class TestSelectRolesForResume(unittest.TestCase):
    def test_rnd_tag_excluded_without_jd(self):
        data = _sample_data()
        out = rd.select_roles_for_resume(data, jd_text=None, budget=12)
        ids = [r["id"] for c in out["companies"] for r in c["roles"]]
        self.assertNotIn("sample-research", ids, "JD 없이는 r&d 태그 role을 이력서에서 빼야 한다")
        self.assertIn("payment-gw", ids)

    def test_rnd_tag_included_when_jd_matches(self):
        data = _sample_data()
        out = rd.select_roles_for_resume(data, jd_text="압축 알고리즘 연구 경험 우대", budget=12)
        ids = [r["id"] for c in out["companies"] for r in c["roles"]]
        self.assertIn("sample-research", ids, "JD가 뚜렷하게 관련되면 r&d role도 포함해야 한다")

    def test_budget_limits_role_count(self):
        data = _sample_data()
        out = rd.select_roles_for_resume(data, jd_text=None, budget=1)
        n = sum(len(c["roles"]) for c in out["companies"])
        self.assertEqual(n, 1)

    def test_recency_prefers_current_company_when_no_jd_signal(self):
        """JD가 없거나 관련도 차이가 없을 때는 최근 회사(acme) role을
        먼저 채택해야 한다 — 사용자가 명시한 기본 방침."""
        data = _sample_data()
        out = rd.select_roles_for_resume(data, jd_text=None, budget=2)
        ids = [r["id"] for c in out["companies"] for r in c["roles"]]
        self.assertIn("payment-gw", ids)
        self.assertNotIn("search-index", ids)
        self.assertNotIn("문서 검색", ids)

    def test_company_structure_preserved_for_kept_roles_only(self):
        data = _sample_data()
        out = rd.select_roles_for_resume(data, jd_text=None, budget=1)
        self.assertEqual(len(out["companies"]), 1, "role이 하나도 안 남은 회사는 출력에서 빠져야 한다")

    def test_jd_relevant_older_role_can_outrank_irrelevant_recent_role(self):
        data = _sample_data()
        out = rd.select_roles_for_resume(data, jd_text="검색 인덱스 검색 Lucene 엔진 경험", budget=1)
        ids = [r["id"] for c in out["companies"] for r in c["roles"]]
        self.assertEqual(ids, ["search-index"], "JD 관련도가 최근순보다 우선해야 한다")


class TestFilterRolesById(unittest.TestCase):
    def test_keeps_only_specified_roles_in_original_order(self):
        data = _sample_data()
        out = rd.filter_roles_by_id(data, ["문서 검색", "sample-workflow"])
        ids = [r["id"] for c in out["companies"] for r in c["roles"]]
        self.assertEqual(set(ids), {"문서 검색", "sample-workflow"})

    def test_company_with_no_kept_roles_is_dropped(self):
        data = _sample_data()
        out = rd.filter_roles_by_id(data, ["sample-workflow"])
        self.assertEqual([c["id"] for c in out["companies"]], ["acme"])

    def test_unknown_id_is_silently_ignored_not_an_error(self):
        data = _sample_data()
        out = rd.filter_roles_by_id(data, ["존재하지않는id", "sample-workflow"])
        ids = [r["id"] for c in out["companies"] for r in c["roles"]]
        self.assertEqual(ids, ["sample-workflow"])


class TestMatchRationale(unittest.TestCase):
    def test_rationale_lists_included_and_excluded(self):
        data = _sample_data()
        md = rd.render_match_rationale_md(data, jd_text="Lucene 검색 엔진", budget=1, company_name="테스트회사")
        self.assertIn("채택된 role", md)
        self.assertIn("검색 인덱스", md)  # 점수가 제일 높은 role이 채택 섹션에 나와야 함
        self.assertIn("규칙으로 제외된 role", md)
        self.assertIn("r&d", md.lower())  # sample-research가 규칙 제외 사유에 나와야 함

    def test_rationale_without_jd_explains_recency_default(self):
        data = _sample_data()
        md = rd.render_match_rationale_md(data, jd_text=None, budget=5, company_name="테스트회사")
        self.assertIn("최근 회사", md)


class TestDesignTemplates(unittest.TestCase):
    def test_default_template_unchanged_when_not_specified(self):
        data = _sample_data()
        default_html = rd.render_resume_html(data)
        explicit_html = rd.render_resume_html(data, rd.DEFAULT_TEMPLATE)
        self.assertEqual(default_html, explicit_html)
        self.assertIn(rd.DESIGN_TEMPLATES["blue"]["primary"], default_html)

    def test_each_template_produces_distinct_valid_html(self):
        data = _sample_data()
        outputs = {name: rd.render_resume_html(data, name) for name in rd.DESIGN_TEMPLATES}
        # 서로 다른 팔레트를 쓰면 결과 HTML도 달라야 한다(그냥 이름만 바뀌고
        # 스타일은 그대로인 버그를 잡기 위한 회귀 테스트)
        self.assertEqual(len(set(outputs.values())), len(outputs))
        for name, html in outputs.items():
            self.assertIn(rd.DESIGN_TEMPLATES[name]["primary"], html)
            self.assertIn("<!doctype html>", html)

    def test_unknown_template_falls_back_to_default_not_crash(self):
        data = _sample_data()
        html = rd.render_resume_html(data, "존재하지-않는-템플릿")
        self.assertIn(rd.DESIGN_TEMPLATES[rd.DEFAULT_TEMPLATE]["primary"], html)

    def test_detail_and_cover_letter_also_respect_template(self):
        data = _sample_data()
        detail_html = rd.render_detail_html(data, "mono")
        self.assertIn(rd.DESIGN_TEMPLATES["mono"]["primary"], detail_html)

        profile = {"name": "테스트", "email": "", "phone": "", "links": []}
        cover_html = rd.render_cover_letter_html(data, profile, "테스트회사", template="modern")
        self.assertIn(rd.DESIGN_TEMPLATES["modern"]["primary"], cover_html)


class TestTokenize(unittest.TestCase):
    def test_stopwords_removed(self):
        toks = rd._tokenize("경력 우대 관련 업무 Python Kotlin")
        self.assertIn("python", toks)
        self.assertIn("kotlin", toks)
        self.assertNotIn("경력", toks)


if __name__ == "__main__":
    unittest.main()
