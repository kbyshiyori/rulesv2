# targets/clash

Emits minimal mihomo YAML profiles for the native **Clash for Apple Platforms**
(Hako) on iOS/macOS, **Clash Verge Rev** on Windows, **FlClash** on Android, and a
simpler universal **Muse** profile for any mihomo client:

- `clash-backcn.yaml`: mainland-China destinations use `PROXY`; everything else is
  `DIRECT`.
- `clash-cnip.yaml`: mainland-China destinations are `DIRECT`; everything else uses
  `PROXY`.
- `clash-verge-backcn.yaml` / `clash-verge-cnip.yaml`: the corresponding Windows
  profiles, with an additional `YuanShen.exe` process rule.
- `flclash.yaml`: one Android FlClash profile. Switch `🎯 全球直连` and `🐟 漏网之鱼` by location;
  NekoBox app groups plus ACL4SSR foreign/CN lists. DNS uses AliDNS on the CN side and
  `--dns` / Cloudflare on the foreign side, each dialed through the same group as the
  connection (`redir-host` + `respect-rules`).
- `clash-backcn-muse.yaml`: one 5-group profile for both locations (no backcn/cnip split).
  `📺 YouTube`, `🎨 Muse`, `🎯 全球直连` (ACL4SSR GFW/media/Telegram), `🇨🇳 中国代理`, and
  `🐟 漏网之鱼`. Muse hosts come from `rules/muse.list`; other routing reuses `rules/` and
  ACL4SSR. Same-side DNS as FlClash.

The Hako/Verge profiles use MetaCubeX `cn.mrs`, `cn-ip.mrs`, `youtube.mrs`, and
`category-ads-all.mrs` rule
providers. MRS is intentional: large YAML/text rule sets can exceed the memory available
to an iOS Network Extension. FlClash and Muse keep those MRS sets and add ACL4SSR classical
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

One published file, not backcn/cnip. Location is a group selection, not a second
subscription.

| Group | What it matches | Typical pick |
|-------|-----------------|--------------|
| `🔞 18` | `18comic.vip`, `hanime1.me` | US/PayPal node |
| `🎬 missav` | `missav.ai`, `missav.ws` | JP/game node |
| `🛡️ 安全浏览` | `browsercrp.vivo.com.cn` | usually `DIRECT` |
| `🎮 游戏` | 原神 (`com.miHoYo.Yuanshen`) **and** hoyoverse/mihoyo suffixes | JP/game node |
| `🇨🇦 北美` | Chase, Citi, Discover, Experian, T-Life, U.S. Bank, YouTube **app**, Muse, plus those banks' suffixes | CA/PayPal node |
| `🎯 全球直连` | the NekoBox 绕过 apps (minus YouTube/T-Life/Muse) **and** ACL4SSR `ProxyGFWlist` / `ProxyMedia` / `Telegram` for the browser | `DIRECT` when abroad; an overseas node when in CN |
| `🐟 漏网之鱼` | CN lists, `redirect-to-cn`, `GEOIP,CN`, unmatched `MATCH` | China node when abroad; `DIRECT` when in CN |

Rules are emitted in that order, so domain groups win over app groups. YouTube **app** still beats the later YouTube rule-set.
`18` and `missav` stay as their own groups. `com.follow.clash` is always `DIRECT`.
Apps are `PROCESS-NAME` so they do not depend on foreign IP; ACL4SSR lists are for the
browser. `geolocation-!cn` is not used.

DNS uses `redir-host` + `respect-rules`. The **resolver** is AliDNS
(`https://223.5.5.5/dns-query`) for CN-side names (`🐟 漏网之鱼`, `🛡️ 安全浏览`, CN
rule-sets, `redirect-to-cn`) and `--dns` (Cloudflare if unset) for foreign-side names
(`🎯 全球直连`, `🔞 18`, `🎬 missav`, `🇨🇦 北美`, `🎮 游戏`, GFW/media/Telegram/YouTube).
The **path to that resolver** follows the domain's group, so switching `🎯 全球直连` /
`🐟 漏网之鱼` between `DIRECT` and a node also switches where the query egresses. Node
hostnames still use `system`. Inner DNS has no `PROCESS-NAME`, so 北美/游戏 company
suffixes live in `policy-domains.list`. YouTube **app** traffic stays `🇨🇦 北美`; YouTube
**DNS** follows the youtube rule-set (`🎯 全球直连`) — both foreign. Do not set
`direct-nameserver: system` or DIRECT groups would leak to the ISP resolver.

Import `https://kbyshiyori.github.io/rulesv2/flclash.yaml`, **Rule** mode, enable process
lookup (查找进程), install `private-provider.yaml` into `private-provider`. Access-control
app lists are VPN membership only; they do not replace these `PROCESS-NAME` rules.

## Clash Muse (5 groups)

One published file, not backcn/cnip. Same location-switch idea as FlClash, without Android
process groups or the extra 18 / missav / 北美 / 游戏 / 安全浏览 selectors. Group names
follow ACL4SSR (emoji + label).

| Group | What it matches | Typical pick |
|-------|-----------------|--------------|
| `📺 YouTube` | MetaCubeX `youtube` rule-set | inherit `🎯 全球直连`, or a dedicated node |
| `🎨 Muse` | `rules/muse.list` (`muse.ai` + Meta AI hosts) | inherit `🎯 全球直连`, or a dedicated node |
| `🎯 全球直连` | ACL4SSR `ProxyGFWlist` / `ProxyMedia` / `Telegram` (non-CN) | `DIRECT` when abroad; an overseas node when in CN |
| `🇨🇳 中国代理` | `redirect-to-cn`, ACL4SSR China domain/IP, MetaCubeX `cn`, `GEOIP,CN` | China node when abroad; `DIRECT` when in CN |
| `🐟 漏网之鱼` | `MATCH` fallback: anything that did not hit YouTube, Muse, ads, LAN, `🎯 全球直连`, or `🇨🇳 中国代理` | China node when abroad; `DIRECT` when in CN |

YouTube and Muse default to `🎯 全球直连` so a location switch cascades; pick a node in
those groups only when they need a different exit. Ads still `REJECT`. LAN / `direct.list`
stay `DIRECT`. `geolocation-!cn` is not used.

DNS uses `redir-host` + `respect-rules`, with each DoH URL bound to its routing group
(`https://…#📺 YouTube`, `#🎨 Muse`, `#🎯 全球直连`, `#🇨🇳 中国代理`, default `#🐟 漏网之鱼`).
AliDNS for CN-side names, `--dns` / Cloudflare for foreign-side names. A bare
`https://1.1.1.1/dns-query` would itself match `MATCH,🐟 漏网之鱼`; in CN that group is
`DIRECT`, so Cloudflare/NextDNS would be unreachable. Node hostnames still use `system`.
Proxy-provider health checks use `https://captive.apple.com`.

Import `https://kbyshiyori.github.io/rulesv2/clash-backcn-muse.yaml`, **Rule** mode, install
`private-provider.yaml` into `private-provider`.

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

python build.py --platform flclash \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --android-apps ../../rules/android-apps.list \
  --policy-domains ../../rules/policy-domains.list \
  --out ../../dist/clash/flclash.yaml

python build.py --platform muse \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --muse-rules ../../rules/muse.list \
  --out ../../dist/clash/clash-backcn-muse.yaml
```

Pass `--dns "$NEXTDNS_DOH_URL"` for Hako/Verge/FlClash/Muse to use the same foreign resolver as
the Shadowrocket profiles. Without it, those builders use Cloudflare DoH. CN names use
`https://223.5.5.5/dns-query`. FlClash and Muse dial each resolver through the matching group.
