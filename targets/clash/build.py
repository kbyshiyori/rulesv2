#!/usr/bin/env python3
"""Build minimal mihomo profiles for Clash/Hako, Clash Verge Rev, or FlClash."""
from __future__ import annotations

import argparse
import ipaddress
import sys
from pathlib import Path

CN_DOMAIN_URL = (
    "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/"
    "meta/geo/geosite/cn.mrs"
)
CN_IP_URL = (
    "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/"
    "meta/geo/geoip/cn.mrs"
)
ADS_URL = (
    "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/"
    "meta/geo/geosite/category-ads-all.mrs"
)
YOUTUBE_URL = (
    "https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/"
    "meta/geo/geosite/youtube.mrs"
)
ACL4SSR_BASE = "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash"
PRIVATE_PROVIDER_PATH = "./providers/private-provider.yaml"
HEALTH_CHECK_URL = "https://captive.apple.com"
CN_DNS = "https://223.5.5.5/dns-query"
FOREIGN_DNS_DEFAULT = "https://1.1.1.1/dns-query"
PLATFORMS = ("hako", "verge", "flclash")
GROUP_NA = "🇨🇦 北美"
GROUP_GAME = "🎮 游戏"
GROUP_GLOBAL = "🎯 全球直连"
GROUP_18 = "🔞 18"
GROUP_MISSAV = "🎬 missav"
GROUP_SAFE = "🛡️ 安全浏览"
GROUP_FINAL = "🐟 漏网之鱼"
ANDROID_GROUPS = (GROUP_NA, GROUP_GAME, GROUP_GLOBAL)
FLCLASH_SELECT_GROUPS = (GROUP_18, GROUP_MISSAV, GROUP_SAFE, GROUP_GAME, GROUP_NA, GROUP_GLOBAL)
POLICY_DOMAIN_TARGETS = ANDROID_GROUPS + (GROUP_18, GROUP_MISSAV, GROUP_SAFE, GROUP_FINAL, "DIRECT", "PROXY", "REJECT")
ALWAYS_DIRECT_PACKAGES = frozenset({"com.follow.clash"})
CN_SIDE_GROUPS = frozenset({GROUP_FINAL, GROUP_SAFE})
FLCLASH_FOREIGN_RULE_SETS = ("youtube", "acl-telegram", "acl-proxy-media", "acl-gfw")
FLCLASH_CN_RULE_SETS = ("acl-cn-domain", "cn-domain")

ACL4SSR_PROVIDERS = (
    ("acl-lan", "classical", "yaml", f"{ACL4SSR_BASE}/Providers/LocalAreaNetwork.yaml"),
    ("acl-program-ads", "classical", "yaml", f"{ACL4SSR_BASE}/Providers/BanProgramAD.yaml"),
    ("acl-telegram", "classical", "text", f"{ACL4SSR_BASE}/Telegram.list"),
    ("acl-proxy-media", "classical", "yaml", f"{ACL4SSR_BASE}/Providers/ProxyMedia.yaml"),
    ("acl-gfw", "classical", "yaml", f"{ACL4SSR_BASE}/Providers/ProxyGFWlist.yaml"),
    ("acl-cn-domain", "classical", "yaml", f"{ACL4SSR_BASE}/Providers/ChinaDomain.yaml"),
    ("acl-cn-company-ip", "ipcidr", "yaml", f"{ACL4SSR_BASE}/Providers/ChinaCompanyIp.yaml"),
    ("acl-cn-ip", "ipcidr", "yaml", f"{ACL4SSR_BASE}/Providers/ChinaIp.yaml"),
    ("acl-cn-ipv6", "ipcidr", "yaml", f"{ACL4SSR_BASE}/Providers/ChinaIpV6.yaml"),
)


def load_domains(path: str) -> list[str]:
    domains: list[str] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        value = raw.strip().lower().rstrip(".")
        if not value or value.startswith("#"):
            continue
        if "," in value or " " in value or "." not in value:
            raise SystemExit(f"error: invalid domain at {path}:{line_number}: {raw}")
        if value not in seen:
            seen.add(value)
            domains.append(value)
    return domains


