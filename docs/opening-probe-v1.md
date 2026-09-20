# Opening Probe v1 — Design Decision Paper

Status: **decided 2026-09-20: all recommendations D0-D6 accepted as written.** The
rejected alternatives are kept below as the record of why. Registered by
QW-004/W2: `schemas/opening-probe-v1.json` (the JSON metadata header),
the `opening_probe` entry in `contracts.json`, fixtures in `fixtures/opening-probe/`
and a reference probe in `scripts/validate_contracts.py`.

`opening-probe.v1` is a compact, read-only, engine-facing lookup artifact
derived from an `opening-book.v1` SQLite book
([`opening-book-v1.md`](opening-book-v1.md), "preferred source-of-truth storage",
lines 6-9). This paper decides its contract.

Evidence citations are `file:line`. Contracts lines are at this repo's `main`
(`cc9081d`); Rust lines are at `quantik-core-rust` `origin/main` (`fe89c44`).
Quantik has no draws (workspace invariant I2); a book `game_value` of `0.0`
means "unknown", never "drawn".

## Why orientation is the whole problem

The probe is keyed by the canonical representative, so a hit answers for the
*representative's* orientation, not the caller's. Three facts in the current code
make that easy to get silently wrong:

- `SymmetryHandler::find_canonical` returns only the representative
  (`crates/quantik-core/src/symmetry.rs:110`); the transform that produced it is
  tracked by neither the loop variable nor the return value
  (`symmetry.rs:110-139`). A caller cannot recover it from the public API today.
- The existing book stores `best_moves` as `(shape, position)` in the
  representative's frame and refuses to write any other orientation
  (`opening_book.rs:232-242`, guard at `:262`). The doc comment calls translating
  across orientations "a documented follow-up" (`:240-242`).
- The only current reader dodges the problem by returning `None` for every
  position that is not already its own representative
  (`bench/book_export.rs:121-126`) — a silent miss, not a wrong move, but it
  means the book is unusable for most real positions.

## Decisions

Each item is DECIDED 2026-09-20 (the RECOMMENDED option was accepted); the
section number is where the options, tradeoffs and rejected alternatives are
written down.

- **D0 DECIDED 2026-09-20 (section 0) Container format** — file, SQLite, KV store, or generated
  module? RECOMMENDED: single sorted fixed-record binary file with a JSON
  metadata header.
- **D1 DECIDED 2026-09-20 (section 1) Probe key** — RECOMMENDED: the 18-byte `canonical_key.v1`,
  stored verbatim per record, sorted by unsigned bytewise order (not numeric
  `u16` order).
- **D2 DECIDED 2026-09-20 (section 2) Value and payload** — RECOMMENDED: `game_value` in
  `{-1, 0, +1}` (side to move), a `status` byte (`exact`/`bounded`), and a
  64-bit set of optimal actions in the representative's frame. No visits, priors
  or Q-values. A miss is `None`; "in the book, unknown" is a hit with
  `status = bounded`, `game_value = 0`.
- **D3 DECIDED 2026-09-20 (section 3) Transform and action mapping** — RECOMMENDED: derive the
  transform at probe time from the caller's position (no stored transform),
  tie-break to the lowest `transform_index`, map with
  `inverse_transform_index(t)`, and require a new
  `find_canonical_with_transform` primitive in `quantik-core`.
- **D4 DECIDED 2026-09-20 (section 4) Metadata and checksum** — RECOMMENDED: full provenance
  (source book id, generator, producer contract release), ply coverage, entry
  count, SHA-256 of the record body, verified at open. `contract_version` is
  informational here, not an equality gate.
- **D5 DECIDED 2026-09-20 (section 5) Errors** — RECOMMENDED: fail fast on everything except
  "key not found" and "ply outside coverage"; add a mandatory
  legality check on the mapped-back action as an orientation tripwire.
- **D6 DECIDED 2026-09-20 (section 6) Migration** — RECOMMENDED: `opening-book.v1` and
  `opening-book-summary.v1` keep their versions; W2 adds two clarifying
  sentences to `opening-book-v1.md` (which frame `action_index` is in; what
  `transform_id` means). No new required fields.

