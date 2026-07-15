# End-to-End Data Pipeline

This runbook describes the reproducible path from contract validation to model
training inputs. Rust produces game/search artifacts, Python core validates and
converts them, and `quantik-models-py` materializes model-training views.

## Repositories

```bash
export CONTRACTS=/Users/mauroberlanda/Code/quantik-ns/quantik-core-contracts
export RUST=/Users/mauroberlanda/Code/quantik-ns/quantik-core-rust
export CORE_PY=/Users/mauroberlanda/Code/quantik-ns/quantik/quantik-core-py
export MODELS=/Users/mauroberlanda/Code/quantik-ns/quantik-models-py
export RUN_ID=smoke-$(date +%Y%m%d-%H%M%S)
export OUT=$MODELS/outputs/$RUN_ID
mkdir -p "$OUT"
```

## Setup

```bash
cd "$MODELS"
test -d .venv || python -m venv .venv
.venv/bin/python -m pip install -e "${CORE_PY}[arrow]"
.venv/bin/python -m pip install -e ".[dev,arrow]"
```

## One-Command Smoke

`quantik-models-py` provides the orchestrator:

```bash
cd "$MODELS"
scripts/run_smoke_pipeline.sh
```

The script runs the same steps listed below with small defaults.

## Manual Steps

1. Validate contracts:

```bash
cd "$CONTRACTS"
python3 scripts/validate_contracts.py   --manifest contracts.json   --version-file VERSION   --schema-glob 'schemas/*.json'   --fixture-glob 'fixtures/**/*.jsonl'   --expected-release "$(cat VERSION)"
```

2. Build an opening book, usually depth 6 for the first model loop:

```bash
cd "$RUST"
scripts/generate_opening_book.sh search   --depth 6   --db "$OUT/opening-book.sqlite"
```

3. Generate positions using the book for reference reuse/writeback:

```bash
scripts/generate_positions.sh   --opening 16   --early-mid 16   --late-mid 16   --endgame 16   --solve-budget 30   --book "$OUT/opening-book.sqlite"   --output "$OUT/positions-v1.json"
```

4. Generate observations across engines:

```bash
scripts/generate_observations.sh   --dataset "$OUT/positions-v1.json"   --output "$OUT/observations-bundle.json"   --checkpoint-dir "$OUT/observations-ckpt"   --engines mcts,minimax,beam   --mcts-iterations 1500   --minimax-depth 6   --beam-width 64   --seeds 10   --workers 4

scripts/export_contract_rows.sh   --input "$OUT/observations-ckpt"   --dataset "$OUT/positions-v1.json"   --observations-output "$OUT/observations-v1.jsonl"
```

5. Generate H2H evidence and game-result rows:

```bash
scripts/generate_h2h_stats.sh run   --dataset "$OUT/positions-v1.json"   --output "$OUT/h2h-bundle.json"   --checkpoint-dir "$OUT/h2h-ckpt"   --report-output "$OUT/h2h-report.md"   --engines mcts,minimax   --h2h-positions 50   --h2h-seeds 10   --mcts-iterations 1500   --minimax-depth 6   --workers 4

scripts/export_contract_rows.sh   --input "$OUT/h2h-ckpt"   --dataset "$OUT/positions-v1.json"   --games-output "$OUT/game-results-v1.jsonl"
```

6. Generate MCTS self-play rows:

```bash
cargo run --release --example selfplay_export --   --games 100   --iterations 2000   --seed 20260713   --out "$OUT/selfplay-v1.jsonl"
```

7. Materialize model-training views:

```bash
cd "$MODELS"
PYTHONPATH="$CORE_PY/src:$MODELS/src" python -m quantik_models.data.materialize   --observations-jsonl "$OUT/observations-v1.jsonl"   --output-npz "$OUT/training-view-observations.npz"

PYTHONPATH="$CORE_PY/src:$MODELS/src" python -m quantik_models.data.materialize   --selfplay-jsonl "$OUT/selfplay-v1.jsonl"   --output-npz "$OUT/training-view-selfplay.npz"
```

## Output Map

| File | Owner / purpose |
| --- | --- |
| `opening-book.sqlite` | `opening-book.v1` source of book/reference knowledge. |
| `positions-v1.json` | Rust benchmark positions artifact. |
| `observations-v1.jsonl` | `observation.v1` policy/value/search rows. |
| `game-results-v1.jsonl` | `game-result.v1` H2H evidence. |
| `selfplay-v1.jsonl` | `selfplay.v1` MCTS autoplay rows. |
| `training-view-observations.npz` | `quantik-models-py` derived observation training view. |
| `training-view-selfplay.npz` | `quantik-models-py` derived self-play training view. |

## Current Gaps

- Book-guided autoplay through depth 6 needs a Rust self-play runner with
  `--book`, `--opening-policy`, engine-pair selection, and provenance.
- `search-summary.v1` remains proposed until real root counters and Q-values are
  exported consistently.
- `opening-probe.v1` or equivalent compact probe metadata is needed before
  shipping engine-facing book/model probe artifacts.
