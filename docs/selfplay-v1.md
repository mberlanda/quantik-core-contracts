# Self-Play v1

`selfplay.v1` defines one supervised training observation emitted from a
self-play game.

The canonical fixture representation is JSONL: one JSON object per line.

## Required Fields

```json
{
  "schema": "selfplay.v1",
  "contract_version": "0.1.0",
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

For Arrow/Parquet, prefer dense visits:

```text
policy_visits: fixed_size_list<uint32, 64>
```

Dense visits avoid ragged nested arrays during training and make the action
index contract explicit.

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
