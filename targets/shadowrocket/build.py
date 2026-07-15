#!/usr/bin/env python3
"""Build the Shadowrocket 回国 (backcn) config.

Pipeline:
  upstream Johnshall sr_backcn_ad.conf
    -> inject redirect-to-cn rules at the TOP of [Rule]   (win over GEOIP + ad Reject)
    -> inline-expand a China-domain list as DOMAIN-SUFFIX,<d>,PROXY, placed AFTER the ad
       Reject list and BEFORE FINAL (so 境内 ad-block still wins, but CN domains route via
       the node and are resolved node-side, never by the local/境外 DNS)
    -> optionally override [General] dns-server with a NextDNS DoH URL (境外 DNS)
    -> write dist/shadowrocket/backcn.conf

Why the two blocks sit in different places:
  Shadowrocket evaluates DOMAIN-type rules ahead of GEOIP/IP rules, and among domain rules
  by file order. The upstream ad Reject list is ~56k DOMAIN-SUFFIX,...,Reject lines. If the
  broad China list went above them, a rule like DOMAIN-SUFFIX,baidu.com,PROXY would beat
  DOMAIN-SUFFIX,mobads.baidu.com,Reject and leak the ad. So the broad list goes just before
  FINAL. redirect-to-cn stays at the top on purpose: those are the services that must work
  fully (their own tracking included), and they are not ad domains.

Design notes:
  * Output contains NO node/proxy secrets. In Shadowrocket you pick the China node and set
    it to "use config"; the PROXY policy follows the selected node.
  * The NextDNS DoH URL is a semi-secret; it is passed via --dns from a CI secret and never
    committed. Empty --dns leaves the upstream dns-server untouched.
  * We keep the `_ad` upstream on purpose: 境内 ad-block is wanted; 境外 ad-block is handled
    by NextDNS, so foreign reject entries are harmless redundancy.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_UPSTREAM = (
    "https://raw.githubusercontent.com/Johnshall/"
    "Shadowrocket-ADBlock-Rules-Forever/release/sr_backcn_ad.conf"
)
# felixonmars/dnsmasq-china-list: the canonical CN accelerated-domains list (dnsmasq fmt).
DEFAULT_CHINA_LIST = (
    "https://raw.githubusercontent.com/felixonmars/"
    "dnsmasq-china-list/master/accelerated-domains.china.conf"
)

RC_BEGIN = "# >>> rulesv2 redirect-to-cn (auto-generated) >>>"
RC_END = "# <<< rulesv2 redirect-to-cn <<<"
CN_BEGIN = "# >>> rulesv2 china-domains (auto-generated, inlined) >>>"
CN_END = "# <<< rulesv2 china-domains <<<"
CN_FALLBACK_DNS = "https://dns.alidns.com/dns-query"


def read_upstream(url: str, file: str | None) -> str:
    if file:
        return Path(file).read_text(encoding="utf-8")
    return _fetch(url)


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "rulesv2-builder"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def load_domains(path: str) -> list[str]:
    domains: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            domains.append(line)
    return domains


def parse_china_list(text: str, exclude: list[str]) -> list[str]:
    """Parse dnsmasq `server=/<domain>/<dns>` lines into deduped domain suffixes,
    dropping any already covered by an `exclude` suffix (the redirect-to-cn domains)."""
    excl = tuple(exclude)
    seen: set[str] = set()
    out: list[str] = []
    for m in re.finditer(r"^server=/([^/]+)/", text, flags=re.M):
        d = m.group(1)
        if d in seen:
            continue
        if any(d == s or d.endswith("." + s) for s in excl):
            continue
        seen.add(d)
        out.append(d)
    return out


def _strip_block(text: str, begin: str, end: str) -> str:
    return re.sub(re.escape(begin) + r".*?" + re.escape(end) + r"\n?", "", text, flags=re.S)


def inject_redirect(text: str, domains: list[str]) -> str:
    text = _strip_block(text, RC_BEGIN, RC_END)
    block = "\n".join([RC_BEGIN, *[f"DOMAIN-SUFFIX,{d},PROXY" for d in domains], RC_END]) + "\n"
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "[Rule]":
            lines.insert(i + 1, "\n" + block)
            return "".join(lines)
    raise SystemExit("error: [Rule] section not found in upstream")


def inject_china(text: str, domains: list[str]) -> str:
    text = _strip_block(text, CN_BEGIN, CN_END)
    if not domains:
        return text
    block = "\n".join([CN_BEGIN, *[f"DOMAIN-SUFFIX,{d},PROXY" for d in domains], CN_END]) + "\n"
    lines = text.splitlines(keepends=True)
    # Prefer just before FINAL (keeps the block below the ad Reject list).
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("FINAL,"):
            lines.insert(i, block + "\n")
            return "".join(lines)
    # No FINAL: insert at end of [Rule] (before the next section header).
    in_rule = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "[Rule]":
            in_rule = True
            continue
        if in_rule and s.startswith("[") and s.endswith("]"):
            lines.insert(i, block + "\n")
            return "".join(lines)
    raise SystemExit("error: could not place china-domains block (no FINAL, no next section)")


def set_dns(text: str, dns_url: str) -> str:
    if not dns_url:
        return text
    new_line = f"dns-server = {dns_url}, {CN_FALLBACK_DNS}\n"
    lines = text.splitlines(keepends=True)
    in_general = False
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            in_general = s == "[General]"
            continue
        if in_general and s.startswith("dns-server"):
            lines[i] = new_line
            return "".join(lines)
    for i, line in enumerate(lines):
        if line.strip() == "[General]":
            lines.insert(i + 1, new_line)
            return "".join(lines)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream-url", default=DEFAULT_UPSTREAM)
    ap.add_argument("--upstream-file", default=None,
                    help="build from a local file instead of fetching (offline/testing)")
    ap.add_argument("--rules", required=True, help="path to redirect-to-cn.list")
    ap.add_argument("--china-mode", choices=["inline", "off"], default="inline",
                    help="inline-expand the China-domain list into DOMAIN-SUFFIX rules, or skip")
    ap.add_argument("--china-list-url", default=DEFAULT_CHINA_LIST)
    ap.add_argument("--china-list-file", default=None, help="local China list (offline/testing)")
    ap.add_argument("--dns", default="",
                    help="NextDNS DoH URL for 境外 traffic; empty keeps the upstream dns-server")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    text = read_upstream(args.upstream_url, args.upstream_file)
    redirect = load_domains(args.rules)

    china: list[str] = []
    if args.china_mode == "inline":
        raw = (Path(args.china_list_file).read_text(encoding="utf-8")
               if args.china_list_file else _fetch(args.china_list_url))
        china = parse_china_list(raw, exclude=redirect)

    text = inject_redirect(text, redirect)
    text = inject_china(text, china)
    text = set_dns(text, args.dns)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    size_mb = len(text.encode("utf-8")) / 1_048_576
    print(
        f"built {out} ({len(text.splitlines())} lines, {size_mb:.2f} MiB) | "
        f"redirect-to-cn={len(redirect)} | china={len(china)} ({args.china_mode}) | "
        f"dns={'nextdns' if args.dns else 'upstream'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