def load_direct_rules(path: str) -> list[str]:
    rules: list[str] = []
    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip().lower() for field in line.split(",")]
        match fields:
            case ["ip-cidr", network] if network:
                try:
                    parsed = ipaddress.ip_network(network, strict=True)
                except ValueError as exc:
                    raise SystemExit(
                        f"error: invalid IP network at {path}:{line_number}: {raw}"
                    ) from exc
                kind = "IP-CIDR" if parsed.version == 4 else "IP-CIDR6"
                rules.append(f"{kind},{parsed},DIRECT,no-resolve")
            case ["domain-suffix", domain] if domain:
                rules.append(f"DOMAIN-SUFFIX,{domain.rstrip('.')},DIRECT")
            case ["protocol-port", protocol, port] if protocol in {"tcp", "udp"}:
                if not port.isdigit() or not 1 <= int(port) <= 65535:
                    raise SystemExit(f"error: invalid port at {path}:{line_number}: {raw}")
                rules.append(f"AND,((NETWORK,{protocol}),(DST-PORT,{port})),DIRECT")
            case _:
                raise SystemExit(f"error: invalid direct intent at {path}:{line_number}: {raw}")
    return rules


def load_android_apps(path: str) -> dict[str, list[str]]:
    groups = {name: [] for name in ANDROID_GROUPS}
    seen: set[str] = set()
    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 2 or fields[0] not in groups or "." not in fields[1]:
            raise SystemExit(f"error: invalid android app at {path}:{line_number}: {raw}")
        package = fields[1]
        if package in seen or package in ALWAYS_DIRECT_PACKAGES:
            continue
        seen.add(package)
        groups[fields[0]].append(package)
    return groups


def load_policy_domains(path: str) -> list[str]:
    rules: list[str] = []
    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        match [fields[0].lower(), *fields[1:]]:
            case ["domain-suffix", domain, target] if domain and target in POLICY_DOMAIN_TARGETS:
                rules.append(f"DOMAIN-SUFFIX,{domain.lower().rstrip('.')},{target}")
            case _:
                raise SystemExit(
                    f"error: invalid policy domain at {path}:{line_number}: {raw}"
                )
    return rules


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _yaml_name(name: str) -> str:
    if not name or name[0].isdigit() or any(ord(char) > 127 for char in name):
        return quote(name)
    return name


def _select_group(name: str, proxies: tuple[str, ...] = ("PROXY", "DIRECT")) -> list[str]:
    lines = [
        f"  - name: {_yaml_name(name)}",
        "    type: select",
        "    proxies:",
    ]
    for proxy in proxies:
        lines.append(f"      - {proxy}")
    lines.extend([
        "    use:",
        "      - private-provider",
    ])
    return lines


def _rule_provider(name: str, behavior: str, fmt: str, url: str, path: str) -> list[str]:
    return [
        f"  {name}:",
        "    type: http",
        f"    behavior: {behavior}",
        f"    format: {fmt}",
        f"    url: {quote(url)}",
        f"    path: {path}",
        "    interval: 86400",
    ]


def _hako_dns(domains: list[str], dns: str, profile: str) -> list[str]:
    cn_dns_route = "PROXY" if profile == "backcn" else "DIRECT"
    foreign_dns_route = "DIRECT" if profile == "backcn" else "PROXY"
    foreign_dns = dns or FOREIGN_DNS_DEFAULT
    lines = [
        "dns:",
        "  enable: true",
        "  ipv6: true",
        "  enhanced-mode: fake-ip",
        "  fake-ip-range: 198.18.0.1/16",
        "  use-hosts: true",
        "  fake-ip-filter:",
        '    - "+.lan"',
        '    - "+.local"',
        "  default-nameserver:",
        "    - system",
        "  proxy-server-nameserver:",
        "    - system",
        "  nameserver:",
        f"    - {quote(foreign_dns + '#' + foreign_dns_route)}",
        "  nameserver-policy:",
        f"    {quote('rule-set:youtube')}: {quote(foreign_dns + '#YouTube')}",
        f"    {quote('rule-set:cn-domain')}: {quote(CN_DNS + '#' + cn_dns_route)}",
    ]
    for domain in domains:
        lines.append(
            f"    {quote('+.' + domain)}: "
            f"{quote(CN_DNS + '#' + cn_dns_route)}"
        )
    return lines


def _flclash_resolver(target: str, foreign_dns: str) -> str:
    if target in CN_SIDE_GROUPS:
        return CN_DNS
    if target in {"DIRECT", "REJECT"}:
        return "system"
    return foreign_dns


