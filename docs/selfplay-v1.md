# Self-Play v1

`selfplay.v1` defines one logical supervised training observation emitted from
a self-play game. It is independent of the physical storage used for large
datasets.

The canonical fixture representation is JSONL: one JSON object per line.

## Required Fields

```json
{
  "schema": "selfplay.v1",
  "contract_version": "1.1.0",
  "game_id": 0,
  "ply": 0,
  "qfen": "..../..../..../....",
  "side_to_move": 0,
  "policy": [
    { "shape": 0, "position": 0, "visits": 10 }
  ],
  "value": 1.0
}
```

Field rules:

- `schema` must be `selfplay.v1`.
- `contract_version`, when present, must match `contracts.json.release_version`.
- `game_id` is a non-negative integer.
- `ply` is a non-negative integer.
- `qfen` must satisfy `qfen.v1`.
- `side_to_move` must be `0` or `1`.
- `policy` must contain at least one legal action.
- `shape` must be in `0..3`.
- `position` must be in `0..15`.
- `visits` must be a positive integer.
- `value` must be exactly `1.0` or `-1.0`.

`value` is from the perspective of `side_to_move` at the row position. Quantik
has no draws, so `0.0` is invalid.

## Policy Encoding

JSONL uses sparse policy visits:

```text
policy = list[{shape, position, visits}]
```

ML vectors use dense 64-action shape-major order:

```text
action_index = shape * 16 + position
```

When converting sparse visits to a dense policy distribution:

```text
policy_distribution[action_index] = visits / sum(visits)
```

All omitted actions have probability `0.0`.

## Large Dataset Encoding

For Arrow/Parquet, use the distinct physical contract
`arrow-parquet-selfplay.v1`. It carries the same row semantics as
`selfplay.v1`, but stores training-friendly physical columns. The key
transformed columns are:

```text
logical_schema: utf8 = "selfplay.v1"
contract_version: utf8
bitboards: fixed_size_list<uint16,8>
policy_visits: fixed_size_list<uint32,64>
value: int8
```

The physical schema also carries `game_id`, `ply`, `side_to_move`, and
optional `qfen` from the logical row. For the complete column specification see
`schemas/arrow-parquet-selfplay-v1.json` and `docs/storage-representations.md`.

Physical rows derive `bitboards` from `qfen`, convert sparse `policy` visits to
dense `policy_visits[64]`, and store `value` as integer `-1` or `1` with the
same side-to-move perspective. The top-level physical schema remains
`arrow-parquet-selfplay.v1`; the row-level logical schema remains
`selfplay.v1`.

Parquet writers should also store file/table key-value metadata:

```text
physical_schema: arrow-parquet-selfplay.v1
logical_schema: selfplay.v1
logical_contract: selfplay.v1
contracts_release: contracts.json.release_version
contract_version: contracts.json.release_version
```

These metadata fields identify the stored bytes and release provenance. They do
not change `selfplay.v1`: the logical contract remains the JSONL row semantics,
while `arrow-parquet-selfplay.v1` is the physical bulk-storage representation.

Dense visits avoid ragged nested arrays during training and make the action
index contract explicit. JSONL fixtures should continue to use sparse policy
lists for readability and contract review.

## Compatibility Rules

Readers must reject:

- Unknown required schema versions.
- Invalid QFEN.
- Side-to-move mismatch.
- Illegal policy actions.
- `value = 0.0`.
- Negative ids, plies, positions, shapes, or visits.

Readers may ignore unknown optional fields if the `schema` remains
`selfplay.v1`.

Parquet readers for `arrow-parquet-selfplay.v1` must not reinterpret the
physical schema ID as a replacement for `selfplay.v1`. The physical contract is
a storage representation for bulk self-play rows, not a new logical training
target.
