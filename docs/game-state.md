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
