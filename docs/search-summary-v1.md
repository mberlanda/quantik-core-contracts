# Search Summary v1

Status: **proposed, not registered**.

`search-summary.v1` is the proposed root-search diagnostic row for completed
engine searches. It is intentionally separate from `observation.v1`:

- `observation.v1` is the implemented training and analytics row contract.
- `search-summary.v1` is for reproducibility and search diagnostics.
- Full per-edge or per-simulation traces are out of scope for v1 because they
  can grow without a stable bound.

## Intended Row Shape

The current candidate is one JSON/Parquet row per completed root search:

```text
schema
contract_version
run_id
row_id
position_key
ply
side_to_move
bitboards
qfen
legal_action_mask
engine_kind
engine_version
engine_checkpoint
config_label
search_depth
rollouts
beam_width
node_budget
time_budget_ms
seed
root_value
policy_visits[64]
root_q_values[64]
principal_variation
expanded_nodes
transposition_hits
terminal_hits
tablebase_hits
elapsed_ms
```

The shape above is a design target, not a registered schema. Producers must not
emit artifacts labeled `search-summary.v1` until the contract is listed in
`contracts.json`.

## Registration Gates

Before registration, both Rust and Python implementations must expose the same
observable semantics for the diagnostic counters below.

`expanded_nodes` must name the same unit of work across MCTS, beam search, and
minimax. Existing proxies such as allocated nodes, inserted beam survivors, or
negamax calls are useful implementation metrics but are not yet a shared
contract definition.

`transposition_hits` must distinguish an actual transposition/cache reuse from
beam canonical deduplication. If a stack reports canonical dedup hits, that
counter needs its own field or a documented mapping before registration.

`terminal_hits` must define whether it counts terminal nodes reached during
tree expansion, rollout/simulation terminal outcomes, minimax terminal leaves,
or all of them. The definition must be portable across stacks.

`tablebase_hits` must be `0` for engines that do not use a tablebase or compact
probe shortcut. If a future probe/tablebase is introduced, a hit must mean a
value/policy result was obtained from that artifact instead of normal search.

`policy_visits[64]` must be a real action-indexed root policy mass. MCTS can
produce visit counts when root move identity is preserved; beam multiplicity is
not the same thing as visits unless the contract explicitly allows engine-kind
specific policy mass semantics.

`root_q_values[64]` must state the value perspective and scale. Minimax scores
may use mate-distance magnitudes, while MCTS and beam values are often
normalized to `[-1, 1]` or `[0, 1]`.

`principal_variation` must use compact action identity and preserve order from
the root. Engines that cannot produce a deeper PV should either omit it under a
registered nullable rule or wait to emit the contract.

## Current Implementation State

As of release `1.1.0`, `search-summary.v1` is not registered.

The Rust telemetry surface is implemented
([quantik-core-rust#33](https://github.com/mberlanda/quantik-core-rust/pull/33)):

- A shared `SearchTelemetry` struct is produced by MCTS, beam search, and
  minimax, with **event-based counter semantics**: each counter is defined by
  a search event (successor set computed, successor state constructed, cached
  result reused, duplicate merged without result reuse, state determined
  terminal during tree search), and every engine increments it at exactly the
  code path where that event occurs. This satisfies the `expanded_nodes`
  shared-unit gate above.
- `transposition_hits` (result/subtree reuse) is a separate counter from
  `canonical_dedup_hits` (duplicate merged, nothing reused), so beam and
  minimax dedup can never masquerade as transposition reuse. This satisfies
  the transposition-vs-dedup gate above.
- `terminal_hits` counts states determined terminal during tree search only;
  rollout/simulation outcomes are excluded in every engine, giving the
  counter one portable definition. `tablebase_hits` is always `0`.
- Root values and per-move Q-values live in `[-1, 1]`, positive good for the
  root player, with `|v| = 1.0` reserved for proven results; sampled and
  heuristic estimates are clamped strictly inside the interval. Policy mass
  is declared per engine kind (`visits` for MCTS, `multiplicity` for beam,
  `none` for minimax), addressing the `policy_visits`/`root_q_values` gates.
- A `root_identity_preserved` flag marks rows whose root-move statistics may
  have collapsed under transposition/canonical merging; the draft exporter
  skips such rows.
- A draft JSONL exporter emits the intended row shape under the schema label
  `search-summary.v1-draft` only. Nothing emits `search-summary.v1` until
  this contract is registered.

The normative counter and value semantics live in the Rust repository's
`docs/search-telemetry.md` and the `search_telemetry` module documentation;
the Python mirror must match them observably.

Neither stack has a tablebase/probe API that can produce `tablebase_hits > 0`.

The next implementation step is the Python telemetry mirror in
`quantik-core-py`, then registration of this contract only after parity tests
prove the same row can be produced and consumed across stacks.
