# targets/shadowrocket

Emits the Shadowrocket 回国 / backcn config.

- **Base upstream:** Johnshall `sr_backcn_ad.conf`
  (`https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_backcn_ad.conf`),
  fetched fresh each build.
- **Upstream anchors** (as of 2026-07-15): `[General]` holds `dns-server = ...`; `[Rule]`
  starts the rule list with `DOMAIN-SUFFIX,cn,proxy` + `GEOIP,CN,proxy`, followed by the
  ad `Reject` list. If these move, `build.py` fails loudly (`[Rule] not found`) rather
  than mis-inject.

## What build.py does

1. Fetch upstream.
2. Inject `DOMAIN-SUFFIX,<d>,PROXY` for every domain in `rules/redirect-to-cn.list` at the
   **top of `[Rule]`**, inside `>>> rulesv2 ... <<<` markers (idempotent). Top placement
   makes these win over `GEOIP,CN` and the ad `Reject` list.
3. If `--dns` is given, replace the `[General]` `dns-server` with
   `<nextdns>, https://dns.alidns.com/dns-query`.
4. Write `--out`.

## Usage

```sh
python build.py --rules ../../rules/redirect-to-cn.list --out ../../dist/shadowrocket/backcn.conf
# --dns "$NEXTDNS_DOH_URL"     inject 境外 DNS (else keep upstream)
# --upstream-file <path>       build offline from a saved upstream
```

## Device setup (Shadowrocket)

1. Subscribe to the built config URL (Config tab → `+`).
2. Add / select your **China node**; set it to *use config*. `PROXY` rules follow it, so
   no node/proxy is stored in the config.
3. To switch to normal 翻墙 later, subscribe to a normal profile instead (see TODO).
