# Consistency Checks

This repository provides three kinds of checks.

## Contract Repository Checks

The default CI validates:

- JSON files parse.
- JSON Schemas have the expected top-level structure.
- Golden JSONL fixtures satisfy the stdlib validator.

Workflow:

```text
.github/workflows/validate-contracts.yml
```

## Reusable Fixture Validation

Consumer repositories can validate their own generated fixtures with:

```yaml
- uses: mberlanda/quantik-core-contracts/actions/validate-contracts@main
  with:
    fixture-glob: "tests/fixtures/**/*.jsonl"
```

This is intentionally dependency-light. It does not require `jsonschema`,
`pyarrow`, or either Quantik implementation.

## Cross-Language Producer/Consumer Smoke

Consumer repositories can produce an artifact, validate it against
`selfplay.v1`, and then feed it to another implementation:

```yaml
- uses: mberlanda/quantik-core-contracts/actions/cross-language-smoke@main
  with:
    artifact-path: "build/selfplay-smoke.jsonl"
    producer-command: "cargo run --bin quantik-selfplay -- --rows 8 --output build/selfplay-smoke.jsonl"
    consumer-command: "python -m quantik_core.ml_data build/selfplay-smoke.jsonl"
```

The action performs:

```text
producer -> contract validation -> consumer
```

The producer and consumer commands are owned by the caller repository because
CLI names may differ across crates/packages.

## Periodic Latest-Release Checks

The scheduled workflow is present but gated by repository variables:

```text
ENABLE_RELEASE_SMOKE=true
PYTHON_PACKAGE=quantik-core
RUST_CRATE=quantik-core-rust
```

When enabled, it installs the latest published Python package and Rust crate,
then runs small import/command smoke checks. This should be switched on after
the Rust crate has a stable published name.

## Future Strict Checks

The next contract increments should add:

- Arrow schema validation.
- Parquet metadata checks.
- Cross-repo generated artifact checks using a known Rust exporter and Python
  importer.
- Canonical orbit fixtures for D4 symmetry.
- Roundtrip checks:
  `Rust export -> Python import -> Python export -> Rust import`.

