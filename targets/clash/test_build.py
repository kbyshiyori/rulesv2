from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import build


class BuildTests(unittest.TestCase):
    def test_profiles_reverse_cn_and_fallback_policies(self) -> None:
        backcn = build.render("backcn", ["xiaohongshu.com"], [], "https://dns.example/dns-query")
        cnip = build.render("cnip", ["xiaohongshu.com"], [], "https://dns.example/dns-query")

        self.assertIn("DOMAIN-SUFFIX,xiaohongshu.com,PROXY", backcn)
        self.assertIn("RULE-SET,cn-domain,PROXY", backcn)
        self.assertIn("MATCH,DIRECT", backcn)
        self.assertIn('"https://dns.example/dns-query#DIRECT"', backcn)
        self.assertIn('"https://223.5.5.5/dns-query#PROXY"', backcn)
        self.assertIn("DOMAIN-SUFFIX,xiaohongshu.com,DIRECT", cnip)
        self.assertIn("RULE-SET,cn-domain,DIRECT", cnip)
        self.assertIn("MATCH,PROXY", cnip)
        self.assertIn('"https://dns.example/dns-query#PROXY"', cnip)
        self.assertIn('"https://223.5.5.5/dns-query#DIRECT"', cnip)

    def test_direct_intents_are_translated(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "direct.list"
            path.write_text(
                "ip-cidr,192.0.2.1/32\n"
                "domain-suffix,example.com\n"
                "protocol-port,udp,443\n",
                encoding="utf-8",
            )
            self.assertEqual(
                build.load_direct_rules(str(path)),
                [
                    "IP-CIDR,192.0.2.1/32,DIRECT,no-resolve",
                    "DOMAIN-SUFFIX,example.com,DIRECT",
                    "AND,((NETWORK,udp),(DST-PORT,443)),DIRECT",
                ],
            )

    def test_secret_placeholder_is_the_only_provider_url(self) -> None:
        text = build.render("cnip", [], [], "")
        self.assertIn(build.PROVIDER_PLACEHOLDER, text)
        self.assertIn("      - REJECT", text)
        self.assertNotIn("password:", text)


if __name__ == "__main__":
    unittest.main()