Questions decided without an obvious right answer (for the W1 handoff): **D3
tie-breaking and D1 record-key width** (see those sections).

## 0. Container format (D0) — DECIDED 2026-09-20

Options:

- **A. Sorted fixed-width binary file, JSON header (RECOMMENDED).** Header, then
  a contiguous array of equal-size records sorted by key; lookup is a binary
  search; memory-mappable; readable from any language with no dependency.
- **B. SQLite subset.** Zero new code on the producer side, but the book already
  is SQLite and is neither compact nor free of a native dependency for consumers
  such as the browser visualizer (workspace `CLAUDE.md`: dependency-free app).
- **C. Key/value store (LMDB, RocksDB, redb).** Fast, but every consumer language
  inherits an engine dependency and a format the contract cannot describe in
  bytes.
- **D. Generated Rust module.** Compile-time table. Rejected: not portable, and
  contradicts I5 (contracts are the source of truth, code is validated against
  them).

Tradeoff accepted for A: a rebuilt table means a new file (no in-place update).
That matches the research position that the probe is derived, not authoritative
(`docs/research/2026-07-14-opening-book-storage-followup.md:125-127`).

Layout, one decision per field, for W2 to put in the schema:

```text
offset 0    8 bytes   magic  "QPROBE\x00\x01"  (ASCII QPROBE, 0x00, format major 1)
offset 8    u32 LE    metadata_len  (bytes)
offset 12   metadata_len bytes   UTF-8 JSON, keys sorted, no NaN (see section 4)
then        zero padding to the next multiple of 8 bytes
then        records: entry_count * 28 bytes, sorted ascending by key
```

Record (28 bytes, all integers little-endian, matching the 8×`u16` LE convention
of `bitboard.v1`):

```text
bytes  0..18   canonical_key.v1                (section 1)
byte   18      game_value  i8   in {-1, 0, 1}  (section 2)
byte   19      status      u8   1 = exact, 2 = bounded
bytes  20..28  optimal_actions  u64 LE, bit i = action i  (section 2)
```

## 1. Probe keys (D1) — DECIDED 2026-09-20

The probe key is the `canonical_key.v1` defined in
[`symmetry-transposition.md`](symmetry-transposition.md) lines 132-143: 18 bytes,

```text
byte 0        = 0x01   format version
byte 1        = 0x02   flags (FLAG_CANON)
bytes 2..17   = canonical bitboard: 8 planes, each u16 little-endian,
                plane order P0 shapes 0-3 then P1 shapes 0-3
```

Rust builds it at `state.rs:67-72` from `canonical_payload()` (`symmetry.rs:142`).
The lookup order of records is **unsigned byte-wise (`memcmp`) order over all 18
bytes**.

