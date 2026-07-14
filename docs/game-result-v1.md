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
started_at: timestamp or ISO-8601 string
p0_engine_kind: string
p0_engine_version: string
p1_engine_kind: string
p1_engine_version: string
initial_position_key: bytes or lowercase hex string
winner: int8
plies: uint16
terminal_reason: string
move_action_indices: list<uint8>
```

Optional fields:

```text
p0_engine_checkpoint
p1_engine_checkpoint
opening_book_id
seed
time_budget_ms_per_move
node_budget_per_move
position_keys
hardware
run_id
```

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

- optional hardware metadata,
- optional position key trace,
- optional opening book id,
- optional seed.
