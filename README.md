# rulesv2

Version-controlled build pipeline for personal proxy rule configs. Takes a maintained
upstream ruleset, layers local overrides (回国 domain routing, DNS), and publishes a
ready-to-subscribe routing profile per client.

- **Today:** Shadowrocket, Clash/Hako (macOS/iOS), and Clash Verge Rev (Windows), each with 回国
  (`backcn`) and 出国 (`cnip`) profiles.
- **Planned:** sing-box config for Android (same `rules/` intent, different emitter).

> This repo is worked on mainly by coding agents (Claude / Codex); the owner mainly
> reviews. Read [`AGENTS.md`](AGENTS.md) before making changes. Open tasks in
> [`TODO.md`](TODO.md).

## What "回国 / backcn" means here

Egress split for someone **outside** mainland China who wants mainland services to see a
China IP:

| Traffic            | Egress            |
|--------------------|-------------------|
| Mainland-CN dest   | **PROXY** (China node) |
| Everything else    | **DIRECT**        |

In Shadowrocket you pick the China node and set it to *use config*; the `PROXY` policy
follows the selected node, so **the built config carries no node/proxy secrets**.

## What "出国 / cnip" means here

For someone **inside** mainland China, mainland destinations stay `DIRECT` and everything
else uses `PROXY` through an overseas node. The explicit `redirect-to-cn` domains also
become `DIRECT` in this direction.

Clash/Hako profiles use a private file Proxy Provider named `private-provider`. Import a
device-specific `private-provider.yaml` containing only `proxies:` into each profile's
Proxy Sources. The public rules files contain no nodes or credentials; devices can share
the same file name while using different WireGuard client keys and addresses.

## Design decisions

- **Base = Johnshall `sr_backcn_ad.conf`.** It is the only maintained upstream with a
  ready 回国 profile *and* ad-block. (GMOogway's repo is modular but has no backcn
  profile — normal-翻墙 oriented — so it is not a drop-in here. Its reject module is a
  candidate future ad source; see TODO.)
- **Ad-block policy:** keep the `_ad` upstream. 境内 ad-block (the `Reject` list) is
  wanted; 境外 ad-block is already handled by NextDNS, so foreign reject entries are
  harmless redundancy.
- **`redirect-to-cn` override.** `GEOIP,CN` mis-routes services hosted on global CDNs
  (Akamai / Tencent EdgeOne overseas) — they resolve to overseas edge IPs and leak to
  DIRECT. So domains in [`rules/redirect-to-cn.list`](rules/redirect-to-cn.list) are
  injected at the top with the route that exits in China: `PROXY` in `backcn`, `DIRECT`
  in `cnip`. (First case: 小红书, diagnosed from a PacketTunnel log on 2026-07-15.)
- **原神 routes by app/process, not by server IP.** The Clash Verge Rev profile includes
  the `YuanShen.exe` process rule and an independent `原神` node selector. On other
  clients, configure app-based routing in the client itself; those device-specific
  settings are not represented in this repository.
- **China-domain list, inlined.** To make CN traffic route (and resolve) via the node
  instead of relying on `GEOIP,CN` — which forces a local/境外 DNS lookup and re-leaks CDN
  services — the builder inline-expands felixonmars `accelerated-domains.china.conf`
  (~111k domains) as `DOMAIN-SUFFIX,<d>,PROXY`, placed **below the ad `Reject` list** so
  境内 ad-block still wins. Output is ~5.6 MiB; `--china-mode off` disables it. See
  `targets/shadowrocket/README.md` and TODO (rule-set delivery) for the size trade-off.
- **Clash uses MRS providers.** The native Clash app runs inside Apple's memory-limited
  Network Extension, so the Clash profiles consume MetaCubeX CN-domain, CN-IP, and ad
  rule sets in compiled MRS form instead of inlining ~111k text rules.