This is the trap: the canonical representative is chosen by comparing planes
*byte by byte in little-endian order* (`le_bytes_less`, `symmetry.rs:241-257`;
`symmetry-transposition.md:80-82`). Comparing the planes as `u16` numbers gives a
different order (plane word `0x0100` has bytes `00 01`, and sorts below
`0x0001`'s `01 00` bytewise but above it numerically), so a table sorted numerically
would silently miss keys under a bytewise binary search. The contract fixes
bytewise.

Options:

- **A. Full 18-byte key per record (RECOMMENDED).** Byte-identical to
  `positions.canonical_key` in the source book, so the builder copies blobs
  without re-encoding; the existing validator already checks 18-byte keys
  (`opening-book-v1.md:280`); every record carries its own version/flag bytes, so
  a key-format drift is detectable per record rather than only in the header.
  Cost: 2 bytes/record (about 7% of a 28-byte record).
- **B. 16-byte payload per record, `0x01 0x02` hoisted to the header.** Saves
  2 bytes/record but makes the file's key differ from the contract's "sole
  portable identity" (`symmetry-transposition.md:132`), and forces every reader
  to reattach the prefix. Not worth 7%.
- **C. Truncated or 64-bit hash of the key.** Rejected: collisions turn into
  wrong-but-legal-looking moves, exactly the failure class this work exists to
  avoid, and `symmetry-transposition.md:146-150` forbids persisted numeric
  hashes.
- **D. QFEN as key.** Rejected: `raw_key.v1 = qfen` is non-canonical
  (`symmetry-transposition.md:141`), and the book itself calls QFEN debug text
  (`schemas/opening-book-v1.json`, notes).

Side to move is **not** in the key. It is the parity of pieces on the board
(workspace invariant table; `game-state.md:131-133`), which every one of the 192
transforms preserves because no colour swap is applied
(`symmetry.rs:108-109`). The probe derives it from the representative.

Every record's byte 0 must equal `1` and byte 1 must equal `0x02`; anything else
is corrupt (section 5). Consequence for W3: `State::unpack` only checks length and
the version byte, not the flags byte, and tolerates longer buffers
(`state.rs:34-46`), so the probe reader must do its own stricter check rather than
reuse it.

Note for W3: three separate places build this key today —
`state.rs:67-72`, `bin/bench_bfs.rs:45-52`, `bin/book_builder.rs:68-75`. They agree
now; W3 should route through one and W4 should pin all three with the fixture.

## 2. Values and bounds (D2) — DECIDED 2026-09-20

Options:

- **A. Value only.** Smallest, but the point of a probe in an opening is the move.
- **B. Value + `status` + all optimal actions as a 64-bit set (RECOMMENDED).**
  8 bytes carry every optimal move regardless of count. Because the exact solver
  stores *every* optimal move (`opening_book.rs:229-230`, loop at `:299-305`)
  rather than a top-5 slice (`:215`), a set matches it exactly and — for an
  exact position — the set is invariant under the position's stabiliser, so the
  tie in section 3 changes which member is returned, never whether a returned
  move is optimal.
- **C. B plus visits, priors, Q-values, ranking.** Rejected for v1: these belong
  to `opening-book.v1` policy rows (`opening-book-v1.md:141-156`), inflate the
  record several times over, and no consumer in QW-004 needs them. Additive later
  as a new optional section if a consumer appears.
- **D. Single best action (1 byte).** Rejected: loses the equal-optimal set, and a
  single stored action makes the section 3 tie-break return an arbitrary member.

Fields:

- `game_value` — `i8` in `{-1, 0, +1}`, from the side to move's perspective
  (`opening-book-v1.md:78-83`). `0` is "unknown or bounded neutral estimate",
  never a draw (I2; `opening-book-v1.md:86-87`).
- `status` — `1 = exact`, `2 = bounded`. Subset of the book's `solved_status`
  (`opening-book-v1.md:89-103`); `unsolved`, `inferred` and `tablebase` are not
  written into a probe (`unsolved` and `inferred` carry no guarantee; `tablebase`
  is the name for the derived artifact itself).
- `optimal_actions` — `u64`, bit `i` means action `i` (`shape * 16 + position`,
  `ACTION_COUNT = 64`, I6), **in the representative's orientation**.

Validity rules (all corrupt if violated, section 5):

- `status = exact` implies `game_value` in `{-1, +1}` (a book row stores exactly
  that today: `opening_book.rs:41`, `add_solved_position` at `:256-261`).
- `status = bounded` may have any of the three values.
- `optimal_actions = 0` is legal only when the position is terminal or has no
  legal move (then `game_value = -1`, `exact`; `game-state.md:136-140`). For any
  other entry an empty set is corrupt: an entry with a value and no move is
  useless for an engine.
- Bits above 63 do not exist; the field is exactly 64 slots.

Absent versus unknown, stated once so implementations cannot conflate them:

- **Not in the book** — no record for the key. The API returns `None`/`Miss`.
  Ply outside `[ply_min, ply_max]` is the same kind of miss (section 4).
- **In the book, unknown** — a record with `status = bounded`, `game_value = 0`.
  The API returns a hit whose value is unknown; the engine may still use
  `optimal_actions` as a move-ordering hint.

The current in-repo reader flattens these: `lookup_reference` returns `None` for
unsolved rows and rows without best moves (`bench/book_export.rs:128-141`), so
"unsolved but present" is indistinguishable from "absent".

## 3. Move and action transforms (D3) — DECIDED 2026-09-20

### 3.1 Definitions (all quoted from existing code, not new)

- A transform is `t = d4_index * 24 + shape_perm_index`, `0..191`
  (`symmetry-transposition.md:46`). `shape_perm_index` is lexicographic order of
  the permutations of `(0,1,2,3)` (`symmetry.rs:29`).
- Applying `t` to a board moves position `p` to `D4_MAPS[d4][p]` and puts, in
  output slot `k`, the plane that was originally shape `perm[k]`
  (`symmetry.rs:7-27`, candidate construction at `:117-127`).
- The representative `R` of position `S` is the byte-wise least payload over the
  192 images of `S` (`symmetry.rs:110-139`). Let `t*` be the transform whose image
  is `R`. Then **`R = apply(S, t*)`: `t*` runs caller to representative.**
- `remap_action_index(a, t)` moves an action the same way the board moved:
  `new_position = D4_MAPS[d4][position]`,
  `new_shape = perm.index(shape)` — an inverse lookup, not `perm[shape]`
  (`symmetry.rs:185-214`, the explanatory comment at `:201-203`;
  `symmetry-transposition.md:105-109`). It maps *from the frame `t` starts in to
  the frame `t` ends in*.
- `inverse_transform_index(t)` is `(D4_INVERSE[d4], inverse(perm))`
  (`symmetry.rs:217-238`; `D4_INVERSE = [0,3,2,1,4,5,6,7]` at `:62`).

### 3.2 The rule

```text
probe(S):                                        S = caller's position
    (R, t*) = find_canonical_with_transform(S)   t*: caller -> representative
    record  = lookup(canonical_key(R))           None => Miss
    for each set bit a_rep in record.optimal_actions:
        a_caller = remap_action_index(a_rep, inverse_transform_index(t*))
    assert every a_caller is a legal move of S   (section 5, fail-fast)
    return hit { game_value, status, actions = { a_caller }, t* }
```

Directions, once:

- Board direction: caller to representative uses `t*`.
- Action direction: stored (representative frame) to caller uses
  `inverse_transform_index(t*)`. Using `t*` itself here is the bug: it is only
  correct when `t*` is its own inverse (identity, rotate180, the four
  reflections with identity shape permutation). It is wrong whenever the D4 part is
  rotate90 or rotate270, or the shape permutation has order greater than 2
  (a 3-cycle or 4-cycle) — most of the 192 transforms (see the example, which
  uses rotate270).
- The mask is remapped **bit by bit** (a permutation of the 64 slots); it is not
  shifted or rotated as an integer.

### 3.3 Options considered

- **A. Derive `t*` at probe time from the caller's position (RECOMMENDED).** The
  transform depends on the *query*, not on the record: two different callers
  hitting the same record need different transforms. So there is nothing correct
  to store per record. Costs one 192-candidate canonicalisation per probe, which
  the engine already pays to form the key (`find_canonical`).
- **B. Store a transform id per record** (the shape the book's optional edge
  `transform_id` suggests, `opening-book-v1.md:126`, `:226`). Rejected: it would
  hold the transform of *whichever* source orientation the builder saw, which is
  meaningless to a caller in a different orientation, and is exactly the
  silent-wrong-move risk if a reader trusts it. This resolves the open question
  at `docs/research/2026-07-14-opening-book-storage-followup.md:196-197`:
  derive at probe time.
- **C. Store actions for every raw orientation** (no canonicalisation on the
  value side). Rejected: up to 192x growth, and it abandons the canonical-key
  design the book already relies on.
- **D. Return the action in the representative frame and let the caller map.**
  Rejected: pushes the correctness risk onto every caller, which is the failure
  the packet exists to prevent.

### 3.4 Tie-break: which `t*` when several transforms give the same representative

If `S` has a non-trivial stabiliser, several transforms produce the same `R`
(the fixture `single-corner-shape-a` has `orbit_size = 16`, so its stabiliser has
`192 / 16 = 12` elements). All of them are valid, and for a stabiliser-invariant
action set they return symmetric-equivalent moves; for a bounded or partial set
they can return different members.

Decision: **`t*` is the lowest `transform_index` among the minimisers.** This
costs nothing today: the search iterates `d4_idx` then `perm` in ascending order
and only replaces `best` on a strictly-less payload (`symmetry.rs:113-133`), so it
naturally keeps the lowest index. The new primitive must preserve that, and the
contract fixes it so that Python and Rust return the same action set, not merely
an equivalent one. Alternative rejected: "any minimiser" — leaves cross-language
results non-reproducible and W4 evidence unfalsifiable.

Required new primitive (W3, not this item):
`SymmetryHandler::find_canonical_with_transform(&Bitboard) -> (Bitboard, u8)`.
`find_canonical` cannot be reused because it does not return the transform
(`symmetry.rs:110-139`). Python needs the analogue in `quantik-core-py`.

### 3.5 Worked example (verify by hand)

Caller position `S`, QFEN (uppercase = player 0, lowercase = player 1; positions
are row-major `0..15`):

```text
..../.B../c.../A...
```

Pieces: P0 `B` at position 5, P0 `A` at 12, P1 `c` at 8. Three pieces on the board,
so **player 1 is to move**.

`S` bitboard planes (u16, bit `p` = position `p`), P0 shapes A,B,C,D then P1
A,B,C,D:

```text
A(P0)=0x1000  B(P0)=0x0020  C(P0)=0  D(P0)=0   a=0  b=0  c(P1)=0x0100  d=0
serialized payload (8 x u16 LE) = 00 10 20 00 00 00 00 00 00 00 00 00 00 01 00 00
```

Over all 192 transforms the least payload is uniquely reached at
`t* = 95 = 3 * 24 + 23`:

```text
d4_index = 3   (rotate270:  position (r,c) -> (3-c)*4 + r)
shape_perm_index = 23 -> shape_perm = (3, 2, 1, 0)
  slot k receives original shape perm[k]:
  slot0<-D, slot1<-C, slot2<-B, slot3<-A
```

Apply it. Position map for rotate270 is `p -> (3-c)*4 + r`: `5 -> 9`, `12 -> 15`,
`8 -> 14`. Shape map: original shape `s` lands in slot `perm.index(s)`: `B(1) ->
slot 2 = C`, `A(0) -> slot 3 = D`, `c(2) -> slot 1 = b`. Representative `R`:

```text
..../..../.C../..bD        P0 C at 9, P0 D at 15, P1 b at 14
payload = 00 00 00 00 00 02 00 80 00 00 00 40 00 00 00 00
canonical_key = 01 02 | 00 00 00 00 00 02 00 80 00 00 00 40 00 00 00 00
                (hex 010200000000000200800000004000000000)
```

Suppose the probe record for that key stores `optimal_actions` with bit **22**
set: shape `22 / 16 = 1` (B), position `22 % 16 = 6`. In the representative's
frame that is "P1 plays shape B at position 6" — legal there (P0 holds no `B`; P1
holds `b` at 14, one of two).

Map it back with `inverse_transform_index(95)`:

```text
inverse of d4=3 (rotate270)  = D4_INVERSE[3] = 1 (rotate90)
inverse of perm (3,2,1,0)    = (3,2,1,0)   (self-inverse)
inverse t = 1 * 24 + 23 = 47
position: rotate90 (r,c) -> c*4 + (3-r); position 6 = (1,2) -> 2*4 + 2 = 10
shape:    perm.index(1) under (3,2,1,0) = 2
a_caller = 2 * 16 + 10 = 42        (shape C, position 10)
```

Check by the forward direction: `remap_action_index(42, 95)`: rotate270 sends
position 10 = (2,2) to `(3-2)*4 + 2 = 6`; shape 2 has `perm.index(2) = 1`;
`1*16 + 6 = 22`. Round trip holds.

Legality in the caller's position `S`: P1 places `C` at position 10 (row 2,
column 2, zone rows 2-3/cols 2-3). Player 0 has no `C` anywhere, and P1's own
`c` at 8 is its first of two. Legal.

