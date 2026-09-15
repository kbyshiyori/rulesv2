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

    def test_private_provider_is_a_local_file_without_embedded_nodes(self) -> None:
        text = build.render("cnip", [], [], "")
        self.assertIn("  private-provider:\n    type: file", text)
        self.assertIn(f'    path: "{build.PRIVATE_PROVIDER_PATH}"', text)
        self.assertNotIn("    url: \"https://example.invalid/", text)
        self.assertIn("      - REJECT", text)
        self.assertNotIn("proxies:\n  - name:", text)
        self.assertNotIn("password:", text)

    def test_youtube_has_an_independent_select_group_in_both_profiles(self) -> None:
        for profile in ("backcn", "cnip"):
            text = build.render(profile, [], [], "https://dns.example/dns-query")
            self.assertIn("  - name: YouTube\n    type: select", text)
            self.assertIn("  - RULE-SET,youtube,YouTube", text)
            self.assertIn(
                '    "rule-set:youtube": "https://dns.example/dns-query#YouTube"',
                text,
            )
            youtube_group = text.split("  - name: YouTube\n", 1)[1].split(
                "rule-providers:", 1
            )[0]
            self.assertIn("    use:\n      - private-provider", youtube_group)
            self.assertNotIn("default-selected:", youtube_group)

    def test_verge_adds_yuanshen_process_group_before_direct_exceptions(self) -> None:
        for profile in ("backcn", "cnip"):
            text = build.render(
                profile, ["yuanshen.com"], ["IP-CIDR,192.0.2.1/32,DIRECT,no-resolve"],
                "", "verge",
            )
            group = text.split('  - name: "原神"\n', 1)[1].split(
                "rule-providers:", 1
            )[0]
            self.assertIn("    type: select", group)
            self.assertIn("    use:\n      - private-provider", group)
            self.assertIn("      - DIRECT", group)
            self.assertIn("find-process-mode: always", text)
            self.assertLess(
                text.index("PROCESS-NAME,YuanShen.exe,原神"),
                text.index("IP-CIDR,192.0.2.1/32,DIRECT,no-resolve"),
            )
            self.assertNotIn("PROCESS-NAME,YuanShen.exe", build.render(profile, [], [], ""))


if __name__ == "__main__":
    unittest.main()
