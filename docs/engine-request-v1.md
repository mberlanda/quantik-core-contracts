# Engine Request v1

Status: **registered** — schema `schemas/engine-request-v1.json`
(JSON Schema 2020-12), fixtures `fixtures/engine-request/*.jsonl`.

`engine-request.v1` is the JSON body a client POSTs to ask an engine service to
choose one move. It captures the format already spoken in production; it does
not redesign it. Pair contract: [`engine-response-v1.md`](engine-response-v1.md).

## Fields

```text
schema                 "engine-request.v1"            required
qfen                   string, qfen.v1                 required
side_to_move           0 or 1                          required
legal_action_indices   array of 0..=63                 required
config                 object                          optional
```

`config` fields are each optional: `max_depth`, `time_limit_ms`, `iterations`,
`beam_width`, `rollouts`, `seed` (non-negative integers). An engine ignores
fields it has no use for. The top level is closed
(`additionalProperties: false`): an unknown field is a validation failure.

`legal_action_indices` uses `action_index = shape * 16 + position`
(`action-index.v1`, 64 slots). Servers verify it against the position and
answer 422 if it disagrees with `quantik-core`.

## Implementations

- `quantik-api-rust/src/lib.rs` — `MoveRequest` / `SearchConfig` /
  `validate_request`; route `POST /v1/move/{engine}`, engines `minimax`,
  `mcts`, `beam`.
- `quantik-qfen-visualizer/src/engines.js` — `createRemoteEngine`; sends the
  four required fields and never sends `config`.
- `quantik-models-py/src/quantik_models/play/service.py` — the play service
  (`POST /api/move/{opponent_id}`); accepts `config.seed`.

## Rename migration (initiative QW-019, decision D3)

The registered name is the bare `engine-request.v1`, like every other contract.
Before registration all three implementations used `quantik.engine-request.v1`.

- For one minor cycle servers accept both spellings on input.
- The prefixed spelling is rejected starting at the next minor.

The fixtures carry the bare name. They were captured from the real
implementations while those still used the prefixed name, and only the `schema`
value was rewritten to the bare name.

## Fixtures

`fixtures/engine-request/engine-request-v1-captured.jsonl`: requests built by
the visualizer's `createRemoteEngine` (no `config`) for an empty board and a
three-ply position, plus the same position with `config` variants that were
accepted by the Rust API and the Python play service.
