# targets/sing-box  (planned — not built yet)

Android emitter. Will consume the same [`rules/redirect-to-cn.list`](../../rules/redirect-to-cn.list)
intent and emit sing-box `route` rules that send those domains to the China outbound,
mirroring the Shadowrocket backcn behavior.

Open questions to settle when implementing (see repo TODO):

- Which maintained 回国 sing-box base to start from (or hand-write a minimal one).
- How the China outbound is provided without committing secrets (device-local outbound,
  or injected from a CI secret at deploy — same rule as Shadowrocket: no secrets in git).
- 境内 ad-block source (reuse a rule-set, or the Johnshall/GMOogway reject list converted).

Until then this folder is intentionally empty except this note.
