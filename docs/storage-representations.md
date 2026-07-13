# Storage Strategies And Representations

Quantik data has multiple access patterns. No single storage format is optimal
for every job, so this repository defines when each format is appropriate.
The supported format IDs and release version are listed in `contracts.json`.

## JSONL

Use JSONL for:

- Golden fixtures.
- Small smoke-test artifacts.
- Human review in pull requests.
- Interchange while a schema is still settling.

Strengths:

- Readable and diffable.
- Easy to validate without native dependencies.
- Works everywhere.

Weaknesses:

- Large files.
- Slow parsing.
- Repeated field names.
- Poor tensor ingestion path for large training sets.

Decision:

`selfplay.v1.jsonl` is the canonical fixture format, not the production bulk
training format.

## CBOR

Use CBOR for:

- Compact binary messages.
- Local interchange where JSON size is painful but schema evolution is still
  lightweight.

Strengths:

- Smaller than JSON.
- Preserves familiar data model.

Weaknesses:

- Less inspectable.
- Less natural for columnar analytics and batch ML.

Decision:

CBOR is acceptable for API artifacts and compact smoke outputs, but it is not
the preferred long-term analytical store.

## Protobuf

Use protobuf for:

- Stable API messages.
- RPC control/configuration messages.
- Small-to-medium event streams.

Strengths:

- Strong schema.
- Good compatibility story.
- Mature Rust and Python tooling.

Weaknesses:

- Row-oriented serialization.
- Repeated decode overhead for training epochs.
- Less direct integration with NumPy, PyTorch, DuckDB, and Polars.

Decision:

Protobuf is not the primary bulk ML dataset format. It may be introduced for
configuration, RPC, or compact control-plane messages.

## Arrow IPC

Use Arrow IPC for:

- Fast language-neutral columnar exchange.
- Batch transfer from Rust generation to Python training/analysis.
- Memory-map friendly local datasets.

Strengths:

- Strong typed schema.
- Columnar and batch-oriented.
- Good Rust/Python support.

Weaknesses:

- Less convenient for long-term partitioned lake-style storage than Parquet.

Decision:

Arrow IPC is the preferred high-throughput interchange format once the JSONL
contract is stable.

## Parquet

Use Parquet for:

- Persisted generated self-play datasets.
- Sharded benchmark evidence.
- Analytical queries with DuckDB, Polars, Spark, Pandas, or PyArrow.
- Cloud storage.

Strengths:

- Compact with compression.
- Column pruning and predicate pushdown.
- Handles millions of rows well when written in batches/shards.

Weaknesses:

- Bad fit for single-row appends.
- Random per-row training reads can be less efficient than tensor stores.
- Nested sparse policies are compact but less direct for GPU batching.

Decision:

Parquet is the preferred persisted bulk-data format. Write batches/shards, not
single-row appends.

Recommended self-play columns:

```text
game_id: uint64
ply: uint16
side_to_move: uint8
bitboards: fixed_size_list<uint16, 8>
policy_visits: fixed_size_list<uint32, 64>
value: int8
qfen: optional utf8
```

Use dense `policy_visits[64]` for ML-oriented datasets. Sparse policy lists are
allowed for JSONL fixtures and compact debug exports.

## SQLite

Use SQLite for:

- Opening books.
- State DAGs.
- Resumable local enumeration.
- Indexed lookup by QFEN/canonical QFEN/depth/terminal status.

Strengths:

- Excellent local transactional store.
- Indexes and joins.
- Easy inspection.

Weaknesses:

- Not ideal for high-throughput tensor training.
- Less natural for columnar scans over millions of training rows.

Decision:

SQLite is preferred for graph/index workflows, not as the main ML training
corpus format. For opening-book scale and storage tradeoffs, see
[Opening Book Scale, Storage, and Proficiency Tradeoffs for Quantik](research/2026-07-13-opening-book-scale-and-storage.md).

## Tensor Stores

Use derived tensor stores for:

- Repeated training epochs.
- Random minibatch sampling.
- GPU-friendly input pipelines.

Recommended tensors:

```text
boards:   uint8 or float32 [rows, 9, 4, 4]
policies: uint16/uint32 or float32 [rows, 64]
values:   int8 or float32 [rows]
```

The tensor board channels are:

```text
0..3 = player 0 shapes A..D
4..7 = player 1 shapes A..D
8    = side_to_move plane, all 0.0 or all 1.0
```

Decision:

Tensor stores are derived artifacts. They must be reproducible from the
contracted JSONL/Arrow/Parquet representation.
