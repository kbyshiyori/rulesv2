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

    def test_direct_dns_reverses_with_profile_direction(self) -> None:
        nextdns = "https://dns.nextdns.io/PLACEHOLDER"
        alidns = "https://223.5.5.5/dns-query"

        self.assertEqual(build.direct_dns_for_profile("backcn", nextdns, alidns), nextdns)
        self.assertEqual(build.direct_dns_for_profile("cnip", nextdns, alidns), alidns)

    def test_youtube_rule_is_idempotent_and_does_not_emit_a_group(self) -> None:
        source = "[General]\ndns-server = system\n[Rule]\nFINAL,DIRECT\n"

        once = build.inject_youtube_rule(source)
        twice = build.inject_youtube_rule(once)

        self.assertEqual(once, twice)
        self.assertEqual(twice.count(build.YOUTUBE_RULE_BEGIN), 1)
        self.assertIn(f"RULE-SET,{build.YOUTUBE_RULESET},YouTube", twice)
        self.assertNotIn("[Proxy Group]", twice)


if __name__ == "__main__":
    unittest.main()
