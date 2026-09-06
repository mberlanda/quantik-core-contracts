# Symmetry, Orbits, And Transposition Keys

This document defines the portability expectations for canonical state
reasoning. It does not force each implementation to use the same internal cache
layout, but it does define how portable keys and canonical forms must behave.

## D4 Board Symmetry

The 4x4 board has eight geometric symmetries, the dihedral group D4:

```text
d4_index  name
0         identity
1         rotate90
2         rotate180
3         rotate270
4         reflect_vertical
5         reflect_horizontal
6         reflect_main_diagonal
7         reflect_anti_diagonal
```

Each transform maps positions `0..15` to positions `0..15`. Geometric symmetry
alone does not touch shape labels or player colour.

## The Canonicalization Group: D4 × Shape Permutation

**Correction (this section previously undersold what both implementations
already compute and cross-verify byte-for-byte):** canonical equivalence is
not the 8-element D4 group alone. Every implementation's canonical form,
canonical key, and orbit size are computed over the 192-element group `D4 ×
S4` — the 8 geometric D4 transforms combined with all 24 permutations of the
four shape labels (A, B, C, D). Player colour is **not** part of this group:
color swap is never applied when computing the portable canonical form, the
canonical key, or orbit size, in either language. (A `color_swap` axis exists
as an opt-in, non-default parameter in the Python implementation; it is not
used by any production call site — TT keys, opening-book keys, or the
portability report all call the canonicalization APIs with color swap off —
and it is explicitly out of scope for every contract in this document.)

A **transform** is therefore the pair `(d4_index, shape_perm)`, where
`shape_perm` is one of the 24 permutations of `(0, 1, 2, 3)`. The 192
transforms are indexed by a single portable integer:

```text
transform_index = d4_index * 24 + shape_perm_index
```

`shape_perm_index` enumerates the 24 permutations of `(0, 1, 2, 3)` in
lexicographic order — the same order Python's `itertools.permutations(range(4))`
produces, and the order both engine implementations' shape-permutation
generators are already required to produce. `transform_index` therefore
ranges over `0..191` and is stable across languages by construction, not by
convention: `transform_index=0` is always the true identity (no-op).

Applying a transform to a bitboard: first permute positions within each of
the 8 planes according to `d4_index`'s position map, then move plane `s` (one
of the 8 colour/shape planes' shape component) into output slot
`shape_perm[s]`... concretely, output slot `k` receives the
geometrically-transformed plane that was originally shape `shape_perm[k]`,
for each colour independently. This is exactly what both implementations'
canonicalization search already does; it is restated here as the contracted
definition rather than an implementation detail.

## Orbit

The orbit of a state is the set of all boards obtained by applying the 192
transforms above (geometry × shape relabeling, no colour swap).

The orbit size divides 192 (orbit-stabilizer theorem) and depends on the
state's own symmetry: `1` for the empty board, `16` for a single piece in a
corner (4 corners × 4 shape relabellings), up to `192` for a fully asymmetric
position. See
[`fixtures/symmetry/symmetry-v1.json`](../fixtures/symmetry/symmetry-v1.json)
for worked examples of each. Implementations may store the orbit size for
analytics, opening books, or search-space accounting.

## Canonical Representative

The portable canonical representative is the lexicographically smallest
**bitboard payload** (8 little-endian `u16` planes, compared byte-by-byte) in
the state's 192-transform orbit:

```text
canonical_bitboard = min(payload(transform(state)) for transform in the 192-transform group)
canonical_qfen      = qfen(canonical_bitboard)
```

Implementations may use faster equivalent bitboard comparisons internally
(both do), but the externally exposed canonical QFEN and canonical key must
match this rule.

## Action-Index Remap

Every transform has an explicit, portable action-index mapping. Given
`action_index = shape * 16 + position` (`action-index.v1`) and a
`transform_index` as defined above:

```text
d4_index, shape_perm_index = divmod(transform_index, 24)
shape_perm                 = the shape_perm_index'th permutation of (0,1,2,3)
shape, position            = divmod(action_index, 16)

new_position = d4_position_map[d4_index][position]   # the D4 transform's position map
new_shape    = shape_perm.index(shape)               # inverse lookup: which output slot receives old shape `shape`
new_action_index = new_shape * 16 + new_position
```

The `shape_perm.index(shape)` inverse lookup (not `shape_perm[shape]`) is
required because `shape_perm[k]` names which *original* shape moves into
output slot `k` — matching the canonicalization search above.

The inverse of a transform is `(d4_inverse[d4_index], inverse_of(shape_perm))`,
re-encoded as a `transform_index` the same way. `d4_inverse` pairs
`rotate90 <-> rotate270` and is the identity on every other D4 element
(`identity`, `rotate180`, and all four reflections are each their own
inverse). Applying a transform and then its inverse to any `action_index`
must return the original `action_index`.

`remap_action_index(action_index, transform_index)` and
`inverse_transform_index(transform_index)` are the two functions each
implementation exposes publicly for this. See
[`fixtures/symmetry/symmetry-v1.json`](../fixtures/symmetry/symmetry-v1.json)'s
`action_remap_cases` for golden input/output pairs, including a pure
shape-relabel and a combined D4 + shape-perm transform.

## Transposition Keys

Portable transposition keys must be based on canonical representation when the
consumer expects symmetry-equivalent states to collapse into the same entry.

The **sole portable identity** is the 18-byte canonical key, byte-identical
across implementations:

```text
byte 0        = format version (1)
byte 1        = flags (bit 1 set: FLAG_CANON)
bytes 2..17   = canonical bitboard: 8 planes, u16 little-endian
```

```text
raw_key.v1       = qfen                (human-readable, non-canonical)
canonical_key.v1 = the 18-byte key above, hex-encoded when serialized as text
```

Numeric/language-native hashes (Rust's `#[derive(Hash)]`, Python's `__hash__`
overrides used for in-process `dict`/`set` keys) are explicitly **excluded**
from portability: they are process-local, not stable across runs or
languages, and must never be persisted or compared across implementations.
Any persisted or cross-language identity must be the byte-level canonical
key (or its hex encoding) — never a numeric hash.

## Opening Book Implications

Opening books and state DAGs should store:

```text
qfen
canonical_qfen
symmetry_count
depth
side_to_move
terminal_status
```

Edges should be representable using portable move tuples:

```text
from_canonical_qfen
to_canonical_qfen
shape
position
side_to_move
```

When multiple raw moves map to the same canonical edge, the implementation may
store an edge multiplicity.

## Validation Expectations

Consistency checks should compare at least:

- QFEN to bitboard roundtrip.
- Bitboard to QFEN roundtrip.
- Canonical QFEN under the full 192-transform group, not the 8-element D4
  subgroup alone.
- Orbit size for known symmetric fixtures (see
  [`fixtures/symmetry/symmetry-v1.json`](../fixtures/symmetry/symmetry-v1.json)).
- `remap_action_index` composed with `inverse_transform_index` returns the
  original action index for every `(action_index, transform_index)` pair —
  action-index stability after transform-aware move mapping.

