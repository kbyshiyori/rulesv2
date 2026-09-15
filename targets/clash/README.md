# targets/clash

Emits two minimal mihomo YAML profiles for the native **Clash for Apple Platforms**
(Hako) on iOS and macOS:

- `clash-backcn.yaml`: mainland-China destinations use `PROXY`; everything else is
  `DIRECT`.
- `clash-cnip.yaml`: mainland-China destinations are `DIRECT`; everything else uses
  `PROXY`.

The profiles use MetaCubeX `cn.mrs`, `cn-ip.mrs`, `youtube.mrs`, and
`category-ads-all.mrs` rule
providers. MRS is intentional: large YAML/text rule sets can exceed the memory available
to an iOS Network Extension.

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
```

Pass `--dns "$NEXTDNS_DOH_URL"` to use the same foreign resolver as the Shadowrocket
profiles. Without it, the builder uses Cloudflare DoH. CN names use
`https://223.5.5.5/dns-query`. Resolver traffic follows its matching exit explicitly:

- `backcn`: NextDNS `#DIRECT`; AliDNS `#PROXY`.
- `cnip`: AliDNS `#DIRECT`; NextDNS `#PROXY`.
