#!/usr/bin/env python3
"""Build the Shadowrocket 回国 (backcn) config.

Pipeline:
  upstream Johnshall sr_backcn_ad.conf
    -> inject redirect-to-cn rules at the TOP of [Rule]  (win over GEOIP + ad Reject)
    -> optionally override [General] dns-server with a NextDNS DoH URL (境外 DNS)
    -> write dist/shadowrocket/backcn.conf

Design notes:
  * The output contains NO node/proxy secrets. In Shadowrocket you pick the China node
    manually and set it to "use config"; the PROXY policy follows the selected node.
  * The NextDNS DoH URL is a semi-secret (it embeds your config id). It is passed via
    --dns from a CI secret at build time and must never be committed. When --dns is
    empty the upstream dns-server line is left untouched, so a secret-free build is safe
    to inspect/share.
  * We keep the `_ad` upstream on purpose: 境内 ad-block (Reject list) is wanted. 境外
    ad-block is handled by NextDNS, so the foreign entries are harmless redundancy.
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
BEGIN = "# >>> rulesv2 redirect-to-cn (auto-generated) >>>"
END = "# <<< rulesv2 redirect-to-cn <<<"
CN_FALLBACK_DNS = "https://dns.alidns.com/dns-query"


def read_upstream(url: str, file: str | None) -> str:
    if file:
        return Path(file).read_text(encoding="utf-8")
    req = urllib.request.Request(url, headers={"User-Agent": "rulesv2-builder"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def load_domains(path: str) -> list[str]:
    domains: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            domains.append(line)
    return domains


def strip_existing_block(text: str) -> str:
    """Remove a previously injected block so re-runs are idempotent."""
    pattern = re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?"
    return re.sub(pattern, "", text, flags=re.S)


def inject_rules(text: str, domains: list[str]) -> str:
    text = strip_existing_block(text)
    block = "\n".join([BEGIN, *[f"DOMAIN-SUFFIX,{d},PROXY" for d in domains], END]) + "\n"
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "[Rule]":
            lines.insert(i + 1, "\n" + block)
            return "".join(lines)
    raise SystemExit("error: [Rule] section not found in upstream")


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
    # No dns-server present: add it right after [General].
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
    ap.add_argument("--dns", default="",
                    help="NextDNS DoH URL for 境外 traffic; empty keeps the upstream dns-server")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    text = read_upstream(args.upstream_url, args.upstream_file)
    domains = load_domains(args.rules)
    text = inject_rules(text, domains)
    text = set_dns(text, args.dns)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(
        f"built {out} ({len(text.splitlines())} lines, "
        f"{len(domains)} redirect-to-cn domains, "
        f"dns={'nextdns' if args.dns else 'upstream'})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
