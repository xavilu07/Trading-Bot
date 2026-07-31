# Canonical runtime identity

The scheduler builds one immutable `runtime_identity.v1` contract after loading
effective settings and before acquiring its process lock. The same contract is
used by the startup log, scheduler lock, initial and subsequent heartbeats, and
new signal/trade metadata.

Production configuration uses these canonical environment names:

- `GIT_COMMIT_SHA`: optional assertion against the checkout's `HEAD`.
- `DEPLOYMENT_ID`: required, unique deployment label.
- `SELECTED_ENGINE`: optional assertion (`legacy` or `modular`) against
  `USE_MODULAR_DECISION_ENGINE`.
- `STRATEGY_VERSION`: optional assertion against
  `LiquiditySweepMTFV1.strategy_version`.
- `POLICY_VERSION`: optional assertion against
  `public_safety_policy.POLICY_VERSION`.
- `EXPERIMENT_ID`: effective experiment label; defaults to `none`.
- `CONFIG_HASH`: optional assertion against the computed hash.

There are no legacy aliases. Empty optional assertions cause the code-derived
effective value to be used; a non-empty mismatch aborts before lock acquisition
and before any healthy heartbeat is written. `selected_engine`,
`strategy_version`, and `policy_version` can never silently become `unknown`.
`RUNTIME_ALLOW_UNKNOWN_IDENTITY=true` is accepted only in development/test and
does not relax those three code identities.

## Deterministic config hash

The hash is SHA-256 over compact, key-sorted JSON. Values are normalized
recursively; paths become strings and floats use a stable representation. Only
the allowlisted effective settings in `CONFIG_HASH_FIELDS` participate:
strategy/policy/engine/experiment identity, timeframes, feature modes and
trading cost assumptions.

Secrets, credentials, `CONFIG_HASH` itself, deployment ID, PID, timestamps,
checkout path, and commit SHA are excluded. This makes the hash stable between
equivalent processes while preventing secret disclosure or recursive hashes.

## Lock and heartbeat schema

Both artifacts contain the identical identity fields:

`runtime_identity_schema`, `git_commit_sha`, `deployment_id`, `config_hash`,
`selected_engine`, `strategy_version`, `policy_version`, `experiment_id`,
`runtime_flags`, `pid`, `started_at`, and `release_cwd`.

The heartbeat adds cycle state such as `cycle_number`, `status`, timestamps,
duration and `last_error`. Identity is applied last on every update, so cycle
state cannot overwrite or drop it.
