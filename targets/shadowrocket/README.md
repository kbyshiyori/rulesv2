# targets/shadowrocket

Emits the Shadowrocket 回国 / backcn config.

- **Base upstream:** Johnshall `sr_backcn_ad.conf`
  (`https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_backcn_ad.conf`),
  fetched fresh each build.
- **China-domain list:** felixonmars `accelerated-domains.china.conf`
  (`https://raw.githubusercontent.com/felixonmars/dnsmasq-china-list/master/accelerated-domains.china.conf`),
  dnsmasq format (`server=/<domain>/<dns>`), ~111k domains.

## What build.py does

1. Fetch upstream.
2. **redirect-to-cn block** — inject `DOMAIN-SUFFIX,<d>,PROXY` for every domain in
   `rules/redirect-to-cn.list` at the **top of `[Rule]`** (inside `>>> ... <<<` markers,
   idempotent). Top placement wins over `GEOIP,CN` and the ad `Reject` list — these are the
   services that must work fully, and they are not ad domains.
3. **china-domains block** — inline-expand the China list to `DOMAIN-SUFFIX,<d>,PROXY`,
   placed **after the ad `Reject` list and before `FINAL`**. This ordering is deliberate:
   Shadowrocket evaluates domain rules by file order, so putting the broad CN list *below*
   the ~56k `Reject` rules keeps 境内 ad-block winning (e.g. `mobads.baidu.com,Reject`
   before `baidu.com,PROXY`). Domains already covered by redirect-to-cn are dropped.
   - Effect: CN domains route via the node **by name**, so they are resolved node-side
     (set the node's resolver to a CN DNS, e.g. Ali `223.5.5.5`) and never hit the local
     境外 DNS. `GEOIP,CN` becomes a thin fallback for names not in the list.
4. If `--dns` is given, replace the `[General]` `dns-server`.
5. Write `--out`.

## Size / performance

Full inline output is **~5.6 MiB / ~168k lines**. That is the cost of a self-contained,
offline-capable config. If Shadowrocket load/matching gets sluggish, switch the broad list
to a remote rule set instead of inlining — see repo TODO ("rule-set delivery"). Quick
local escape hatch: `--china-mode off` builds without the broad list (keeps redirect-to-cn
+ upstream GEOIP only).

## Usage

```sh
python build.py --rules ../../rules/redirect-to-cn.list --out ../../dist/shadowrocket/sr-backcn.conf
# --dns "$NEXTDNS_DOH_URL"        inject 境外 DNS (else keep upstream)
# --china-mode off                skip the broad China list
# --upstream-file / --china-list-file <path>   build offline from saved copies
```

## Device setup (Shadowrocket)

1. Subscribe to the built config URL (Config tab → `+`):
   `https://kbyshiyori.github.io/rulesv2/sr-backcn.conf` (published by CI on each build).
2. Add / select your **China node**; set it to *use config*. `PROXY` rules follow it, so
   no node/proxy is stored in the config.
3. Set the China node's own resolver to a CN DNS (e.g. Ali `223.5.5.5`) so the CN domains
   routed to it resolve domestically. 境外/DIRECT traffic uses the config's `dns-server`
   (NextDNS).