What the two wrong implementations do:

- No transform (return the stored action as is): shape B, position 6. In `S`,
  P0's `B` is at position 5, same row as 6. **Illegal** — the lucky case where
  the engine's legality mask catches it (I3).
- Using `t*` instead of its inverse: `remap_action_index(22, 95)` gives shape
  `perm.index(1) = 2`, position `rotate270(6) = (3-2)*4 + 1 = 5`, action 37 — shape
  C at position 5, which is occupied by P0's `B`. Also illegal here, but this is
  a coincidence of this position; in general a wrong-direction action lands on
  another legal square and is not caught. That is why section 5 makes the
  legality check mandatory and why W4 needs a case where the wrong direction is
  legal.

(The numbers above were computed by an independent re-implementation of the
symmetry group that reproduces all three `board_cases` and all eleven
`action_remap_cases` in `fixtures/symmetry/symmetry-v1.json`; W2 should turn this
example into a fixture so nobody has to trust this paragraph.)

### 3.6 Tie example (for the fixture)

Caller `B.../..../..c./....` (P0 `B` at 0, P1 `c` at 10, player 0 to move) has
representative `..../..c./..../D...` reached by four transforms:
`t in {77, 91, 125, 139}`. Take the stored action 10 (shape A, position 10) in the
representative frame. Mapped back:

