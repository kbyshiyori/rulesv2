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
        self.assertIn(f'      url: "{build.HEALTH_CHECK_URL}"', text)
        self.assertIn("      expected-status: 200", text)
        self.assertNotIn("gstatic.com", text)
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
                "🇨🇦 北美,com.google.android.youtube,YouTube\n"
                "🎯 全球直连,com.google.android.youtube,YouTube again\n"
                "🎯 全球直连,com.Slack,Slack\n"
                "🎯 全球直连,com.follow.clash,FIClash\n",
                encoding="utf-8",
            )
            self.assertEqual(
                build.load_android_apps(str(path)),
                {
                    "🇨🇦 北美": ["com.google.android.youtube"],
                    "🎮 游戏": [],
                    "🎯 全球直连": ["com.Slack"],
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
        self.assertIn("nameserver-policy:", text)
        self.assertIn('    - "https://223.5.5.5/dns-query"', text)
        self.assertIn('    "+.xiaohongshu.com": "https://223.5.5.5/dns-query"', text)
        self.assertIn('    "+.18comic.vip": "https://dns.example/dns-query"', text)
        self.assertIn('    "+.missav.ai": "https://dns.example/dns-query"', text)
        self.assertIn('    "+.browsercrp.vivo.com.cn": "https://223.5.5.5/dns-query"', text)
        self.assertIn('    "+.chase.com": "https://dns.example/dns-query"', text)
        self.assertIn('    "+.hoyoverse.com": "https://dns.example/dns-query"', text)
        self.assertIn('    "rule-set:youtube": "https://dns.example/dns-query"', text)
        self.assertIn('    "rule-set:acl-gfw": "https://dns.example/dns-query"', text)
        self.assertIn('    "rule-set:acl-cn-domain": "https://223.5.5.5/dns-query"', text)
        self.assertIn("proxy-server-nameserver:\n    - system", text)
        self.assertNotIn("direct-nameserver:", text)
        self.assertNotIn("enhanced-mode: fake-ip", text)
        default_dns = build.render(
            "backcn", ["xiaohongshu.com"], [], "", "flclash", apps, policy_domains,
        )
        self.assertIn('    "rule-set:youtube": "https://1.1.1.1/dns-query"', default_dns)
        self.assertNotIn("dns.example", default_dns)
        self.assertIn(f"PROCESS-NAME,com.chase.sig.android,{build.GROUP_NA}", text)
        self.assertIn(f"PROCESS-NAME,com.miHoYo.Yuanshen,{build.GROUP_GAME}", text)
        self.assertIn(f"PROCESS-NAME,com.google.android.youtube,{build.GROUP_NA}", text)
        self.assertNotIn(f"PROCESS-NAME,com.google.android.youtube,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"PROCESS-NAME,com.facebook.aura,{build.GROUP_NA}", text)
        self.assertNotIn(f"PROCESS-NAME,com.facebook.aura,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"PROCESS-NAME,com.reddit.frontpage,{build.GROUP_GLOBAL}", text)
        self.assertIn("PROCESS-NAME,com.follow.clash,DIRECT", text)
        self.assertNotIn(f"PROCESS-NAME,com.follow.clash,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"DOMAIN-SUFFIX,18comic.vip,{build.GROUP_18}", text)
        self.assertIn(f"DOMAIN-SUFFIX,missav.ai,{build.GROUP_MISSAV}", text)
        self.assertIn(f"DOMAIN-SUFFIX,browsercrp.vivo.com.cn,{build.GROUP_SAFE}", text)
        self.assertIn(f"DOMAIN-SUFFIX,chase.com,{build.GROUP_NA}", text)
        self.assertIn(f"DOMAIN-SUFFIX,hoyoverse.com,{build.GROUP_GAME}", text)
        self.assertNotIn(f"DOMAIN-SUFFIX,18comic.vip,{build.GROUP_NA}", text)
        self.assertNotIn(f"DOMAIN-SUFFIX,missav.ai,{build.GROUP_GAME}", text)
        self.assertIn(f"  - name: \"{build.GROUP_FINAL}\"\n    type: select", text)
        self.assertIn(f"  - name: \"{build.GROUP_GLOBAL}\"\n    type: select", text)
        self.assertIn(f"  - name: \"{build.GROUP_18}\"\n    type: select", text)
        self.assertIn(f"  - name: \"{build.GROUP_MISSAV}\"\n    type: select", text)
        self.assertIn(f"  - name: \"{build.GROUP_SAFE}\"\n    type: select", text)
        self.assertNotIn("  - name: YouTube\n", text)
        self.assertIn(f"RULE-SET,youtube,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"RULE-SET,acl-gfw,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"RULE-SET,acl-proxy-media,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"RULE-SET,acl-telegram,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"RULE-SET,acl-cn-domain,{build.GROUP_FINAL}", text)
        self.assertIn(f"DOMAIN-SUFFIX,xiaohongshu.com,{build.GROUP_FINAL}", text)
        self.assertIn(f"GEOIP,CN,{build.GROUP_FINAL},no-resolve", text)
        self.assertLess(
            text.index(f"DOMAIN-SUFFIX,18comic.vip,{build.GROUP_18}"),
            text.index(f"DOMAIN-SUFFIX,missav.ai,{build.GROUP_MISSAV}"),
        )
        self.assertLess(
            text.index(f"DOMAIN-SUFFIX,missav.ai,{build.GROUP_MISSAV}"),
            text.index(f"DOMAIN-SUFFIX,browsercrp.vivo.com.cn,{build.GROUP_SAFE}"),
        )
        self.assertLess(
            text.index(f"DOMAIN-SUFFIX,browsercrp.vivo.com.cn,{build.GROUP_SAFE}"),
            text.index(f"DOMAIN-SUFFIX,hoyoverse.com,{build.GROUP_GAME}"),
        )
        self.assertLess(
            text.index(f"DOMAIN-SUFFIX,hoyoverse.com,{build.GROUP_GAME}"),
            text.index(f"DOMAIN-SUFFIX,chase.com,{build.GROUP_NA}"),
        )
        self.assertLess(
            text.index(f"DOMAIN-SUFFIX,chase.com,{build.GROUP_NA}"),
            text.index(f"PROCESS-NAME,com.miHoYo.Yuanshen,{build.GROUP_GAME}"),
        )
        self.assertLess(
            text.index(f"PROCESS-NAME,com.miHoYo.Yuanshen,{build.GROUP_GAME}"),
            text.index(f"PROCESS-NAME,com.chase.sig.android,{build.GROUP_NA}"),
        )
        self.assertLess(
            text.index(f"PROCESS-NAME,com.chase.sig.android,{build.GROUP_NA}"),
            text.index(f"PROCESS-NAME,com.reddit.frontpage,{build.GROUP_GLOBAL}"),
        )
        self.assertLess(
            text.index(f"PROCESS-NAME,com.reddit.frontpage,{build.GROUP_GLOBAL}"),
            text.index(f"MATCH,{build.GROUP_FINAL}"),
        )
        group_block = text.split("proxy-groups:\n", 1)[1].split("rule-providers:", 1)[0]
        def group_pos(name: str) -> int:
            return group_block.index(f"  - name: \"{name}\"")

        self.assertLess(group_pos(build.GROUP_18), group_pos(build.GROUP_MISSAV))
        self.assertLess(group_pos(build.GROUP_MISSAV), group_pos(build.GROUP_SAFE))
        self.assertLess(group_pos(build.GROUP_SAFE), group_pos(build.GROUP_GAME))
        self.assertLess(group_pos(build.GROUP_GAME), group_pos(build.GROUP_NA))
        self.assertLess(group_pos(build.GROUP_NA), group_pos(build.GROUP_GLOBAL))
        self.assertLess(group_pos(build.GROUP_GLOBAL), group_pos(build.GROUP_FINAL))
        self.assertNotIn("geolocation-!cn", text)
        self.assertNotIn("GEOIP,!CN", text)
        self.assertNotIn("ACL4SSR", build.render("backcn", [], [], ""))
        self.assertIn(
            f"{build.ACL4SSR_BASE}/Providers/ProxyGFWlist.yaml",
            text,
        )

    def test_muse_rules_accept_domain_and_suffix(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "muse.list"
            path.write_text(
                "domain-suffix,muse.ai\n"
                "domain,auth.meta.com\n"
                "# comment\n"
                "domain,www.multimango.com\n",
                encoding="utf-8",
            )
            self.assertEqual(
                build.load_muse_rules(str(path)),
                [
                    f"DOMAIN-SUFFIX,muse.ai,{build.GROUP_MUSE}",
                    f"DOMAIN,auth.meta.com,{build.GROUP_MUSE}",
                    f"DOMAIN,www.multimango.com,{build.GROUP_MUSE}",
                ],
            )

    def test_muse_is_a_five_group_universal_profile(self) -> None:
        root = Path(__file__).resolve().parents[2]
        muse_rules = build.load_muse_rules(str(root / "rules" / "muse.list"))
        text = build.render(
            "backcn", ["xiaohongshu.com"], [],
            "https://dns.example/dns-query", "muse", None, None, muse_rules,
        )
        same_if_cnip = build.render(
            "cnip", ["xiaohongshu.com"], [],
            "https://dns.example/dns-query", "muse", None, None, muse_rules,
        )
        self.assertEqual(text, same_if_cnip)
        self.assertIn("enhanced-mode: redir-host", text)
        self.assertIn("respect-rules: true", text)
        self.assertNotIn("find-process-mode:", text)
        self.assertNotIn("PROCESS-NAME,", text)
        self.assertNotIn("store-fake-ip:", text)
        self.assertNotIn("  - name: PROXY\n", text)
        self.assertNotIn("  - name: YouTube\n", text)
        self.assertNotIn(f"  - name: \"{build.GROUP_18}\"", text)
        self.assertNotIn(f"  - name: \"{build.GROUP_NA}\"", text)
        self.assertNotIn(f"  - name: \"{build.GROUP_GAME}\"", text)
        group_block = text.split("proxy-groups:\n", 1)[1].split("rule-providers:", 1)[0]
        self.assertEqual(group_block.count("  - name:"), len(build.MUSE_SELECT_GROUPS) + 1)

        def group_pos(name: str) -> int:
            return group_block.index(f"  - name: \"{name}\"")

        self.assertLess(group_pos(build.GROUP_YOUTUBE), group_pos(build.GROUP_MUSE))
        self.assertLess(group_pos(build.GROUP_MUSE), group_pos(build.GROUP_GLOBAL))
        self.assertLess(group_pos(build.GROUP_GLOBAL), group_pos(build.GROUP_CN))
        self.assertLess(group_pos(build.GROUP_CN), group_pos(build.GROUP_FINAL))
        youtube_group = text.split(f'  - name: "{build.GROUP_YOUTUBE}"\n', 1)[1].split(
            "  - name:", 1
        )[0]
        muse_group = text.split(f'  - name: "{build.GROUP_MUSE}"\n', 1)[1].split(
            "  - name:", 1
        )[0]
        self.assertIn(f'      - "{build.GROUP_GLOBAL}"', youtube_group)
        self.assertIn(f'      - "{build.GROUP_GLOBAL}"', muse_group)
        self.assertIn("    use:\n      - private-provider", muse_group)
        self.assertIn(f"DOMAIN-SUFFIX,muse.ai,{build.GROUP_MUSE}", text)
        self.assertIn(f"DOMAIN,auth.meta.com,{build.GROUP_MUSE}", text)
        self.assertIn(f"DOMAIN,api.meta.ai,{build.GROUP_MUSE}", text)
        self.assertIn(f"DOMAIN,hatch-api.meta.ai,{build.GROUP_MUSE}", text)
        self.assertIn(f"DOMAIN,hatch.metaaivm.com,{build.GROUP_MUSE}", text)
        self.assertIn(f"DOMAIN,www.multimango.com,{build.GROUP_MUSE}", text)
        self.assertNotIn("graph.facebook.com", text)
        self.assertNotIn("facebook.com", text)
        self.assertIn(f"RULE-SET,youtube,{build.GROUP_YOUTUBE}", text)
        self.assertIn(f"RULE-SET,acl-gfw,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"RULE-SET,acl-proxy-media,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"RULE-SET,acl-telegram,{build.GROUP_GLOBAL}", text)
        self.assertIn(f"DOMAIN-SUFFIX,xiaohongshu.com,{build.GROUP_CN}", text)
        self.assertIn(f"RULE-SET,acl-cn-domain,{build.GROUP_CN}", text)
        self.assertIn(f"RULE-SET,cn-domain,{build.GROUP_CN}", text)
        self.assertIn(f"GEOIP,CN,{build.GROUP_CN},no-resolve", text)
        self.assertIn(f"MATCH,{build.GROUP_FINAL}", text)
        self.assertEqual(build.GROUP_CN, "🇨🇳 中国代理")
        self.assertEqual(build.HEALTH_CHECK_URL, "https://captive.apple.com")
        self.assertIn(f'      url: "{build.HEALTH_CHECK_URL}"', text)
        self.assertLess(
            text.index(f"GEOIP,CN,{build.GROUP_CN},no-resolve"),
            text.index(f"MATCH,{build.GROUP_FINAL}"),
        )
        self.assertLess(
            text.index(f"DOMAIN-SUFFIX,muse.ai,{build.GROUP_MUSE}"),
            text.index(f"RULE-SET,youtube,{build.GROUP_YOUTUBE}"),
        )
        self.assertLess(
            text.index(f"RULE-SET,youtube,{build.GROUP_YOUTUBE}"),
            text.index(f"RULE-SET,acl-gfw,{build.GROUP_GLOBAL}"),
        )
        self.assertLess(
            text.index(f"RULE-SET,acl-gfw,{build.GROUP_GLOBAL}"),
            text.index(f"GEOIP,CN,{build.GROUP_CN},no-resolve"),
        )
        self.assertIn('    "+.muse.ai": "https://dns.example/dns-query"', text)
        self.assertIn('    "auth.meta.com": "https://dns.example/dns-query"', text)
        self.assertNotIn("graph.facebook.com", text)
        self.assertIn('    "+.xiaohongshu.com": "https://223.5.5.5/dns-query"', text)
        self.assertIn('    "rule-set:youtube": "https://dns.example/dns-query"', text)
        self.assertIn('    "rule-set:acl-gfw": "https://dns.example/dns-query"', text)
        self.assertIn('    "rule-set:acl-cn-domain": "https://223.5.5.5/dns-query"', text)
        self.assertNotIn("geolocation-!cn", text)
        self.assertNotIn("GEOIP,!CN", text)
        self.assertNotIn("dns.nextdns.io", text)
        self.assertIn(
            f"{build.ACL4SSR_BASE}/Providers/ProxyGFWlist.yaml",
            text,
        )
        self.assertNotIn("ACL4SSR", build.render("backcn", [], [], ""))


if __name__ == "__main__":
    unittest.main()
