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

## Demonstrated 2026-09-20: a one-sided release bump no longer deadlocks the opening-book check

The circular wait from the 1.2.0 release was: the Python PR's opening-book
consistency job compared its summary to the Rust stack's `main`, the equality
included `contract_version`, so a PR that moved one stack's version was red until
the other stack had already moved. Neither could merge first.

Scenario: the Rust summary comes from a sibling `main` still on `1.3.0`; the
Python summary, from a PR that touches only Python, reports `contract_version`
`1.4.0`. Contracts stays on `1.3.0`, no tag is cut. Both summaries carry the real
depth-4 shape (11739 positions, 12 terminal, 340680 edges). The command is the
one `actions/opening-book-consistency` runs when `expected-release` is unset,
which is how quantik-core-py's `contracts.yml` calls it. The summaries are
hand-built to that shape, not generated by the engines; this demonstrates the
validator's policy, not a full run of both stacks' CI.

Post-fix, contracts `main` at `7e3889e` (and the `v1.3.0` tag, which quantik-core-py
pins, behaves identically):

```text
$ python3 scripts/validate_opening_book_summary.py \
    --rust-summary rust-summary.json --python-summary python-summary.json --expected-depth 4
opening-book-summary.v1 consistency passed: depth=4 positions=11739 edges=340680 rust_contract_version=1.3.0 python_contract_version=1.4.0
exit=0
```

Control, the same inputs against the `v1.2.0` validator (the deadlocked one):

```text
opening book summary validation failed: summaries differ between Rust and Python
exit=1
```

The check did not go blind. An explicit `--expected-release 1.3.0`, which only
release-time jobs pass, still rejects the same Python summary:

```text
opening book summary validation failed: .../python-summary.json: contract_version 1.4.0 does not match 1.3.0
exit=1
```

And a real graph difference (one extra depth-4 edge in the Python summary) still fails:

```text
opening book summary validation failed: summaries differ between Rust and Python
exit=1
```

The contracts repository's own CI check (`validate-contracts.yml`) passes with its
CI arguments: `contract validation complete: 24 json files, 42 fixture rows`.

Not covered here: quantik-core-py's separate `validate-contract-fixtures` job
passes `--expected-release 1.3.0` against a checkout pinned to `v1.3.0`. That pin
moves only when someone edits both lines, so it is a deliberate release act and not
a cross-repository wait; it would only matter if the pin lagged a fixture bump.
