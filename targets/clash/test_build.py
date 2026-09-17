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

    def test_android_apps_keep_first_group_and_exact_package_case(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "apps.list"
            path.write_text(
                "北美,com.google.android.youtube,YouTube\n"
                "国外,com.google.android.youtube,YouTube again\n"
                "国外,com.Slack,Slack\n"
                "国外,com.follow.clash,FIClash\n",
                encoding="utf-8",
            )
            self.assertEqual(
                build.load_android_apps(str(path)),
                {
                    "北美": ["com.google.android.youtube"],
                    "游戏": [],
                    "国外": ["com.Slack"],
                },
            )

    def test_flclash_is_a_single_profile_with_location_switch_groups(self) -> None:
        root = Path(__file__).resolve().parents[2]
        apps = build.load_android_apps(str(root / "rules" / "android-apps.list"))
        policy_domains = build.load_policy_domains(
            str(root / "rules" / "policy-domains.list")
        )
        text = build.render(
            "backcn", ["xiaohongshu.com"], [],
            "https://dns.example/dns-query", "flclash", apps, policy_domains,
        )
        same_if_cnip = build.render(
            "cnip", ["xiaohongshu.com"], [],
            "https://dns.example/dns-query", "flclash", apps, policy_domains,
        )
        self.assertEqual(text, same_if_cnip)
        self.assertIn("find-process-mode: always", text)
        self.assertIn("enhanced-mode: redir-host", text)
        self.assertIn("respect-rules: true", text)
        self.assertNotIn("nameserver-policy:", text)
        self.assertNotIn("223.5.5.5", text)
        self.assertNotIn("dns.example", text)
        self.assertNotIn("enhanced-mode: fake-ip", text)
        self.assertIn("PROCESS-NAME,com.chase.sig.android,北美", text)
        self.assertIn("PROCESS-NAME,com.miHoYo.Yuanshen,游戏", text)
        self.assertIn("PROCESS-NAME,com.google.android.youtube,北美", text)
        self.assertNotIn("PROCESS-NAME,com.google.android.youtube,国外", text)
        self.assertIn("PROCESS-NAME,com.reddit.frontpage,国外", text)
        self.assertIn("PROCESS-NAME,com.follow.clash,DIRECT", text)
        self.assertNotIn("PROCESS-NAME,com.follow.clash,国外", text)
        self.assertIn("DOMAIN-SUFFIX,18comic.vip,18", text)
        self.assertIn("DOMAIN-SUFFIX,missav.ai,missav", text)
        self.assertIn("DOMAIN-SUFFIX,browsercrp.vivo.com.cn,安全浏览", text)
        self.assertNotIn("DOMAIN-SUFFIX,18comic.vip,北美", text)
        self.assertNotIn("DOMAIN-SUFFIX,missav.ai,游戏", text)
        self.assertIn("  - name: \"兜底\"\n    type: select", text)
        self.assertIn("  - name: \"国外\"\n    type: select", text)
        self.assertIn("  - name: \"18\"\n    type: select", text)
        self.assertIn("  - name: missav\n    type: select", text)
        self.assertIn("  - name: \"安全浏览\"\n    type: select", text)
        self.assertNotIn("  - name: YouTube\n", text)
        self.assertIn("RULE-SET,youtube,国外", text)
        self.assertIn("RULE-SET,acl-gfw,国外", text)
        self.assertIn("RULE-SET,acl-proxy-media,国外", text)
        self.assertIn("RULE-SET,acl-telegram,国外", text)
        self.assertIn("RULE-SET,acl-cn-domain,兜底", text)
        self.assertIn("DOMAIN-SUFFIX,xiaohongshu.com,兜底", text)
        self.assertIn("GEOIP,CN,兜底,no-resolve", text)
        self.assertIn("MATCH,兜底", text)
        self.assertNotIn("geolocation-!cn", text)
        self.assertNotIn("GEOIP,!CN", text)
        self.assertNotIn("ACL4SSR", build.render("backcn", [], [], ""))
        self.assertIn(
            f"{build.ACL4SSR_BASE}/Providers/ProxyGFWlist.yaml",
            text,
        )


if __name__ == "__main__":
    unittest.main()
