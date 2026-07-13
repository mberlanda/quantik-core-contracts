# Doing Better Than A Larger Opening Book

Date: 2026-07-13

Status: research note for contract design

## Abstract

The previous scale note showed that Quantik can plausibly store millions of
canonical positions, but it also exposed a sharper question: how do we maximize
playing and explanatory strength per byte? The answer is not simply a larger
opening book. Quantik should combine a canonical directed acyclic graph (DAG),
exact solved slices, search observations, compact learned evaluation, and a
separate human theory layer.

This note expands each improvement point independently. It argues that the
opening-book project should become a knowledge system with five jobs:

1. Preserve exact graph facts.
2. Measure uncertainty and forcedness.
3. Learn compact policy/value functions from search.
4. Serve fast engine probes.
5. Support human names, defenses, puzzles, and book writing.

## Point 1: The Primitive Is A Canonical Graph, Not A Move List

Let raw legal positions be $S$ and canonicalization be:

```text
c: S -> V
```

where $V$ is the set of canonical representatives under Quantik symmetries. The
opening book should store a graph:

```text
G = (V, E)
E = {(c(s), a, c(T(s, a)))}
```

where $T(s,a)$ applies legal action $a$ to state $s$.

This matters because different histories can reach the same canonical state.
If we store histories, the data grows like a tree. If we store canonical states,
the data grows like a DAG. A tree is useful for storytelling; a DAG is the
correct compute substrate.

The current local census already demonstrates the compression pressure:
canonical nodes through depth 8 are about 23.6 million, while raw ongoing
transitions at depth 8 are about 2 trillion. The graph is not a micro
optimization; it is the difference between a practical research artifact and an
unbounded history archive.

Contract implication:

- `opening-book.v1` should define canonical node identity, legal edge identity,
  and symmetry transform metadata.
- QFEN remains an inspection format, not the hot lookup key.
- Edges should carry action, child, policy, counts, and transform safety data.

## Point 2: Store Uncertainty, Not Only Best Moves

A best-move table hides why a move is best. Quantik needs a richer node and edge
model:

```text
node(s) = {
  value_mean,
  value_confidence,
  solved_status,
  policy_entropy,
  forcedness,
  source,
  generation_budget
}
```

For a recommender, `value_confidence` may be as important as `value_mean`. A
move with estimated value $0.82$ from shallow search may be less trustworthy
than a move with value $0.74$ from exact retrograde propagation.

For search, a useful edge score is:

```text
score(s, a) = Q(s, a) + U(s, a)
```

A PUCT-style exploration term is:

```text
U(s, a) = c_{puct} P(s, a) \frac{\sqrt{\sum_b N(s,b)}}{1 + N(s,a)}
```

where $P(s,a)$ is the policy prior, $N(s,a)$ is the edge visit count, and
$Q(s,a)$ is the current value estimate. This is the policy-guided search pattern
used by AlphaZero-style engines and Lc0-style engines.

Contract implication:

- Policy is not just a ranked move list. It needs priors, visits, source, and
  entropy.
- Value should have a provenance and confidence field.
- Forced moves should be represented explicitly, because a forced defense and a
  high-probability preference are different concepts.

## Point 3: Exactness Should Be A Solved Slice, Not A Universal Promise

Quantik has no draws in the current self-play contract, so a terminal position
can be represented as a win/loss value. For nonterminal positions, exact
retrograde logic has the zero-sum recurrence:

```text
V(s) = max_{a in Legal(s)} -V(T(s, a))
```

with terminal states evaluated from the side-to-move perspective.

This recurrence is simple, but computing it naively for every position is not.
The current depth-4 exact-solve pilot estimated about 12.7 days because each
position was solved too independently. A shared DAG solver changes the shape of
the problem:

1. Generate canonical nodes once.
2. Generate legal edges once.
3. Mark terminals.
4. Propagate exact values backward through the DAG.
5. Cache partial bounds and proof status.

This mirrors the tablebase lesson from chess. Stockfish uses optional Syzygy
WDL/DTZ tablebase probing for exact endgame knowledge, while normal strength
still comes from search and evaluation. Quantik should adopt the separation:
exact solved slices are probeable artifacts, not the whole engine.

Contract implication:

