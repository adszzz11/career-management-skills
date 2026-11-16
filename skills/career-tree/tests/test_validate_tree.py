import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate_tree as vt

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "tree")


class TestValidateTree(unittest.TestCase):
    def test_valid_company_passes(self):
        errors = vt.collect_errors(os.path.join(FIXTURES, "companyA"))
        self.assertEqual(errors, [])

    def test_broken_company_reports_missing_period_and_empty_role(self):
        errors = vt.collect_errors(os.path.join(FIXTURES, "companyA_broken"))
        joined = "\n".join(errors)
        self.assertIn("period", joined, "role에 period 필수 필드가 없다고 잡아야 한다")
        self.assertIn("problem yaml이 하나도 없음", joined, "problem이 없는 role을 잡아야 한다")

    def test_missing_dir_reports_error_not_crash(self):
        errors = vt.collect_errors(os.path.join(FIXTURES, "does-not-exist"))
        self.assertEqual(len(errors), 1)
        self.assertIn("디렉터리 없음", errors[0])


if __name__ == "__main__":
    unittest.main()
