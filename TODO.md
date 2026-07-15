# TODO

Handoff state (2026-07-15): repo scaffolded. The Shadowrocket builder works end-to-end
locally and in CI (build + artifact). Delivery to yyz and NextDNS injection are wired but
**inert until secrets are set**.

## Next up

- [ ] **Push the initial commit.** Scaffold is committed locally on `main`, not pushed.
      `git push -u origin main`.
- [ ] **Set GitHub Actions secrets** (repo → Settings → Secrets and variables → Actions):
  - [ ] `NEXTDNS_DOH_URL` — from NextDNS setup page (DNS-over-HTTPS URL).
  - [ ] `YYZ_SSH_KEY` — a **deploy-only** private key; add its public key to
        `~/.ssh/authorized_keys` for the target user on yyz.
  - [ ] `YYZ_HOST` (REDACTED), `YYZ_USER`, `YYZ_DEST` (web root path),
        `YYZ_KNOWN_HOSTS` (`ssh-keyscan yyz`).
- [ ] **Stand up HTTPS delivery on yyz.** Caddy (auto-TLS) serving the deployed conf at an
      unguessable path; needs a domain. Then subscribe Shadowrocket to that URL. Consider
      mirroring to the China node for faster in-CN fetches.
- [ ] **Verify the deployed conf on device**: re-subscribe, restart 小红书, confirm
      `edith/www/fe-static/...xiaohongshu.com|xhscdn.com` now hit the injected PROXY rule
      (egress `240.0.0.x`), not `FINAL,DIRECT`. See the vps repo conversation / log.

## Backlog

- [ ] **rule-set delivery for the China list (size).** Inline output is ~5.6 MiB / ~168k
      lines. If Shadowrocket load/matching gets sluggish, host the expanded China list on
      yyz (or convert felixonmars) and reference it as a single `RULE-SET,<url>,PROXY`
      instead of inlining. The builder already has the seam (`--china-mode`); add a
      `rule-set` mode that emits the RULE-SET line + publishes the list file.
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
