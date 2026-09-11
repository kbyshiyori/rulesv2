# targets/clash

Emits two minimal mihomo YAML profiles for the native **Clash for Apple Platforms**
(Hako) on iOS and macOS:

- `clash-backcn.yaml`: mainland-China destinations use `PROXY`; everything else is
  `DIRECT`.
- `clash-cnip.yaml`: mainland-China destinations are `DIRECT`; everything else uses
  `PROXY`.

The profiles use MetaCubeX `cn.mrs`, `cn-ip.mrs`, and `category-ads-all.mrs` rule
providers. MRS is intentional: large YAML/text rule sets can exceed the memory available
to an iOS Network Extension.

## Private node setup

Published profiles contain no node, credential, or subscription token. After importing a
profile, open **Edit Source** and replace this value:

```yaml
url: "https://example.invalid/replace-with-private-mihomo-profile.yaml"
```

with the HTTPS URL of your private Clash/mihomo subscription. Keep the quotation marks.
For `backcn`, that provider must contain a mainland-China node; for `cnip`, it should
contain the overseas nodes you want to use. The source URL is a secret: never commit it or
publish the edited profile. Until a working provider is configured, the `PROXY` group
falls back to `REJECT` so traffic cannot silently leak through `DIRECT`.

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
