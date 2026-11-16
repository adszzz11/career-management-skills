import importlib.util
import os
import sys
import unittest

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "dashboard")
FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

spec = importlib.util.spec_from_file_location("dashboard_build", os.path.join(DASHBOARD_DIR, "build.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class TestDashboardBuildIsUserAgnostic(unittest.TestCase):
    """회귀 테스트: template.html에 특정 사용자 이름("홍길동")이 하드코딩돼
    있던 버그 — 다른 사람이 이 스킬을 그대로 가져오면 대시보드에 이전
    사용자 이름이 그대로 남았다. build.py가 design/profile.yaml에서 이름을
    읽어와 채우고, profile.yaml이 아예 없어도(새 사용자) 안 죽어야 한다."""

    def test_template_has_no_hardcoded_name_placeholder(self):
        with open(os.path.join(DASHBOARD_DIR, "template.html"), encoding="utf-8") as f:
            template = f.read()
        self.assertIn("__USER_NAME__", template)
        self.assertNotIn("홍길동", template, "template.html에 특정 사용자 이름이 하드코딩되면 안 된다")

    def test_missing_profile_does_not_crash_and_uses_placeholder(self):
        name = build._load_user_name("/no/such/profile.yaml")
        self.assertIn("없음", name)

    def test_real_profile_yaml_name_is_used(self):
        real_profile = os.path.join(DASHBOARD_DIR, "..", "design", "profile.yaml")
        if os.path.isfile(real_profile):
            name = build._load_user_name(real_profile)
            self.assertTrue(name and "없음" not in name)


if __name__ == "__main__":
    unittest.main()
