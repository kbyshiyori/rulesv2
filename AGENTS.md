# Operating rules for agents

You (Claude / Codex) do most of the work in this repo; the owner reviews. Keep changes
small, reviewable, and secret-free.

## Golden rules

- **Never commit secrets.** No NextDNS DoH URL (embeds a config id), no node keys, no SSH
  keys, no `.env`. Secrets live only as GitHub Actions secrets / a local gitignored
  `.env`. `dist/` is gitignored because a built file can carry the injected NextDNS URL.
- **The built config carries no proxy/node.** Routing to the China node is done by the
  user selecting a node in Shadowrocket + "use config"; rules just say `PROXY`. Do not add
  a `[Proxy]` section with credentials.
- **`rules/` is client-agnostic.** Put routing *intent* there (e.g. domains that must exit
  via the CN node). Each `targets/<client>/` emitter translates intent into that client's
  syntax. When adding a client, reuse `rules/`, don't fork the domain lists.
- **Keep the pipeline idempotent.** The Shadowrocket builder wraps its injected block in
  `>>> rulesv2 ... <<<` markers and strips any prior block before re-injecting, so
  re-running (or upstream format drift) never double-injects. Preserve that.
- **Prefer editing the builder over hand-editing output.** `dist/` is disposable.

## Conventions

- Python 3.12, stdlib only (no third-party deps) so CI needs no install step.
- Upstream is **fetched at build time**, never vendored, so we always track the daily
  rebuild. Use `--upstream-file` only for offline testing.
- One emitter per client under `targets/<client>/`; document the base upstream + injection
  points in that folder's `README.md`.

## How to verify a change

```sh
python targets/shadowrocket/build.py --rules rules/redirect-to-cn.list \
  --out /tmp/backcn.conf
grep -n 'rulesv2 redirect-to-cn' /tmp/backcn.conf      # markers present once
grep -n 'DOMAIN-SUFFIX,xiaohongshu.com,PROXY' /tmp/backcn.conf   # rules injected
grep -n '^\[Rule\]' /tmp/backcn.conf                   # injected right after [Rule]
```

For a DNS change also pass `--dns 'https://dns.nextdns.io/PLACEHOLDER'` and confirm the
`dns-server` line under `[General]` is replaced (and only there).

## Adding the sing-box (Android) target

Consume `rules/redirect-to-cn.list`, emit sing-box `route` rules pointing those domains
at the China outbound. Pick a maintained 回国 sing-box base, document it in
`targets/sing-box/README.md`, and add a job to `.github/workflows/build.yml`. Keep it
secret-free the same way (outbound/node config stays on the device or is injected from a
secret at deploy).

## Related infra

Delivery host is **yyz** (`ssh yyz`, Oracle aarch64 ops host) from the owner's `vps`
repo. That repo owns node/DNS config on the China relay; this repo only owns rule/config
generation.
