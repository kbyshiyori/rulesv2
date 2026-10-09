# Private subscription agent rules

Read `README.md` here before changing or deploying subscriptions.

- Cloudflare's per-device JSON CONFIG variable is authoritative. Never use iCloud or an old local
  node file as the source for a routine update.
- Use `python3.12 subscriptions/publish.py --device <device> --pull`, edit the ignored
  `dist/subscriptions/<device>-provider.yaml`, then `--check` and `--publish`.
- For Worker code updates use `--deploy-code`; it preserves current cloud nodes and
  does not read a stale node working copy.
- Respect baseline conflicts and local uncommitted edits. The check is optimistic,
  not atomic: one publisher at a time. Do not add an automatic force/rotation path.
- Credentials are in root `.env.cloudflare` and `.env.subscriptions`, not this source
  directory. Never print secrets, complete provider content, or private subscription
  URLs. Missing device tokens require recovery of the existing token.
- Public rules come from the fixed rulesv2 Pages URL. Full subscriptions use
  `config.yaml`; `provider.yaml` contains nodes only. Preserve Android IPv6-off policy.
- Node YAML validation needs Ruby/Psych; Python uses stdlib. Run publisher tests for
  publisher changes, Worker tests for Worker changes. Verify after deployment.
- Deployment failures may occur after upload: use `--verify` to resolve the state
  before retrying. Document actual live verification and remaining client limits.
- Android, iPhone (Clash backcn), and MacBook (Muse) are deployed. Choose the device
  explicitly; preserve other device bindings. Only use `--bootstrap --provider` for
  a user-requested first migration, never to overwrite an existing cloud device.
  Windows and AVP have not been migrated.

- The owner chose account-visible JSON variables rather than Secret bindings. Keep
  tokenHash unchanged when editing provider. Never put Cloudflare API credentials
  in the runtime bindings. Dashboard edits are cloud updates: pull a fresh baseline.
- Publish CONFIG as `type: json`, preserve other device bindings via inherit. Worker
  accepts native JSON objects and legacy string bindings during migration.

- Shared API credentials are in Google Drive `Agents/cloudflare/.env.cloudflare`
  under the plugin account larry@kbyshiyori.com. See README for verified folder/file
  links. The owner authorizes agents to update this project's shared credential
  files in place, preserving IDs, parents and permissions. Do not create duplicate
  files or widen sharing. Read fresh content, merge, and verify the write.
- `.env.subscriptions` is not currently uploaded to Drive. Do not claim device
  tokens are available there. When the owner requests sharing that registry, keep
  device additions/removals synchronized in the original Drive file and local copy.
- Device changes need Worker/publisher mappings, deployment and live verification;
  editing Drive credentials alone does not change subscriptions. There is no delete
  CLI. Remove only a user-requested device and preserve all others; see README.
