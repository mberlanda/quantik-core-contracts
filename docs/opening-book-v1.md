# Opening Book v1

`opening-book.v1` defines the portable structure for Quantik opening knowledge.
It is a graph contract, not a raw-history or best-move-only format.

The preferred source-of-truth storage is SQLite. Implementations may derive
compact probe artifacts from the SQLite source, but those artifacts must retain
the same node, edge, value, policy, and provenance semantics.

For the storage lessons learned from the first depth-7 Rust-generated SQLite
book, see
[Opening Book Storage Follow-Up From Depth-7 Generation](research/2026-07-14-opening-book-storage-followup.md).

## Scope

Opening books store:

- canonical positions,
- legal graph edges,
- aggregated policy and value knowledge,
- solved or bounded status,
- generation provenance,
- optional human opening and defense annotations.

Opening books do not store raw per-search observations. Use `observation.v1`
for engine observations and `game-result.v1` for head-to-head games.

## Required Concepts

### Book Metadata

Every book artifact must identify:

```text
schema = opening-book.v1
contract_version = 1.1.0
book_id
created_at
generator
generator_version
source_contracts
```

`book_id` should be stable for an artifact build and should change when the
node, edge, value, policy, or annotation contents change.

### Position Node

A position node is identified by `canonical_key`. Implementations may also use a
dense `node_id` for local storage and compact edge references.

Required node fields:

```text
canonical_key
node_id
bitboards
side_to_move
depth_ply
terminal_status
solved_status
game_value
value_confidence
source
```

Optional node fields:

```text
qfen_debug
symmetry_orbit_size
position_encoding
policy_entropy
created_at
updated_at
```

`game_value` is from the perspective of `side_to_move` and must be one of:

```text
-1.0 = losing
 0.0 = unknown or bounded neutral estimate
 1.0 = winning
```

Current `selfplay.v1` rows still disallow draws. `opening-book.v1` permits
`0.0` because book nodes may be unsolved or bounded.

### Solved Status

`solved_status` must be one of:

```text
unsolved
bounded
exact
tablebase
inferred
```

Use `exact` only when the value follows from complete search or retrograde
propagation for the relevant subspace. Use `tablebase` for a derived compact
exact-probe artifact. Use `inferred` for neural or statistical labels.

### Edge

An edge represents a legal action from a parent canonical node to a child
canonical node.

Edge identity must preserve the legal action. Symmetry may map multiple legal
actions from the same parent to the same canonical child, so implementations must
not collapse edges by `(parent, child)` alone.

Required edge fields:

```text
parent_node_id or parent_canonical_key
action_index
child_node_id or child_canonical_key
edge_flags
```

Optional edge fields:

```text
transform_id
prior
visits
q_value
rank
source
source_confidence
```

`action_index` uses `action-index.v1`:

```text
action_index = shape * 16 + position
```

### Policy

Policy may be stored on edges or in a separate policy table. For each policy row:

```text
node_id
action_index
rank
prior
visits
q_value
source
source_confidence
```

`prior` must be in `0.0..1.0`. Policy rows for the same node should either sum
to approximately `1.0` or clearly declare that they are sparse top-k priors.

### Forcedness

Forcedness is distinct from policy probability. Recommended values:

```text
none
only_legal_move
forced_win
forced_defense
tactical_trap
refutation
```

Forcedness may be attached to nodes, edges, or annotations.

### Human Annotation

Named theory is a sparse overlay. It should point at graph nodes and action
sequences instead of duplicating board state.

Recommended fields:

```text
line_id
name
family
root_node_id or root_canonical_key
principal_variation
refutations
tags
notes
evidence
curator
```

`evidence` should identify whether the line is supported by exact solve, MCTS,
minimax, beam search, H2H outcomes, or human curation.

## SQLite Table Shape

The recommended SQLite source shape is:

```sql
CREATE TABLE book_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE positions (
  canonical_key BLOB PRIMARY KEY,
  node_id INTEGER UNIQUE,
  bitboards BLOB NOT NULL,
  side_to_move INTEGER NOT NULL,
  depth_ply INTEGER NOT NULL,
  terminal_status TEXT NOT NULL,
  solved_status TEXT NOT NULL,
  game_value REAL,
  value_confidence REAL NOT NULL,
  qfen_debug TEXT,
  source TEXT NOT NULL
);

CREATE TABLE edges (
  parent_node_id INTEGER NOT NULL,
  action_index INTEGER NOT NULL,
  child_node_id INTEGER NOT NULL,
  edge_flags TEXT NOT NULL,
  transform_id INTEGER,
  PRIMARY KEY (parent_node_id, action_index, child_node_id)
) WITHOUT ROWID;

CREATE TABLE book_policy (
  node_id INTEGER NOT NULL,
  action_index INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  prior REAL,
  visits INTEGER,
  q_value REAL,
  source TEXT NOT NULL,
  source_confidence REAL NOT NULL,
  PRIMARY KEY (node_id, action_index, source)
);
```

Implementations may add indexes and additive columns. Readers must ignore
unknown additive columns when possible.

SQLite builders may use text status fields while the schema is evolving, but
high-cardinality tables should prefer integer ids and compact encoded actions.
Human-readable moves belong in debug views or export layers, not in the hot edge
identity.

## Compatibility Rules

Readers must reject:

- unknown required schema versions,
- invalid `side_to_move`,
- invalid action indices,
- policy rows on illegal actions,
- terminal nodes marked as `unsolved`,
- negative visit counts,
- `value_confidence` outside `0.0..1.0`,
- missing provenance for generated values.

Readers may ignore:

- unknown optional metadata keys,
- human annotations,
- sparse policy fields they do not use,
- debug QFEN fields when bitboards are present.