- `solved_status` should distinguish `unsolved`, `bounded`, `exact`,
  `tablebase`, and `inferred`.
- WDL-like value is the first exact target.
- Distance-to-proof is valuable for puzzles and book writing, but it can be
  selective rather than universal.

## Point 4: Search Traces Are Training Data, Not Book Rows

Engine observations should be stored as analytical data, not embedded directly
into the SQLite opening book. A training row is:

```text
D_i = (x_i, \pi_i, z_i, w_i, m_i)
```

where:

- $x_i$ is the encoded position.
- $\pi_i$ is the search-improved policy target.
- $z_i$ is the value target from exact solve, game result, or search value.
- $w_i$ is a confidence or sample weight.
- $m_i$ is the legal action mask.

The model objective can be:

```text
L(\theta) =
  \lambda_v w_i (v_\theta(x_i) - z_i)^2
  - \lambda_p \sum_a \pi_i(a) \log p_\theta(a | x_i)
  + \lambda_u (u_\theta(x_i) - w_i)^2
```

where $v_\theta$ is the value head, $p_\theta$ is the policy head, and
$u_\theta$ is an optional confidence head.

This converts expensive search into a compact evaluator. If the evaluator is
small enough to run at every search leaf, the system gets stronger outside the
stored opening book.

Contract implication:

- Observations need a bulk format with fixed policy vectors, engine metadata,
  checkpoint ids, budgets, and seeds.
- Parquet is better than SQLite for this layer because observations are scanned,
  filtered, joined, and batched for training.
- SQLite should keep aggregated graph facts, not raw per-run trace rows.

## Point 5: Graph Search Beats Tree Search For Quantik

AlphaZero-style MCTS traditionally expands a tree. Quantik has dense
transpositions and symmetries, so a DAG search is more natural. Monte-Carlo
Graph Search generalizes tree search to a DAG, allowing shared values across
transpositions and reducing duplicate evaluations.

For Quantik, the graph-search advantage is amplified:

- The board is small.
- Symmetry canonicalization is already part of the contract.
- Many move orders can collapse to the same canonical state.
- A search engine can reuse opening-book nodes directly.

A practical search node can store:

```text
node_key
value_estimate
node_visits
out_edges: [
  action,
  child_key,
  prior,
  edge_visits,
  edge_q
]
```

The important detail is that both node and edge statistics are useful. Node
statistics capture transposition-level knowledge; edge statistics preserve the
parent-specific decision context.

Contract implication:

- Opening-book edge stats and MCTS edge stats should share vocabulary.
- Runtime search caches should be exportable into observation rows.
- The book should not force tree-only principal variations.

## Point 6: A Small Model Can Be A Better Database

A database memorizes. A model generalizes. If a 70 MB evaluator improves move
ordering and leaf evaluation everywhere, it may produce more strength than a 70
GB book that only helps inside stored coverage.

The model does not replace exact knowledge. It compresses patterns from exact
knowledge and search. The winning architecture is layered:

```text
book probe -> model eval -> graph search -> observation export -> retraining
```

This creates a feedback loop. The opening book teaches the model. The model
guides search. Search finds gaps. The gaps produce new observations. The book
and model both improve.

The active-learning version of this loop should deliberately sample archived
states of interest rather than only replaying from the empty board. That mirrors
the motivation in targeted AlphaZero search-control work: varied start states
can expose deeper parts of the game tree and produce more independent value
targets.

Contract implication:

- Model checkpoints need metadata: input contract, output contract, training
  data manifest, calibration set, quantization type, and hash.
- The contracts should define model I/O before blessing a specific neural
  architecture.

## Point 7: Human Theory Should Be Sparse And Editorial

The goal includes named openings, defenses, puzzles, and eventually a book in
the chess sense. That layer should not be mixed into every graph node.

Human theory is a sparse overlay:

```text
line = {
  line_id,
  name,
  family,
  root_node,
  principal_variation,
  refutations,
  tags,
  notes,
  curator,
  evidence
}
```

This lets the machine layer remain compact while the human layer stays legible.
An opening can be a path. A defense can be a reply set. A puzzle can be a
subgraph with a target tactic and a proof line.

Contract implication:

- Names should point to canonical nodes and action sequences.
- Human annotations should cite evidence: exact solve, MCTS tournament,
  engine agreement, or curator judgment.
