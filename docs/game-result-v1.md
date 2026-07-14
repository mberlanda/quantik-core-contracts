# Game Result v1

`game-result.v1` defines one completed Quantik game used for head-to-head
statistics, Elo proxy estimation, opening-line analysis, and regression
tracking.

The normative bulk storage format is Parquet. JSONL may be used for tiny
fixtures and debug samples.

## Required Fields

```text
schema: game-result.v1
contract_version: 1.1.0
game_id: string
started_at: ISO-8601 utf8 string
p0_engine_kind: string
p0_engine_version: string
p1_engine_kind: string
p1_engine_version: string
initial_position_key: lowercase hex string or other stable utf8 position key
winner: uint8
plies: uint16
terminal_reason: string
move_action_indices: list<uint8>
```

Implemented optional fields:

```text
run_id
```

Checkpoint IDs, opening book IDs, seeds, budgets, position-key traces, and
hardware metadata belong in future additive columns once both implementation
stacks preserve them end to end.

## Winner

`winner` must be:

```text
0 = player 0 won
1 = player 1 won
```

The current Quantik contracts do not encode draws. If a future game variant
needs draws, it must introduce a new major contract or an explicit additive
field that old readers can ignore safely.

## Terminal Reason

Recommended values:

```text
win_condition
no_legal_moves
resignation
timeout
illegal_move_forfeit
adjudication
```

Generated benchmark games should avoid `resignation` unless the engine can
prove the losing condition or the benchmark config explicitly enables
resignation.

## Elo Proxy

For a batch where engine A scores win rate `S` against engine B:

```text
delta_elo = 400 * log10(S / (1 - S))
```

Because current Quantik has no draws, `S` is simply wins divided by games.
Aggregators should still record sample count and confidence intervals.

## Parquet Metadata

The implemented Parquet physical schema is the column set in
`schemas/game-result-v1.json`. Parquet writers should also store file/table
key-value metadata:

```text
physical_schema: game-result.v1
logical_schema: game-result.v1
logical_contract: game-result.v1
contracts_release: 1.1.0
contract_version: 1.1.0
```

The dependency-free manifest
`fixtures/parquet/game-result-v1-metadata.json` mirrors this metadata and
column order for CI checks that cannot import Arrow.

## Compatibility Rules

Readers must reject:

- unknown required schema versions,
- missing engine identity,
- invalid winner,
- empty move list for a non-initial terminal game,
- action indices outside `0..63`,
- `plies` inconsistent with `move_action_indices`,
- missing terminal reason.

Readers may ignore:

- future additive columns that are not required by the v1 physical schema.
