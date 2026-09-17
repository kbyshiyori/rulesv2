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
                "绕过,com.google.android.youtube,YouTube again\n"
                "绕过,com.Slack,Slack\n",
                encoding="utf-8",
            )
            self.assertEqual(
                build.load_android_apps(str(path)),
                {
                    "北美": ["com.google.android.youtube"],
                    "游戏": [],
                    "绕过": ["com.Slack"],
                },
            )

    def test_flclash_writes_nekobox_groups_and_acl4ssr_instead_of_geolocation_not_cn(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        apps = build.load_android_apps(str(root / "rules" / "android-apps.list"))
        policy_domains = build.load_policy_domains(
            str(root / "rules" / "policy-domains.list")
        )
        backcn = build.render(
            "backcn", ["xiaohongshu.com"], [], "", "flclash", apps, policy_domains,
        )
        cnip = build.render(
            "cnip", ["xiaohongshu.com"], [], "", "flclash", apps, policy_domains,
        )

        self.assertIn("find-process-mode: always", backcn)
        self.assertIn("PROCESS-NAME,com.chase.sig.android,北美", backcn)
        self.assertIn("PROCESS-NAME,com.miHoYo.Yuanshen,游戏", backcn)
        self.assertIn("PROCESS-NAME,com.google.android.youtube,北美", backcn)
        self.assertNotIn("PROCESS-NAME,com.google.android.youtube,DIRECT", backcn)
        self.assertIn("PROCESS-NAME,com.tmobile.tuesdays,北美", backcn)
        self.assertNotIn("PROCESS-NAME,com.tmobile.tuesdays,DIRECT", backcn)
        self.assertIn("PROCESS-NAME,com.reddit.frontpage,DIRECT", backcn)
        self.assertNotIn("PROCESS-NAME,com.reddit.frontpage,DIRECT", cnip)
        self.assertIn("PROCESS-NAME,com.follow.clash,DIRECT", cnip)
        self.assertIn("DOMAIN-SUFFIX,18comic.vip,北美", backcn)
        self.assertIn("DOMAIN-SUFFIX,missav.ai,游戏", backcn)
        self.assertIn("DOMAIN-SUFFIX,browsercrp.vivo.com.cn,DIRECT", backcn)
        self.assertIn("  - name: \"北美\"\n    type: select", backcn)
        self.assertIn("  - name: \"游戏\"\n    type: select", backcn)
        self.assertIn("RULE-SET,acl-gfw,DIRECT", backcn)
        self.assertIn("RULE-SET,acl-proxy-media,DIRECT", backcn)
        self.assertIn("RULE-SET,acl-telegram,DIRECT", backcn)
        self.assertIn("RULE-SET,acl-cn-domain,PROXY", backcn)
        self.assertIn("GEOIP,CN,PROXY,no-resolve", backcn)
        self.assertIn("MATCH,DIRECT", backcn)
        self.assertIn("RULE-SET,acl-gfw,PROXY", cnip)
        self.assertIn("RULE-SET,acl-cn-domain,DIRECT", cnip)
        self.assertIn("GEOIP,CN,DIRECT,no-resolve", cnip)
        self.assertIn("MATCH,PROXY", cnip)
        self.assertNotIn("geolocation-!cn", backcn)
        self.assertNotIn("GEOIP,!CN", backcn)
        self.assertNotIn("ACL4SSR", build.render("backcn", [], [], ""))
        self.assertNotIn("PROCESS-NAME,com.chase.sig.android", build.render("backcn", [], [], ""))
        self.assertIn(
            f"{build.ACL4SSR_BASE}/Providers/ProxyGFWlist.yaml",
            backcn,
        )


if __name__ == "__main__":
    unittest.main()