```text
t = 77  (inverse 29):   action 9   (A at 9)     <- lowest index: the contract's answer
t = 91  (inverse 35):   action 57  (D at 9)
t = 125 (inverse 125):  action 6   (A at 6)
t = 139 (inverse 131):  action 54  (D at 6)
```

All four are symmetric images of one another because `A <-> D` is a symmetry (both
absent from `S`) and so is the reflection through the main diagonal (both
pieces sit on it). The contract returns the `t = 77` result. This case exists to make Rust and Python agree, not merely be correct.

## 4. Metadata (D4) — DECIDED 2026-09-20

Goal: a stale or foreign probe is detectable, not merely wrong. The JSON header
object holds:

```text
schema               "opening-probe.v1"
format_major         1
key_format           "canonical_key.v1"
record_size          28
entry_count          integer
ply_min, ply_max     integer, inclusive coverage (depth_ply = pieces on board)
per_ply              [{ "ply": n, "entries": m }, ...]   sums to entry_count
coverage_complete    bool: every canonical position at plies ply_min..ply_max
                     that the source book contains is present
source_book          { "book_id", "schema", "contract_version",
                       "generator", "generator_version" }
generator            name of the probe builder
generator_version    version of the probe builder
contract_version     contracts release the builder validated against
created_at           RFC 3339
body_sha256          hex SHA-256 of the record region, exactly entry_count*28 bytes
```

