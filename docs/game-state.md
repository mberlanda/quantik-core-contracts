# Game State Representation

This document defines `qfen.v1`, `bitboard.v1`, and `action-index.v1`.
These IDs are listed in `contracts.json`; incompatible changes must introduce a
new major contract ID.

## Board Coordinates

Quantik uses a 4x4 board. Positions are integer indices `0..15` in row-major
order:

```text
 0  1  2  3
 4  5  6  7
 8  9 10 11
12 13 14 15
```

The conversion is:

```text
position = row * 4 + column
row = position // 4
column = position % 4
```

## Players And Shapes

Players are encoded as:

```text
0 = first player
1 = second player
```

Shapes are encoded as:

```text
0 = A
1 = B
2 = C
3 = D
```

## QFEN v1

QFEN is the canonical human-readable board notation.

Rules:

- A QFEN string has 4 ranks separated by `/`.
- Each rank has exactly 4 characters.
- `.` means an empty square.
- `A`, `B`, `C`, `D` are player `0` pieces.
- `a`, `b`, `c`, `d` are player `1` pieces.
- Ranks are emitted from top row to bottom row.
- Whitespace is not part of the canonical representation.

The empty board is:

```text
..../..../..../....
```

Example:

```text
A.bC/..../d..B/...a
```

This means:

```text
position 0  = player 0, shape A
position 2  = player 1, shape B
position 3  = player 0, shape C
position 8  = player 1, shape D
position 11 = player 0, shape B
position 15 = player 1, shape A
```

QFEN only encodes pieces. The side to move must be represented separately or
derived from a validated legal game state.

## Bitboard v1

The cross-language bitboard representation is an ordered sequence of eight
unsigned 16-bit values:

```text
index 0 = player 0, shape 0
index 1 = player 0, shape 1
index 2 = player 0, shape 2
index 3 = player 0, shape 3
index 4 = player 1, shape 0
index 5 = player 1, shape 1
index 6 = player 1, shape 2
index 7 = player 1, shape 3
```

Within each 16-bit value, bit `position` is set when that player/shape occupies
that square.

Invariants:

- All bitboards must be in `0..65535`.
- No square may be occupied by more than one piece.
- Legal game states must also satisfy Quantik inventory and placement rules.

## Move v1

A move is:

```text
player: 0|1
shape: 0..3
position: 0..15
```

For policy targets and ML action vectors, `player` is implicit from
`side_to_move`. The action index is shape-major:

```text
action_index = shape * 16 + position
```

There are exactly 64 action slots.

## Side To Move

`side_to_move` is encoded as `0` or `1`.

When a row includes both `qfen` and `side_to_move`, validators must confirm that
the side is consistent with the legal game state.

## Terminal State

A state is **terminal** when either player has completed a winning line, or
when the side to move has **no legal moves** — in the latter case the side to
move loses. Every state/game/adapter-facing API that reports terminal status
(board/game objects, search engines, the portability report, and any
`observation`/`game-result` producer) must include the no-legal-moves case as
a loss for the side to move, not just an explicit win. A low-level function
that checks only for a completed line (no legal-move check) must not be
named or documented as a terminal check — name it as a win check instead
(e.g. `check_winner`/`has_winning_line`), so callers cannot mistake a
partial check for the full terminal contract.

## Invalid-State Validation Boundaries

Game-state validation is layered. Each boundary below has a required floor;
an implementation may check more, but must not check less at its own layer,
because a QW-001 goal is generating structurally identical adapter reports.
Golden cases for every one of these are in
[`fixtures/invalid-states/invalid-state-v1.json`](../fixtures/invalid-states/invalid-state-v1.json)
(`invalid-state-fixtures.v1`).

**Parser boundary** (QFEN/wire string → bitboards). Structural checks only,
always enforced, independent of any "strict" flag:

- exactly 4 ranks, each exactly 4 characters (`MALFORMED_QFEN`),
- every character is `.`, `A`-`D`, or `a`-`d` (`MALFORMED_QFEN`).

The parser boundary does not check inventory, overlap, line conflicts, or
turn balance — a QFEN string cannot encode an overlap (one character per
cell), and the other three require counting across the whole board, which is
the constructor boundary's job.

**Constructor boundary** (bitboards → validated state). Full game-state
validation, always enforced when a public state/board type is constructed
from raw bitboards:

- no two planes occupy the same cell (`PIECE_OVERLAP`),
- no plane exceeds the per-shape inventory limit, 2 per shape per player
  (`SHAPE_COUNT_EXCEEDED`),
- player piece-count difference is `0` or `1` (`TURN_BALANCE_INVALID`),
- no row/column/region holds the same shape from both players
  (`ILLEGAL_PLACEMENT`).

**Adapter/portability-report boundary.** The same four checks as the
constructor boundary, applied unconditionally — an adapter must never accept
a state its own language's constructor would reject. This closes a
cross-stack gap found during QW-001: a portability-report code path that
parses a QFEN without also running the constructor's full validation can
silently diverge from the other language's report for the same fixture
input.

`MALFORMED_QFEN` is a parser-boundary-only outcome (no `ValidationResult`
enum member applies, because no bitboard was ever built); the other four
names match the shared `ValidationResult` vocabulary and must be spelled
identically by every implementation's own validation-result type.
