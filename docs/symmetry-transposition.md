# Symmetry, Orbits, And Transposition Keys

This document defines the portability expectations for canonical state
reasoning. It does not force each implementation to use the same internal cache
layout, but it does define how portable keys and canonical forms must behave.

## D4 Board Symmetry

The 4x4 board has eight geometric symmetries, the dihedral group D4:

```text
identity
rotate90
rotate180
rotate270
reflect_horizontal
reflect_vertical
reflect_main_diagonal
reflect_anti_diagonal
```

Each transform maps positions `0..15` to positions `0..15`. Shapes and players
are not changed by geometric symmetry.

## Orbit

The orbit of a state is the set of all QFEN/bitboard states obtained by applying
the eight D4 transforms.

The orbit size can be `1`, `2`, `4`, or `8` depending on the state symmetry.
Implementations may store the orbit size for analytics, opening books, or
search-space accounting.

## Canonical Representative

The portable canonical representative is the lexicographically smallest QFEN in
the state orbit.

This rule is intentionally simple and language independent:

```text
canonical_qfen = min(qfen(transform(state)) for transform in D4)
```

Implementations may use faster equivalent bitboard comparisons internally, but
externally exposed canonical QFEN must match this rule.

## Transposition Keys

Portable transposition keys must be based on canonical representation when the
consumer expects symmetry-equivalent states to collapse into the same entry.

Recommended external keys:

```text
raw_key.v1       = qfen
canonical_key.v1 = canonical_qfen
```

Binary or hashed keys may be used internally, but persisted data must name the
key strategy explicitly.

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
- Canonical QFEN under all D4 transforms.
- Orbit size for known symmetric fixtures.
- Action index stability after transform-aware move mapping.

