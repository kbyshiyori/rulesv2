# TODO

Handoff state (2026-07-15): repo pushed to `main`. The Shadowrocket builder works
end-to-end locally and in CI, which now **publishes the built config to GitHub Pages**
(delivery pivoted off the old yyz/rsync path). NextDNS injection is wired via the
`NEXTDNS_DOH_URL` secret.

## Next up

- [ ] **Make the repo public + enable Pages.** Settings → General → make public. The
      workflow uses `actions/configure-pages@v5` with `enablement: true`, so the first run
      after going public turns Pages on (Source: GitHub Actions) automatically — no manual
      Pages setting needed. If enablement is ever blocked, set Settings → Pages → Source:
      GitHub Actions by hand.
- [x] **Set GitHub Actions secret** — done 2026-07-15: `NEXTDNS_DOH_URL`. (The former
      `YYZ_*` SSH/rsync secrets are no longer used and can be deleted from repo settings.)
- [ ] **Confirm the published URL.** After a green run, `curl -sI
      https://kbyshiyori.github.io/rulesv2/backcn.conf` returns 200 and the body starts
      with the Johnshall header + injected `dns-server`/redirect-to-cn block.
- [ ] **Verify on device**: subscribe Shadowrocket to the Pages URL, restart 小红书, confirm
      `edith/www/fe-static/...xiaohongshu.com|xhscdn.com` now hit the injected PROXY rule
      (egress `240.0.0.x`), not `FINAL,DIRECT`. See the vps repo conversation / log.

## Backlog

- [ ] **rule-set delivery for the China list (size).** Inline output is ~5.6 MiB / ~168k
      lines. If Shadowrocket load/matching gets sluggish, publish the expanded China list
      as a second Pages file (or convert felixonmars) and reference it as a single
      `RULE-SET,<url>,PROXY` instead of inlining. The builder already has the seam
      (`--china-mode`); add a `rule-set` mode that emits the RULE-SET line + publishes the
      list file alongside `backcn.conf`.
- [ ] **sing-box (Android) target.** New emitter under `targets/sing-box/` consuming
      `rules/redirect-to-cn.list` (and the same China list); pick a maintained 回国 sing-box
      base; add a CI job.
- [ ] **Grow `redirect-to-cn.list`** as more CN services leak via overseas CDN (diagnose
      from PacketTunnel logs, same method as 小红书).
- [ ] **Optional: also build the normal 翻墙 profile** (`sr_cnip_ad.conf`) so the owner can
      toggle backcn <-> normal by switching subscriptions.
- [ ] **Evaluate GMOogway reject module** as a higher-quality 境内 ad source layered on top
      of the Johnshall base.
- [ ] **CI hardening:** fail the build if the injected block is missing/duplicated or if
      `[Rule]`/`[General]` anchors disappear (upstream format drift).
