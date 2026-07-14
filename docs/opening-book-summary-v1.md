# Opening Book Summary v1

`opening-book-summary.v1` is a small cross-stack consistency artifact. It is not
the opening book itself. It records enough aggregate graph shape to verify that
Rust generation and Python consumption agree on canonical positions, terminals,
and legal outgoing edges for a bounded smoke depth.

The default consistency depth is 4.

Required fields:

```text
schema = opening-book-summary.v1
contract_version
depth
total_positions
terminal_positions
total_edges
per_depth
```

Each `per_depth` row contains:

```text
depth
positions
terminal
edges
```

The totals must equal the sums of the per-depth rows. Consumers should reject
missing rows, negative counts, terminal counts larger than position counts, and
any schema or release mismatch.

Use this summary for CI drift detection. Use `opening-book.v1` for the graph,
`observation.v1` for search observations, and `game-result.v1` for completed
head-to-head games.
