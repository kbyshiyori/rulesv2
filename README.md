# rulesv2

Version-controlled build pipeline for personal proxy rule configs. Takes a maintained
upstream ruleset, layers local overrides (回国 domain routing, DNS), and publishes a
ready-to-subscribe config per client.

- **Today:** Shadowrocket (macOS/iOS), 回国 / backcn profile.
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
  injected at the **top of `[Rule]`** as `DOMAIN-SUFFIX,<d>,PROXY`, winning over both
  `GEOIP,CN` and the ad `Reject` list. (First case: 小红书, diagnosed from a
  PacketTunnel log on 2026-07-15.)
- **China-domain list, inlined.** To make CN traffic route (and resolve) via the node
  instead of relying on `GEOIP,CN` — which forces a local/境外 DNS lookup and re-leaks CDN
  services — the builder inline-expands felixonmars `accelerated-domains.china.conf`
  (~111k domains) as `DOMAIN-SUFFIX,<d>,PROXY`, placed **below the ad `Reject` list** so
  境内 ad-block still wins. Output is ~5.6 MiB; `--china-mode off` disables it. See
  `targets/shadowrocket/README.md` and TODO (rule-set delivery) for the size trade-off.
- **DNS.** 境外 traffic (DIRECT) uses the local `dns-server` = your **NextDNS** DoH URL
  (`--dns`). 境内 traffic is matched by domain and routed to the China node, so it is
  resolved node-side — set the node's resolver to a CN DNS (Ali `223.5.5.5`); that is the
  vps repo's concern, not this one. This is why CN names never hit NextDNS.

## Layout

```
rules/redirect-to-cn.list      # client-agnostic: domains that must exit via the CN node
targets/shadowrocket/build.py  # emits the Shadowrocket backcn.conf
targets/sing-box/              # planned Android emitter (stub)
.github/workflows/build.yml    # daily cron + on-push build, publish to GitHub Pages
dist/                          # local build output (gitignored)
```

## Build locally

```sh
python targets/shadowrocket/build.py \
  --rules rules/redirect-to-cn.list \
  --out dist/shadowrocket/backcn.conf
# add --dns "$NEXTDNS_DOH_URL" to inject NextDNS
# add --upstream-file <path> to build offline from a saved upstream
```

## Delivery

CI builds on a daily cron (and on push) and publishes `backcn.conf` to **GitHub Pages**:

```
https://kbyshiyori.github.io/rulesv2/backcn.conf
```

Subscribe Shadowrocket to that URL (Config tab → `+`). Pages gives auto-TLS + CDN and no
server to run. The Pages site is public, so the published config — **including the
injected `NEXTDNS_DOH_URL`** — is public by design (see below).

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