Mandatory: `schema`, `format_major`, `key_format`, `record_size`, `entry_count`,
`ply_min`, `ply_max`, `per_ply`, `source_book.book_id`, `generator`,
`generator_version`, `contract_version`, `body_sha256`. Optional: `created_at`,
the rest of `source_book`, `coverage_complete`. Unknown optional keys are ignored
(same posture as `opening-book-v1.md:264-266`).

Options:

- **A. Version and entry count only.** Detects truncation, not staleness; a probe
  built from last month's book is indistinguishable.
- **B. Provenance + coverage + body checksum (RECOMMENDED).** `source_book.book_id`
  changes whenever the book's nodes, edges, values, policy or annotations change
  (`opening-book-v1.md:44-45`), so comparing it to the current book detects a stale
  probe. `per_ply` mirrors `opening-book-summary.v1`'s `per_depth`
  (`opening-book-summary-v1.md`, "Each `per_depth` row"), so the existing summary
  can cross-check the probe without a new format.
- **C. B plus a detached signature.** Rejected: this is an integrity check, not an
  authenticity one, and distribution signing is a separate concern.

Checksum: SHA-256 over the record region, verified when opening. CRC32C was
considered and rejected: cheaper, but SHA-256 is in every language's standard
library, lets a manifest or the validator pin one artifact exactly, and the cost
is one pass at open.