def _flclash_dns(domains: list[str], dns: str, policy_domains: list[str]) -> list[str]:
    foreign_dns = dns or FOREIGN_DNS_DEFAULT
    lines = [
        "dns:",
        "  enable: true",
        "  ipv6: true",
        "  enhanced-mode: redir-host",
        "  respect-rules: true",
        "  use-hosts: true",
        "  default-nameserver:",
        "    - system",
        "  proxy-server-nameserver:",
        "    - system",
        "  nameserver:",
        f"    - {quote(CN_DNS)}",
        "  nameserver-policy:",
        f"    {quote('+.lan')}: system",
        f"    {quote('+.local')}: system",
        "    pikvm.kbyshiyori.com: system",
    ]
    seen = {"+.lan", "+.local", "pikvm.kbyshiyori.com"}
    for rule in policy_domains:
        _kind, domain, target = rule.split(",", 2)
        key = "+." + domain
        if key not in seen:
            seen.add(key)
            lines.append(f"    {quote(key)}: {quote(_flclash_resolver(target, foreign_dns))}")
    for domain in domains:
        key = "+." + domain
        if key not in seen:
            seen.add(key)
            lines.append(f"    {quote(key)}: {quote(CN_DNS)}")
    for name in FLCLASH_FOREIGN_RULE_SETS:
        lines.append(f"    {quote('rule-set:' + name)}: {quote(foreign_dns)}")
    for name in FLCLASH_CN_RULE_SETS:
        lines.append(f"    {quote('rule-set:' + name)}: {quote(CN_DNS)}")
    return lines


