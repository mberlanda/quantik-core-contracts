# 50-100MB Policy/Value Model Project

The model project lives in `quantik-models-py`. The core libraries do not vendor
model weights, training loops, architecture experiments, PyTorch, or ONNX
runtime dependencies. They only preserve APIs for reading, validating, and
feeding model artifacts.

## Target

| Property | Target |
| --- | --- |
| Size | 50-100 MB including weights and manifest. |
| Inputs | `tensor-board.v1`, `bitboard.v1`, `action-index.v1`, side-to-move, legal action mask. |
| Outputs | Policy over 64 actions and scalar value in `[-1, 1]`. |
| Training repo | `quantik-models-py`. |
| Runtime handshake | `model-checkpoint.v1` manifest plus weights artifact. |
| Core behavior | Validate manifest, expose game/artifact APIs, fail fast on unsupported formats. |

## Why It Can Beat A Larger Book

A large book memorizes known positions. A compact evaluator can generalize to
nearby and unseen states, then search can refine its suggestions. The intended
loop is:

```text
opening book depth 6 -> search observations -> training view -> model checkpoint
        ^                                                        |
        |                                                        v
new H2H/autoplay disagreements <- model-guided search <- checkpoint eval
```

The opening book supplies high-confidence early knowledge; MCTS/beam/minimax
supply policy and tactical labels; autoplay supplies new states where the model
is weak.

## Data Milestones

1. Build or refresh a depth-6 opening book.
2. Generate positions with `generate_positions.sh --book` so solved references
   are reused and written back.
3. Generate observations across MCTS, minimax, and beam.
4. Export `observation.v1` and `game-result.v1` rows.
5. Export MCTS self-play as `selfplay.v1`.
6. Materialize training views in `quantik-models-py`.
7. Train a baseline policy/value model.
8. Export weights plus `model-checkpoint.v1` manifest.
9. Evaluate model-guided search against book-only/search-only baselines.

Current materialization command:

```bash
cd "$QUANTIK_NS/quantik-models-py"
quantik-models-materialize \
  --observations-jsonl /path/to/observations-v1.jsonl \
  --output-npz /path/to/training-view-observations.npz
```

## First Model Shape

The first portable model should stay simple:

- input tensor: `(9, 4, 4)` float32 planes,
- optional bitboard/hash side channel after the baseline works,
- shared trunk with small residual or MLP blocks,
- policy head: 64 logits masked by `legal_action_mask`,
- value head: one `tanh` scalar,
- calibration metadata recorded in `model-checkpoint.v1`.

The training framework is deliberately outside the contract. Exported
checkpoints should prefer ONNX or Safetensors once runtime support is selected.

## Autoplay Strategy

1. **Supervised bootstrap**: train from depth-6 book labels, observations, and
   MCTS self-play.
2. **Book-guided autoplay**: use opening-book moves through depth 6, then fall
   back to engine/model-guided search.
3. **Engine mixture**: rotate MCTS, minimax, beam, and model-guided variants to
   avoid overfitting one labeler.
4. **Active learning**: export positions where model policy and search policy
   disagree; relabel with stronger search or exact book/solver paths.
5. **H2H validation**: keep held-out book-frontier and non-book positions for
   model+search versus book-only/search-only comparisons.

Needed Rust producer work for richer autoplay:

- self-play runner supporting `--book PATH`, `--opening-policy`, and engine
  pairs,
- book/frontier start-position sampling,
- provenance for book-guided versus search-guided plies,
- later `search-summary.v1` rows with real root visits/Q-values/counters.

## Acceptance Gates

A checkpoint is useful only if it:

- validates through `model-checkpoint.v1`,
- loads in the intended runtime stack or fails fast with a clear unsupported
  format error,
- improves fixed-budget search on held-out positions,
- beats or ties static opening-book-only play on book-frontier H2H,
- keeps illegal move probability near zero after masking,
- has reproducible training data and calibration reports.