`contract_version` — a decision with a real conflict. `docs/versioning.md:66` says
optional `contract_version` fields "equal the repository release version", but a
probe file is a distributable artifact that will outlive the release that built
it. Decision: in a probe file `contract_version` is **informational** (the release
the builder validated against), never an equality gate at runtime; the fixture
files W2 adds are the only place the equality rule applies, as for every other
fixture. Compatibility at runtime is decided by `schema`, `format_major`, and
`key_format` only. Rejected alternative: enforce equality at runtime — it would
make every published probe fail after the next contracts release.

`coverage_complete` matters for interpreting misses: with `true`, a miss inside
`[ply_min, ply_max]` means the source book had no such position; with `false` or
absent it means only "this file does not know". A miss outside the range is always
"not covered".

## 5. Errors (D5) — DECIDED 2026-09-20

Fail-fast is the default. Every non-miss failure is an error value, never a
silent fallback to "no book move".

Fail-fast (return an error, do not degrade to a miss):

- **Corrupt** — bad magic; metadata not valid JSON or missing a mandatory key;
  `record_size` other than 28; a record whose key byte 0 is not `1` or byte 1 is
  not `0x02` (`FLAG_CANON`, `constants.rs:2`); `status` not in `{1, 2}`;
  `game_value` not in `{-1, 0, 1}`; `exact` with `game_value = 0`; empty
  `optimal_actions` on a non-terminal entry; `per_ply` not summing to
  `entry_count`.
- **Truncated** — `12 + metadata_len` plus padding plus `entry_count * 28` is not
  the file length. Checked at open, before any lookup.
- **Incompatible version** — `format_major` other than 1, `schema` other than
  `opening-probe.v1`, or an unknown `key_format`. Never partially read.
- **Checksum mismatch** — `body_sha256` differs. Checked at open.
- **Unsorted or duplicate keys** — checked in one pass at open. A buggy producer
  can emit a valid checksum over an unsorted table, and a bytewise binary search
  over it returns silent misses.
- **Invalid caller position** — the state fails engine validation
  ("invalid states fail explicitly at the contracted adapter boundary", workspace
  canonical-invariants table). Not a miss.
- **Illegal mapped-back action** — after section 3's mapping, any returned action is
  not a legal move of the caller's position. This can only mean a wrong transform
  or a corrupt record. It is the orientation tripwire; the legality generator is
  exact (I3) and the cost is a few move-generator calls per hit. It must also run
  in release builds.
- **Stale** (opt-in) — an `open` variant that takes an expected `book_id` and
  fails on mismatch. Not the default, because a probe need not be re-checked
  against a book that is not present at runtime.

Ordinary misses (not errors):

- Key not present in a valid probe.
- Ply of the caller's position outside `[ply_min, ply_max]` (cheap early exit;
  the engine falls through to search).

A hit with `status = bounded, game_value = 0` is a hit (section 2), not a miss.

Rejected: treating corruption as a miss so the engine "just searches". That keeps
the engine running while the book is silently broken, which for a strength
feature reads as "the book never helps" and would go unnoticed for a long time.
The one place a runtime may soften a fail-fast is the caller's own policy:
`open` returns an error and the *application* decides whether to continue
without a book; the library does not decide for it.

Open-time verification cost: the checksum and sortedness pass are O(n) reads of the
file. Options for very large files are a documented `verify = false` that is an
explicit, named opt-out and is never the default. Left to W3 to size.

## 6. Migration (D6) — DECIDED 2026-09-20

Relationship: `opening-probe.v1` is **derived** from `opening-book.v1` (SQLite),
which stays the source of truth (`opening-book-v1.md:6-9`; research
`...storage-followup.md:125-127`). The probe's records are a projection of book
rows: the key is `positions.canonical_key`, the value is `game_value` / solved
status, the action set is the book's optimal-move rows.

Options:

- **A. No change to either book contract; document only in the probe doc.**
  Cheapest, but leaves a real gap open, below.
