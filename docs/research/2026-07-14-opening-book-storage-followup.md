# Opening Book Storage Follow-Up From Depth-7 Generation

Date: 2026-07-14

Status: follow-up design note for `opening-book.v1` implementers

## Executive Summary

The Rust depth-7 generation run confirmed that Quantik opening knowledge should
remain a graph contract, but the first SQLite implementation is too verbose to
be the long-term engine-facing artifact.

The useful result is not just the larger book. The important learning is the
shape of the next contract boundary:

1. Keep SQLite as the resumable source-of-truth graph builder.
2. Make edge identity action-preserving, even when symmetry maps different legal
   moves to the same canonical child.
3. Replace human move text in hot graph tables with compact `action_index`
   values.
4. Use dense integer `node_id` references for edges instead of repeated
   canonical keys.
5. Consider `WITHOUT ROWID` tables and archive/probe formats for compact
   distribution.
6. Define `searched_depth` semantics strongly enough that resume tooling can
   distinguish terminal proof, horizon discovery, and expandable non-terminal
   work.

This note bridges the observed Rust data into concrete contract and
implementation work. It is intentionally narrower than the earlier research
essays: it exists to prevent the next implementation round from optimizing the
wrong thing.

## Observed Evidence

The latest local run generated a depth-7 SQLite opening book:

| Metric | Value |
| --- | ---: |
| Total positions | 5,943,140 |
| Total edges | 22,271,192 |
| Elapsed time | 453.320 s |
| Throughput | 13,110 positions/s |
| SQLite file size | 3,755,429,888 bytes |

Per-depth shape:

| Depth | Positions | Terminal | Edges | Symmetry sum | Searched >= 1 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1 | 0 | 3 | 1 | 1 |
| 1 | 3 | 0 | 51 | 64 | 3 |
| 2 | 51 | 0 | 1,422 | 3,392 | 51 |
| 3 | 726 | 0 | 21,522 | 83,776 | 726 |
| 4 | 10,958 | 12 | 317,682 | 1,694,240 | 10,958 |
| 5 | 106,216 | 584 | 2,739,766 | 19,346,688 | 106,216 |
| 6 | 919,688 | 17,772 | 19,190,746 | 174,516,480 | 919,688 |
| 7 | 4,905,497 | 247,032 | 0 | 939,863,424 | 0 |

The depth-7 row has zero outgoing edges because it is the generation horizon.
Those positions are discovered but not expanded. The resume target for depth 8
therefore needs to revisit non-terminal horizon rows and any earlier rows whose
remaining searched budget is insufficient.

## Contract Lessons

### Compact Edge Storage

Edges dominate the generated book. The first implementation stores enough
information to inspect and resume, but not in the shape an engine should probe.

The long-term source table should use:

```sql
CREATE TABLE edges (
  parent_node_id INTEGER NOT NULL,
  action_index INTEGER NOT NULL,
  child_node_id INTEGER NOT NULL,
  edge_flags INTEGER NOT NULL,
  transform_id INTEGER,
  PRIMARY KEY (parent_node_id, action_index, child_node_id)
) WITHOUT ROWID;
```

The hot path should avoid repeated `parent_key` and `child_key` blobs. Canonical
keys still belong in `positions`; edges should join through dense ids.

### Encoded Moves

`opening-book.v1` already defines `action_index = shape * 16 + position`.
Generation tables should use that as the stable move identity. Human-readable
move strings can be derived for debug output or stored in an optional view.

This gives the engine one compact, language-neutral move encoding and prevents
text formatting from becoming part of book semantics.

### Action-Preserving Edge Identity

Symmetry can map different legal moves from the same parent to the same
canonical child. A table keyed only by `(parent, child)` loses information: it
collapses distinct legal actions into one edge.

The semantic edge identity must therefore include the action:

```text
edge_identity = (parent_canonical_position, action_index, child_canonical_position)
```

This may increase edge counts compared with a collapsed transposition graph, but
it is required for legal move reconstruction, policy training, opening-line
naming, puzzle generation, and explanation of forced defenses.

If a compact archive wants one child entry with multiple actions, it must still
preserve the action set.

### Builder, Analytics, And Probe Artifacts

The contract should preserve three distinct storage roles:

| Role | Recommended format | Purpose |
| --- | --- | --- |
| Builder graph | SQLite | resumable enumeration, graph integrity, local inspection |
| Observations and games | Parquet | search traces, h2h games, Elo calibration, training data |
| Engine probe | packed binary or memory-mapped arrays | fast lookup, small distribution artifact |

The packed probe artifact should be derived from the SQLite source. It should
not become the only source of truth until migration and validation tooling can
round-trip it back to the contract concepts.

### Stronger Resume Semantics

The current `searched_depth` field is useful but easy to misread. It can mean
"this row was proven terminal immediately" or "this row has been expanded to a
remaining search budget." For resumable generation, the next contract iteration
should make the state explicit.

Recommended fields:

```text
depth_ply
is_terminal
terminal_winner
expanded_to_remaining_depth
search_status
last_generator_run_id
updated_at
```

Recommended `search_status` values:

```text
discovered
terminal_proven
expanded
horizon
stale
error
```

Resume selection for target depth `D` should be expressible as:

```text
needs_search(node, D) =
  !node.is_terminal
  && node.expanded_to_remaining_depth < (D - node.depth_ply)
```

Terminal rows may have proof metadata, but they should not be counted as
expandable work.

## Next Implementation Slice

The next Rust implementation PR should be narrow and measurable:

1. Add `action_index` to generation edges.
2. Change the edge primary key to include the action.
3. Assign dense `node_id` references during insertion.
4. Add or migrate explicit resume fields.
5. Add an inspector check that reports action-collapsed duplicates.
6. Generate a small depth book in both old and new layouts and compare size.
7. Report bytes per position and bytes per edge in the PR description.

Success criteria:

- no legal move is lost when multiple actions map to the same canonical child,
- resume counts distinguish terminal rows from expandable rows,
- depth-6/depth-7 storage size is materially lower for the same semantics,
- the engine-facing contract remains independent from SQLite implementation
  details.

## Open Questions

- Should `node_id` be stable across independently generated books, or only
  stable within one artifact?
- Should packed probe artifacts use sorted adjacency arrays, perfect hashing, or
  a B-tree-like page layout?
- Do we need transform metadata on every edge, or can it be derived at probe
  time from the input position and canonical representative?
- What is the smallest policy payload that preserves enough playing strength:
  best move only, top-k priors, or full legal distribution?

These should be answered with generated size measurements rather than taste.