def render(
    profile: str,
    domains: list[str],
    direct_rules: list[str],
    dns: str,
    platform: str = "hako",
    android_apps: dict[str, list[str]] | None = None,
    policy_domains: list[str] | None = None,
) -> str:
    if platform not in PLATFORMS:
        raise ValueError(f"unsupported platform: {platform}")
    android_apps = android_apps or {name: [] for name in ANDROID_GROUPS}
    policy_domains = policy_domains or []
    if platform == "flclash":
        cn_policy = GROUP_FINAL
        fallback = GROUP_FINAL
        foreign_policy = GROUP_GLOBAL
        youtube_policy = GROUP_GLOBAL
        profile_label = "single FlClash profile; switch 🎯 全球直连 / 🐟 漏网之鱼 by location"
    else:
        cn_policy = "PROXY" if profile == "backcn" else "DIRECT"
        fallback = "DIRECT" if profile == "backcn" else "PROXY"
        foreign_policy = fallback
        youtube_policy = "YouTube"
        profile_label = (
            "CN via proxy, overseas direct" if profile == "backcn"
            else "CN direct, overseas via proxy"
        )

    lines = [
        "# Generated by rulesv2. Install private-provider.yaml locally; never publish node credentials.",
        f"# Profile: {profile_label}",
        "mode: rule",
        "log-level: warning",
        "ipv6: true",
        "unified-delay: true",
        "tcp-concurrent: true",
    ]
    if platform in {"verge", "flclash"}:
        lines.append("find-process-mode: always")
    if platform == "flclash":
        lines.extend([
            "sniffer:",
            "  enable: true",
            "  override-destination: false",
            "  sniff:",
            "    HTTP:",
            "      ports: [80, 443]",
            "    TLS:",
            "      ports: [443]",
            "    QUIC:",
            "      ports: [443]",
        ])
    lines.extend([
        "profile:",
        "  store-selected: true",
    ])
    if platform != "flclash":
        lines.append("  store-fake-ip: true")
    if platform == "flclash":
        lines.extend(_flclash_dns(domains, dns, policy_domains))
    else:
        lines.extend(_hako_dns(domains, dns, profile))

    lines.extend([
        "proxy-providers:",
        "  private-provider:",
        "    type: file",
        f"    path: {quote(PRIVATE_PROVIDER_PATH)}",
        "    health-check:",
        "      enable: true",
        f"      url: {quote(HEALTH_CHECK_URL)}",
        "      expected-status: 200",
        "      interval: 600",
        "      lazy: true",
        "proxy-groups:",
    ])
    if platform == "flclash":
        for name in FLCLASH_SELECT_GROUPS:
            lines.extend(_select_group(name, ("DIRECT", GROUP_FINAL)))
        lines.extend(_select_group(GROUP_FINAL, ("DIRECT", "REJECT")))
    else:
        lines.extend([
            "  - name: PROXY",
            "    type: select",
            "    proxies:",
            "      - REJECT",
            "    use:",
            "      - private-provider",
            "  - name: YouTube",
            "    type: select",
            "    proxies:",
            "      - PROXY",
            "      - DIRECT",
            "    use:",
            "      - private-provider",
        ])
        if platform == "verge":
            lines.extend(_select_group("原神"))
    lines.extend([
        "rule-providers:",
        *_rule_provider("cn-domain", "domain", "mrs", CN_DOMAIN_URL, "./rules/cn-domain.mrs"),
        *_rule_provider("cn-ip", "ipcidr", "mrs", CN_IP_URL, "./rules/cn-ip.mrs"),
        *_rule_provider("ads", "domain", "mrs", ADS_URL, "./rules/ads.mrs"),
        *_rule_provider("youtube", "domain", "mrs", YOUTUBE_URL, "./rules/youtube.mrs"),
    ])
    if platform == "flclash":
        for name, behavior, fmt, url in ACL4SSR_PROVIDERS:
            suffix = ".list" if fmt == "text" else ".yaml"
            lines.extend(
                _rule_provider(name, behavior, fmt, url, f"./rules/{name}{suffix}")
            )
    lines.extend([
        "rules:",
        "  - DOMAIN,pikvm.kbyshiyori.com,DIRECT",
    ])
    if platform == "verge":
        lines.append("  - PROCESS-NAME,YuanShen.exe,原神")
    if platform == "flclash":
        lines.extend(f"  - {rule}" for rule in policy_domains)
        for package in android_apps.get(GROUP_GAME, []):
            lines.append(f"  - PROCESS-NAME,{package},{GROUP_GAME}")
        for package in android_apps.get(GROUP_NA, []):
            lines.append(f"  - PROCESS-NAME,{package},{GROUP_NA}")
        for package in android_apps.get(GROUP_GLOBAL, []):
            lines.append(f"  - PROCESS-NAME,{package},{GROUP_GLOBAL}")
        for package in ALWAYS_DIRECT_PACKAGES:
            lines.append(f"  - PROCESS-NAME,{package},DIRECT")
    lines.extend(f"  - {rule}" for rule in direct_rules)
    lines.extend(f"  - DOMAIN-SUFFIX,{domain},{cn_policy}" for domain in domains)
    lines.extend([
        f"  - RULE-SET,youtube,{youtube_policy}",
        "  - RULE-SET,ads,REJECT",
    ])
    if platform == "flclash":
        lines.extend([
            "  - RULE-SET,acl-program-ads,REJECT",
            "  - RULE-SET,acl-lan,DIRECT",
            f"  - RULE-SET,acl-telegram,{foreign_policy}",
            f"  - RULE-SET,acl-proxy-media,{foreign_policy}",
            f"  - RULE-SET,acl-gfw,{foreign_policy}",
            f"  - RULE-SET,acl-cn-domain,{cn_policy}",
        ])
    lines.append(f"  - RULE-SET,cn-domain,{cn_policy}")
    if platform == "flclash":
        lines.extend([
            f"  - RULE-SET,acl-cn-company-ip,{cn_policy},no-resolve",
            f"  - RULE-SET,acl-cn-ip,{cn_policy},no-resolve",
            f"  - RULE-SET,acl-cn-ipv6,{cn_policy},no-resolve",
        ])
    lines.append(f"  - RULE-SET,cn-ip,{cn_policy},no-resolve")
    if platform == "flclash":
        lines.append(f"  - GEOIP,CN,{cn_policy},no-resolve")
    lines.extend([
        "  - IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
        "  - IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
        "  - IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
        "  - IP-CIDR6,fc00::/7,DIRECT,no-resolve",
        f"  - MATCH,{fallback}",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["backcn", "cnip"], default="")
    parser.add_argument("--platform", choices=list(PLATFORMS), default="hako")
    parser.add_argument("--rules", required=True, help="path to redirect-to-cn.list")
    parser.add_argument("--direct-rules", required=True, help="path to direct.list")
    parser.add_argument("--android-apps", default="", help="path to android-apps.list")
    parser.add_argument("--policy-domains", default="", help="path to policy-domains.list")
    parser.add_argument("--dns", default="", help="foreign DoH URL; defaults to Cloudflare")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.platform != "flclash" and args.profile not in {"backcn", "cnip"}:
        parser.error("--profile is required unless --platform flclash")

    domains = load_domains(args.rules)
    direct_rules = load_direct_rules(args.direct_rules)
    android_apps = load_android_apps(args.android_apps) if args.android_apps else None
    policy_domains = load_policy_domains(args.policy_domains) if args.policy_domains else None
    profile = args.profile or "backcn"
    text = render(
        profile,
        domains,
        direct_rules,
        args.dns,
        args.platform,
        android_apps,
        policy_domains,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    app_count = sum(len(packages) for packages in (android_apps or {}).values())
    profile_label = "single" if args.platform == "flclash" else profile
    print(
        f"built {out} | platform={args.platform} | profile={profile_label} | direct={len(direct_rules)} | "
        f"redirect-to-cn={len(domains)} | android-apps={app_count} | "
        f"policy-domains={len(policy_domains or [])} | dns={'custom' if args.dns else 'cloudflare'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