- **YouTube has an independent selectable exit.** Both clients route a maintained
  YouTube rule set to the `YouTube` policy. Clash emits that select group; Shadowrocket
  references the user's app-global group without defining it in the published conf.
  Node credentials remain local/private.
- **DNS follows the exit direction.** Clash expresses the full split in YAML. Shadowrocket
  applies `dns-server` only to `DIRECT` domains, while `PROXY` domains resolve on the
  selected proxy server; the node-side resolver must therefore match the second column.

  | Profile | `DIRECT` DNS | `PROXY` DNS |
  |---------|--------------|-------------|
  | `backcn` | NextDNS | `https://223.5.5.5/dns-query` |
  | `cnip` | `https://223.5.5.5/dns-query` | NextDNS |

## Layout

```
rules/redirect-to-cn.list      # client-agnostic: domains that must exit via the CN node
rules/direct.list              # client-agnostic: optional local DIRECT exceptions
targets/shadowrocket/build.py  # emits the Shadowrocket sr-backcn.conf
targets/clash/build.py         # emits Clash/Hako and Clash Verge Rev YAML profiles
targets/sing-box/              # planned Android emitter (stub)
.github/workflows/build.yml    # daily cron + on-push build, publish to GitHub Pages
dist/                          # local build output (gitignored)
```

## Build locally

```sh
python targets/shadowrocket/build.py \
  --rules rules/redirect-to-cn.list \
  --direct-rules rules/direct.list \
  --out dist/shadowrocket/sr-backcn.conf
# add --dns "$NEXTDNS_DOH_URL" to inject NextDNS
# add --upstream-file <path> to build offline from a saved upstream

# Shadowrocket 出国
python targets/shadowrocket/build.py --profile cnip \
  --rules rules/redirect-to-cn.list \
  --direct-rules rules/direct.list \
  --out dist/shadowrocket/sr-cnip.conf

# Clash/Hako: change --profile between backcn and cnip
python targets/clash/build.py --profile backcn \
  --rules rules/redirect-to-cn.list \
  --direct-rules rules/direct.list \
  --out dist/clash/clash-backcn.yaml

# Clash Verge Rev: same rules, plus Windows executable routing
python targets/clash/build.py --platform verge --profile backcn \
  --rules rules/redirect-to-cn.list \
  --direct-rules rules/direct.list \
  --out dist/clash/clash-verge-backcn.yaml
```

## Delivery

CI builds on a daily cron (and on push) and publishes six files to **GitHub Pages**:

- `https://kbyshiyori.github.io/rulesv2/sr-backcn.conf`
- `https://kbyshiyori.github.io/rulesv2/sr-cnip.conf`
- `https://kbyshiyori.github.io/rulesv2/clash-backcn.yaml`
- `https://kbyshiyori.github.io/rulesv2/clash-cnip.yaml`
- `https://kbyshiyori.github.io/rulesv2/clash-verge-backcn.yaml`
- `https://kbyshiyori.github.io/rulesv2/clash-verge-cnip.yaml`

Subscribe the matching client to its URL. For Clash, import a device-specific
`private-provider.yaml` under the profile's **Proxy Sources**; keep that file private.
Pages gives auto-TLS + CDN and no server to run. The Pages site is public, so the published
config — **including the injected `NEXTDNS_DOH_URL`** — is public by design (see below).

## Secrets

The source tree is secret-free. The one build input is a GitHub Actions repo secret (name
mirrors [`.env.example`](.env.example)):

- `NEXTDNS_DOH_URL` — 境外 DNS DoH URL (embeds a NextDNS config id). It is injected into
  the built config at build time. Since the built config is served publicly on Pages, this
  URL is **public by design** — accepted because it only selects an ad-block config; a
  stranger using it just shares this config's blocklists and counts against its NextDNS
  query quota. Rotate the config id if that ever becomes a problem. Keep the URL out of the
  *source tree* regardless; set it only as the Actions secret.

Publishing is intentional here — there is no private/"unguessable path" delivery anymore.