- The annotation layer should be versioned separately from the engine probe
  layer.

## Point 8: Elo Must Be Measured Against Roles

The previous note used Elo proxy ranges. Those are planning estimates, not
ratings. The contract should support later measurement.

If engine A scores $S$ against engine B, the Elo difference estimate is:

```text
\Delta = 400 \log_{10} \frac{S}{1-S}
```

where wins count as 1, losses as 0, and draws would count as 0.5 if a future
contract introduced them. Current Quantik self-play has no draws, so $S$ is the
win rate.

But there are multiple roles:

- Player strength: wins under fixed wall-clock and hardware.
- Recommender strength: top-k move quality against stronger search.
- Puzzle strength: ability to identify forced lines and traps.
- Theory strength: ability to produce stable named openings and defenses.

Contract implication:

- H2H results need engine ids, checkpoint ids, time budgets, seeds, opening
  seeds, and hardware notes.
- Recommender evaluations need top-k accuracy and regret against a stronger
  reference engine.
- Puzzle evaluations need proof depth, uniqueness, and failure modes.

## Point 9: Storage Tiers Should Match Access Patterns

One storage engine should not own every artifact. The better split is:

| Artifact | Best initial storage | Reason |
| --- | --- | --- |
| Golden fixtures | JSONL | Diffable, readable, CI-friendly. |
| Opening-book graph | SQLite | Local ACID graph/index store. |
| Observations and games | Parquet | Columnar scans, compression, ML batching. |
| Ad-hoc analytics | DuckDB over Parquet | Embedded OLAP and SQL exploration. |
| Engine probe | Compact key-value/tablebase artifact | Fast lookup and mmap-friendly reads. |
| Model | Quantized checkpoint plus manifest | Generalization per byte. |
| Named theory | SQLite or JSON/Markdown overlay | Curatable human layer. |

Apache Parquet is designed as a column-oriented file format for efficient bulk
storage and retrieval. That matches observations. SQLite is a transactional
local store. That matches graph truth and resumability. Stockfish/Syzygy shows
that engine probes should eventually be specialized binary artifacts, not
general-purpose analytical tables.

## Adoption Thesis

The optimal path is:

1. Define contracted graph and observation artifacts.
2. Generate complete depth-6 graph data and selective deeper data.
3. Run engines to produce Parquet observations.
4. Train a sub-100MB policy/value evaluator.
5. Integrate book probe plus evaluator into MCTS/beam/minimax.
6. Measure H2H and recommender Elo proxy.
7. Name openings and defenses from stable, evidence-backed graph regions.

This does better than a larger opening book because it turns every expensive
computation into reusable structure:

- exact facts in the graph,
- statistics in observations,
- compressed expertise in the model,
- fast decisions in the probe,
- and human meaning in the annotation layer.

## References

- David Silver et al., "Mastering Chess and Shogi by Self-Play with a General
  Reinforcement Learning Algorithm", arXiv:1712.01815:
  https://arxiv.org/abs/1712.01815
- Johannes Czech, Patrick Korus, Kristian Kersting, "Monte-Carlo Graph Search
  for AlphaZero", arXiv:2012.11045: https://arxiv.org/abs/2012.11045
- Alexandre Trudeau, Michael Bowling, "Targeted Search Control in AlphaZero for
  Effective Policy Improvement", arXiv:2302.12359:
  https://arxiv.org/abs/2302.12359
- Leela Chess Zero technical explanation:
  https://lczero.org/dev/wiki/technical-explanation-of-leela-chess-zero/
- Stockfish UCI and Syzygy options:
  https://official-stockfish.github.io/docs/stockfish-wiki/UCI-%26-Commands.html
- Stockfish Syzygy probing source:
  https://github.com/official-stockfish/Stockfish/blob/master/src/syzygy/tbprobe.cpp
- Official Stockfish NNUE PyTorch documentation:
  https://github.com/official-stockfish/nnue-pytorch/blob/master/docs/nnue.md
- Apache Parquet overview: https://parquet.apache.org/docs/overview/
- Quantik companion note:
  [Opening Book Scale, Storage, and Proficiency Tradeoffs](2026-07-13-opening-book-scale-and-storage.md)
