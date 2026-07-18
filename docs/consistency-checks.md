# Consistency Checks

This repository provides three kinds of checks.

## Contract Repository Checks

The default CI validates:

- `VERSION` matches `contracts.json.release_version`.
- `contracts.json` references existing docs and schemas.
- JSON files parse.
- JSON Schemas have the expected top-level structure.
- Golden JSONL fixtures satisfy the stdlib validator.
- Fixture `schema` and optional `contract_version` fields match the manifest.

Workflow:

```text
.github/workflows/validate-contracts.yml
```

Tag release packaging:

```text
.github/workflows/release-contracts.yml
```

The release workflow re-runs the same validator against the tag version before
uploading the contract archive and checksum to the GitHub Release.

## Fixture Validation From Consumer Repositories

Consumer repositories can validate their own generated fixtures by checking out
this repository and running the stdlib validator directly:

```yaml
- uses: actions/checkout@v4
  with:
    path: caller
- uses: actions/checkout@v4
  with:
    repository: mberlanda/quantik-core-contracts
    ref: v1.2.0
    path: contracts
- working-directory: caller
  run: |
    python3 ../contracts/scripts/validate_contracts.py \
      --fixture-glob "tests/fixtures/**/*.jsonl" \
      --expected-release 1.2.0
```

This is intentionally dependency-light. It does not require `jsonschema`,
`pyarrow`, or either Quantik implementation.

`expected-release` should match the contracts release declared by the
implementation under test. When fixtures include `contract_version`, the script
rejects rows that drift from that release.

## Cross-Language Producer/Consumer Smoke

Consumer repositories can produce an artifact, validate it against
`selfplay.v1`, and then feed it to another implementation:

```yaml
- uses: mberlanda/quantik-core-contracts/actions/cross-language-smoke@v1.2.0
  with:
    artifact-path: "build/selfplay-smoke.jsonl"
    producer-command: "cargo run --bin quantik-selfplay -- --rows 8 --output build/selfplay-smoke.jsonl"
    consumer-command: "python -m quantik_core.ml_data build/selfplay-smoke.jsonl"
    expected-release: "1.2.0"
```

The action performs:

```text
producer -> contract validation -> consumer
```

The producer and consumer commands are owned by the caller repository because
CLI names may differ across crates/packages.

## API Portability Testing

`docs/api-portability-testing.md` defines the next portability-testing layer:
golden game-state/move/symmetry fixtures, implementation-produced normalized
reports, and cross-stack report comparison. This should become the main
Python/Rust API parity gate once both implementations expose report commands.

## Current Implementation Parity

`docs/implementation-status.md` is the live status page for registered
contracts. As of release `1.2.0`, the active end-to-end parity surfaces are:

- `opening-book-summary.v1`: Rust and Python emit comparable summary JSON and
  the contracts package validates/compares those summaries.
- `observation.v1`: Rust emits JSONL/debug rows and Rust/Python both validate
  release `1.2.0`, bitboards, legal masks, policy visits, and scalar fields.
- `game-result.v1`: Rust emits JSONL/debug rows and Rust/Python both validate
  release `1.2.0`, winners, plies, action indices, and required engine fields.
- `model-checkpoint.v1`: Rust and Python both parse and validate manifest JSON.

Large Parquet paths and full opening-book graph validators remain follow-up
work.

## Periodic Latest-Release Checks

The scheduled workflow is present but gated by repository variables:

```text
ENABLE_RELEASE_SMOKE=true
PYTHON_PACKAGE=quantik-core
RUST_CRATE=quantik-core
```

When enabled, it installs the latest published Python package and Rust crate,
then runs small import/command smoke checks. This should be switched on after
the Rust crate has a stable published name.

The release smoke should eventually assert that each implementation exposes the
same `contracts.json.release_version` and supported wire contract IDs.

## Future Strict Checks

The next contract increments should add:

- Arrow schema validation.
- Parquet metadata checks.
- Cross-repo generated artifact checks using a known Rust exporter and Python
  importer.
- API portability fixtures and report comparison for Python/Rust parity.
- Canonical orbit fixtures for D4 symmetry.
- Roundtrip checks:
  `Rust export -> Python import -> Python export -> Rust import`.
