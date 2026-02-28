import unittest

from compliance_guard import apply_icml_tense_fixes, scan_compliance_violations


class TestComplianceGuard(unittest.TestCase):
    def test_detects_url_email_shortlink(self):
        text = "See https://example.com and contact a@b.com plus bit.ly/abc"
        kinds = {v.kind for v in scan_compliance_violations(text)}
        self.assertIn("url", kinds)
        self.assertIn("email", kinds)
        self.assertIn("shortlink", kinds)

    def test_detects_past_tense_update_claim(self):
        text = "We have updated the paper to address this concern."
        kinds = {v.kind for v in scan_compliance_violations(text)}
        self.assertIn("past_tense_update_claim", kinds)

    def test_applies_tense_fix(self):
        text = "We revised the manuscript and we have updated the paper."
        fixed = apply_icml_tense_fixes(text)
        self.assertNotIn("updated the paper", fixed.lower())
        self.assertNotIn("revised the manuscript", fixed.lower())
        self.assertIn("camera-ready", fixed.lower())


if __name__ == "__main__":
    unittest.main()

