# Model Checkpoint v1

`model-checkpoint.v1` defines metadata for Quantik neural or statistical model
artifacts. It does not standardize one training framework. It standardizes how a
runtime can understand the model's input/output contracts, hashes, quantization,
and provenance.

## Scope

Use this contract for:

- policy/value neural checkpoints,
- compact evaluator manifests,
- model calibration reports,
- runtime compatibility checks.

Do not store model weights directly in the contracts repository. Store only
small manifests and fixtures.

## Required Fields

```text
schema: model-checkpoint.v1
contract_version: 1.1.0
model_id: string
model_family: string
created_at: timestamp or ISO-8601 string
input_contracts: list<string>
output_contract: string
weights_format: string
weights_hash: string
size_bytes: uint64
training_data_manifest: string
calibration_report: string
```

Optional fields:

```text
feature_hash
quantization
parameter_count
architecture
legal_action_mask_required
recommended_engine_order
notes
```

## Recommended Output Contract

Policy/value models should produce:

```text
policy_logits: fixed_size_list<float32, 64>
value: float32
confidence: optional float32
```

The runtime must apply the legal action mask before selecting or sampling a
move. A model may learn legality, but legality remains a rules-engine
responsibility.

## Quantization

Recommended values:

```text
float32
float16
int16-accumulator/int8-dense
int8
```

Quantized models must record whether quantization-aware training was used.

## Weights Format

Recommended values:

```text
safetensors
onnx
npz
custom-binary
```

Runtime engines may support only a subset. Unsupported `weights_format` values
must fail fast with a clear message.

## Compatibility Rules

Readers must reject:

- unknown required schema versions,
- missing input/output contracts,
- unsupported weights format,
- missing weights hash,
- non-positive size,
- checkpoints whose input contracts are unsupported by the runtime.

Readers may ignore:

- optional architecture notes,
- optional calibration-report details,
- optional training notes.
