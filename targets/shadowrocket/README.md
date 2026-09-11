# targets/shadowrocket

Emits Shadowrocket 回国 (`backcn`) and 出国 (`cnip`) configs.

- **Base upstream:** Johnshall `sr_backcn_ad.conf`
  (`https://raw.githubusercontent.com/Johnshall/Shadowrocket-ADBlock-Rules-Forever/release/sr_backcn_ad.conf`),
  fetched fresh each build.
- **出国 upstream:** Johnshall `sr_cnip_ad.conf` from the same release branch.
- **China-domain list:** felixonmars `accelerated-domains.china.conf`
  (`https://raw.githubusercontent.com/felixonmars/dnsmasq-china-list/master/accelerated-domains.china.conf`),
  dnsmasq format (`server=/<domain>/<dns>`), ~111k domains.

## What build.py does

1. Fetch upstream.
2. **Local PiKVM exception** — set `dns-direct-system = true`, append
   `pikvm.kbyshiyori.com` to `always-real-ip`, and inject
   `DOMAIN,pikvm.kbyshiyori.com,DIRECT` at the top of `[Rule]`. This makes the home
   router's DNS/Hosts answer win instead of returning a Shadowrocket Fake IP.
3. **direct block** — translate `rules/direct.list` exact IP intents into
   `IP-CIDR,<address>/32,DIRECT,no-resolve` rules at the top of `[Rule]`. These explicit
   exceptions override `GEOIP,CN,PROXY` without changing domain routing.
4. **redirect-to-cn block** — inject every domain from `rules/redirect-to-cn.list` at the
   **top of `[Rule]`** (inside `>>> ... <<<` markers, idempotent). The policy is `PROXY`
   for `backcn` and `DIRECT` for `cnip`, so the same routing intent works from either side
   of the mainland border.
5. **china-domains block** — inline-expand the China list to `DOMAIN-SUFFIX,<d>,PROXY`,
   placed **after the ad `Reject` list and before `FINAL`**. This ordering is deliberate:
   Shadowrocket evaluates domain rules by file order, so putting the broad CN list *below*
   the ~56k `Reject` rules keeps 境内 ad-block winning (e.g. `mobads.baidu.com,Reject`
   before `baidu.com,PROXY`). Domains already covered by redirect-to-cn are dropped.
   - Effect: CN domains route via the node **by name**, so they are resolved node-side
     (set the node's resolver to a CN DNS, e.g. Ali `223.5.5.5`) and never hit the local
     境外 DNS. `GEOIP,CN` becomes a thin fallback for names not in the list.
6. Set the DIRECT-side `[General]` `dns-server`: `--dns` (NextDNS) for `backcn`, or
   `--cn-dns` (default `https://223.5.5.5/dns-query`) for `cnip`.
7. Write `--out`.

The broad inlined China list defaults to on for `backcn` and off for `cnip`, whose
maintained upstream already implements the usual CN-direct split. `--china-mode` can
override either default.

## Size / performance

Full inline output is **~5.6 MiB / ~168k lines**. That is the cost of a self-contained,
offline-capable config. If Shadowrocket load/matching gets sluggish, switch the broad list
to a remote rule set instead of inlining — see repo TODO ("rule-set delivery"). Quick
local escape hatch: `--china-mode off` builds without the broad list (keeps redirect-to-cn
+ upstream GEOIP only).

## Usage

```sh
python build.py \
  --rules ../../rules/redirect-to-cn.list \
  --direct-rules ../../rules/direct.list \
  --out ../../dist/shadowrocket/sr-backcn.conf
# --dns "$NEXTDNS_DOH_URL"        backcn DIRECT DNS (else keep upstream)
# --cn-dns <url>                  cnip DIRECT DNS (default: AliDNS DoH)
# --china-mode off                skip the broad China list
# --upstream-file / --china-list-file <path>   build offline from saved copies
# --profile cnip                 build the 出国 profile (default: backcn)
```

## Device setup (Shadowrocket)

1. Subscribe to the built config URL (Config tab → `+`):
   `https://kbyshiyori.github.io/rulesv2/sr-backcn.conf` (published by CI on each build).
2. Add / select your **China node**; set it to *use config*. `PROXY` rules follow it, so
   no node/proxy is stored in the config.
3. Set the China node's own resolver to a CN DNS (e.g. Ali `223.5.5.5`) so the CN domains
   routed to it resolve domestically. 境外/DIRECT traffic uses the config's `dns-server`
   (NextDNS).

For `sr-cnip.conf`, select an overseas node instead; CN rules remain direct and the final
fallback follows the selected proxy node. The profile's DIRECT domains use
`https://223.5.5.5/dns-query`; configure the overseas proxy server to use NextDNS for its
PROXY-side domain resolution.

Shadowrocket's `proxy-dns-server` is not a PROXY-traffic DNS setting: it resolves the
proxy node's own hostname. It cannot replace the required node-side resolver setup.
