# targets/clash

Emits minimal mihomo YAML profiles for the native **Clash for Apple Platforms**
(Hako) on iOS/macOS, **Clash Verge Rev** on Windows, and **FlClash** on Android.
The same builder and client-agnostic `rules/` lists produce each client's profiles:

- `clash-backcn.yaml`: mainland-China destinations use `PROXY`; everything else is
  `DIRECT`.
- `clash-cnip.yaml`: mainland-China destinations are `DIRECT`; everything else uses
  `PROXY`.
- `clash-verge-backcn.yaml` / `clash-verge-cnip.yaml`: the corresponding Windows
  profiles, with an additional `YuanShen.exe` process rule.
- `flclash-backcn.yaml` / `flclash-cnip.yaml`: Android FlClash profiles. Same CN/overseas
  split, plus NekoBox app groups (`北美`, `游戏`, `绕过`) and ACL4SSR foreign/CN lists
  instead of `geolocation-!cn`.

The Hako/Verge profiles use MetaCubeX `cn.mrs`, `cn-ip.mrs`, `youtube.mrs`, and
`category-ads-all.mrs` rule
providers. MRS is intentional: large YAML/text rule sets can exceed the memory available
to an iOS Network Extension. FlClash keeps those MRS sets and adds ACL4SSR classical
providers (`ProxyGFWlist`, `ProxyMedia`, `Telegram`, `ChinaDomain`, `ChinaIp`).

## Private node setup

Published profiles contain no node or credential. They declare a file Proxy Source named
`private-provider`, with a core-managed path `./providers/private-provider.yaml`. On each
device, import a private YAML file named `private-provider.yaml` into that profile's
**Proxy Sources** → **private-provider** → **Source: file** → **Choose File**. Hako copies
the selected file into the profile's protected resource store; the original path is not
used at runtime. Re-import the file if its contents change. Until a valid local provider
is installed, `PROXY` falls back to `REJECT` rather than `DIRECT`.

The private file must contain only a `proxies:` list, not `rules:` or `proxy-groups:`.
Each device can use the same file name while keeping its own WireGuard client key and
address. Do not commit or publish any device's private file. For `backcn`, select a
mainland-China node in `PROXY`; for `cnip`, select an overseas node.

Both profiles expose a separate `YouTube` select group populated from the same private
provider. Its selection is independent of `PROXY`; no default node is forced. YouTube DNS
uses the foreign resolver through the node selected in that group.

## Clash Verge Rev on Windows

Clash Verge Rev runs mihomo, so the Hako YAML rule syntax is reusable. The Windows
variant adds `PROCESS-NAME,YuanShen.exe,原神` near the top of the rules, before the
shared `direct.list` exceptions, and enables process matching. `原神` is an independent select group with `PROXY`,
`DIRECT`, and every node in the local private provider, like `YouTube`. The selection
affects traffic from that executable only; the game websites still follow domain rules.

The public profile contains rules, groups, DNS settings and a reference to the private
provider, but no node credentials. On Windows, save a `proxies:`-only
`private-provider.yaml` at
`%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\providers\private-provider.yaml`
(create the `providers` folder if necessary). This is relative to mihomo's application
home, not to the downloaded profile file. Keep it private. Then import the matching
published profile URL into Clash Verge Rev, select **Rule** mode, and pick nodes in the
`PROXY`, `YouTube`, and `原神` groups. Use Clash Verge Rev's **TUN** mode so Windows
game traffic, including UDP, enters mihomo; system proxy alone may not capture the game.
Choose a node that supports UDP when routing the game through it. If the process is not
shown as `YuanShen.exe` in Verge's connections view, update the rule to the actual
executable name.

The private provider can be the same *format* used on iOS, while each device keeps its
own node credentials. A remote node subscription in Verge is a separate main profile;
this rules profile instead reads a local file provider so changing nodes does not require
publishing them in the rules repo.

原神 routing is app/process-based rather than tied to server IPs. This repository encodes
Windows as `YuanShen.exe` → `原神` in the Verge profile, and Android as
`com.miHoYo.Yuanshen` → `游戏` in the FlClash profile.

## FlClash on Android

FlClash runs mihomo, so it consumes the same YAML rule language. The FlClash profiles
turn the NekoBox snapshot in [`docs/nekobox-route-snapshot.json`](../../docs/nekobox-route-snapshot.json)
into `PROCESS-NAME` rules from [`rules/android-apps.list`](../../rules/android-apps.list):

| Group | Exit | Examples |
|-------|------|----------|
| `北美` | select (pick the US/PayPal node) | Chase, Citi, Discover, Experian, T-Life, U.S. Bank, YouTube app; `18comic.vip`, `hanime1.me` |
| `游戏` | select (pick the JP/game node) | 原神; `missav.ai`, `missav.ws` |
| `绕过` | `DIRECT` on `backcn` only | Google/Play/GMS, PayPal, Slack, X, Reddit, FlClash itself, … |
| unmatched | `MATCH,DIRECT` (`backcn`) or `MATCH,PROXY` (`cnip`) | replaces NekoBox `geolocation-!cn` |

`绕过` apps stay local when you are abroad (`backcn`). On `cnip` those apps are **not**
forced DIRECT (otherwise X/Reddit/Play would leak to the mainland network); only
`com.follow.clash` stays DIRECT so the VPN client cannot loop. YouTube and T-Life are in
`北美` only: that rule sat above `绕过app` on the phone.

Foreign classification follows [ACL4SSR_BackCN.ini](https://github.com/ACL4SSR/ACL4SSR/blob/master/Clash/config/ACL4SSR_BackCN.ini): known-foreign lists (`Telegram`, `ProxyMedia`, `ProxyGFWlist`) take the overseas policy, China lists plus `GEOIP,CN` take the CN policy. Unmatched traffic uses this repo's `MATCH` fallback (`DIRECT` for 回国), not ACL4SSR's `漏网之鱼` defaulting to the China node, and not NekoBox's negative `geolocation-!cn` list.

Import the published URL in FlClash, **Rule** mode, enable process lookup (查找进程), and
install `private-provider.yaml` into the profile's `private-provider` file source — same
format as Hako. Pick nodes in `PROXY`, `北美`, `游戏`, and `YouTube`. FlClash's own
access-control app list is VPN membership only; it does not replace these `PROCESS-NAME`
rules.

## Build

```sh
python build.py --profile backcn \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --out ../../dist/clash/clash-backcn.yaml

python build.py --profile cnip \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --out ../../dist/clash/clash-cnip.yaml

python build.py --platform verge --profile backcn \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --out ../../dist/clash/clash-verge-backcn.yaml

python build.py --platform flclash --profile backcn \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --android-apps ../../rules/android-apps.list \
  --policy-domains ../../rules/policy-domains.list \
  --out ../../dist/clash/flclash-backcn.yaml
```

Pass `--dns "$NEXTDNS_DOH_URL"` to use the same foreign resolver as the Shadowrocket
profiles. Without it, the builder uses Cloudflare DoH. CN names use
`https://223.5.5.5/dns-query`. Resolver traffic follows its matching exit explicitly:

- `backcn`: NextDNS `#DIRECT`; AliDNS `#PROXY`.
- `cnip`: AliDNS `#DIRECT`; NextDNS `#PROXY`.
