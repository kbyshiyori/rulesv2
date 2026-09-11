import unittest

import build


class BuildTests(unittest.TestCase):
    def test_redirect_policy_supports_both_directions(self) -> None:
        source = "[General]\ndns-server = system\n[Rule]\nFINAL,DIRECT\n"

        backcn = build.inject_redirect(source, ["xiaohongshu.com"], "PROXY")
        cnip = build.inject_redirect(source, ["xiaohongshu.com"], "DIRECT")

        self.assertIn("DOMAIN-SUFFIX,xiaohongshu.com,PROXY", backcn)
        self.assertIn("DOMAIN-SUFFIX,xiaohongshu.com,DIRECT", cnip)

    def test_redirect_injection_is_idempotent(self) -> None:
        source = "[General]\ndns-server = system\n[Rule]\nFINAL,DIRECT\n"
        once = build.inject_redirect(source, ["example.com"])
        twice = build.inject_redirect(once, ["example.com"])

        self.assertEqual(once, twice)
        self.assertEqual(twice.count(build.RC_BEGIN), 1)


if __name__ == "__main__":
    unittest.main()