- **B. Additive clarifications in `opening-book-v1.md` (RECOMMENDED).** No new
  required field, no version change (minor per `versioning.md:25`):
  1. State that `action_index` on any row keyed by a canonical key (positions'
     best moves, `book_policy`) is in the **canonical representative's
     orientation**. Today the contract never says which frame it is in
     (`opening-book-v1.md:138`, `:141-156`), while the only writer stores the
     representative frame and rejects the rest (`opening_book.rs:232-242`); a
     second implementation could store the caller's frame and no validator would
     notice (the validator "does not recompute legal moves from board state",
     `opening-book-v1.md:288-290`).
  2. Define the optional edge `transform_id` (`:126`): the `transform_index`
     (`symmetry-transposition.md:46`) that maps the board reached by applying
     `action_index` on the parent's representative to the child's representative
     (caller-to-representative direction, same as section 3). Keep it optional
     and unused by the probe.
- **C. New required fields or `opening-book.v2`.** Rejected: nothing in the probe
  needs the book to change shape, and a major bump would trigger the downstream
  tag-order ceremony for no consumer benefit.

`opening-book-summary.v1` is unchanged. The probe carries its own `per_ply`
(section 4); a validator may cross-check it against a summary, but the summary
never gains probe fields.

Consequences for W2's `allowed_paths`: B touches only `docs/opening-book-v1.md`
plus the probe doc, schema and fixtures, all already on W2's list; `schemas/
opening-book-v1.json` needs no change (the tables and columns are unchanged).

Registering `opening-probe.v1` is an additive minor contracts release (new
contract, new fixtures, new checks) under `versioning.md:25`.

## Fixtures W2 should ship (so W4 has something to cross-produce against)

1. Hit at identity transform (`t* = 0`).
2. Hit needing a non-self-inverse transform: the example in 3.5.
3. The tie case in 3.6, fixing lowest-index tie-break.
4. A case where the *wrong-direction* mapping (using `t*` not its inverse) is still
   a legal move, so the fixture fails an implementation the legality tripwire
   would not catch.
5. Miss (key absent) and miss (ply outside coverage).
6. Bounded/unknown hit (`bounded`, value 0) distinct from a miss.
7. Corrupt-key-flags, truncated, unsorted, bad checksum, `format_major = 2`.
8. A stale-book case for the opt-in `book_id` check.

## Registered fixtures (W2)

A probe is a binary file and fixtures are JSONL, so each row in
`fixtures/opening-probe/opening-probe-v1-synthetic.jsonl` is a decoded description of one
probe file: `header` (the schema object), `records` (`key` as 36 hex characters,
`game_value`, `status` as `exact`/`bounded`, `optimal_actions` as a sorted list that
serialises to the u64 set) and `probe_cases` (a caller QFEN and the expected hit, miss or
error). `scripts/validate_contracts.py` serialises the records to compute `body_sha256`
and the layout length (metadata as compact key-sorted JSON), runs the section 5 checks,
and replays every `probe_cases` entry through a reference probe. Values are synthetic,
not oracle output. Rows that must be rejected live in `opening-probe-v1-invalid.json`
(not `.jsonl`, so the fixture glob does not pick them up); a truncated file is expressed
as a declared `file_length` that disagrees with the layout.

## Follow-ups

W2 (`quantik-core-contracts`, `feat/register-opening-probe`):

- Register `opening-probe.v1`: schema, `contracts.json` entry, validator.
- Add to `opening-book-v1.md` (D6): `action_index` on rows keyed by a canonical
  key is in the canonical representative's orientation; optional edge
  `transform_id` is the caller-to-representative `transform_index`.
- Ship the probe fixtures listed above, including the section 3.5 case and a case
  where applying `t*` instead of `inverse_transform_index(t*)` still yields a
  legal move.

W3 (`quantik-core-rust`, `feat/opening-probe`, plus `quantik-core-py`):

- Add `SymmetryHandler::find_canonical_with_transform(&Bitboard) -> (Bitboard, u8)`
  in core, lowest-`transform_index` tie-break, and a Python analogue.
- Implement the probe with the section 5 fail-fast taxonomy, bytewise key order,
  and the mandatory mapped-back legality check.
