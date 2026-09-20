# Engine Response v1

Status: **registered** — schema `schemas/engine-response-v1.json`
(JSON Schema 2020-12), fixtures `fixtures/engine-response/*.jsonl`.

`engine-response.v1` is the JSON body an engine service returns for
[`engine-request.v1`](engine-request-v1.md). It captures the format actually
emitted today; reconciling the implementations is out of scope here
(initiative QW-019 decision D5; richer responses belong to QW-018).

## Fields

```text
schema           "engine-response.v1"     required
action_index     0..=63                   required
engine_kind      string                   required
engine_version   string                   required
elapsed_ms       non-negative integer     required
value            number                   optional
policy           64 numbers               optional
```

The top level is closed (`additionalProperties: false`). `value` and `policy`
are optional and the schema accepts their union.

## Which implementation emits what

- `quantik-api-rust/src/lib.rs` (`MoveResponse`): the five required fields,
  plus `value` for `mcts` and `beam`. `minimax` emits no `value`.
  `engine_kind` is the engine route (`minimax`, `mcts`, `beam`);
  `engine_version` is the quantik-core git revision.
- `quantik-models-py/src/quantik_models/play/service.py` (`choose_move`): the
  five required fields; `engine_version` is the opponent id (for example
  `minimax-d2`, `cpool@0`). Network opponents additionally emit `value` and
  `policy` (the network prior, 64 floats, from one extra forward pass, not MCTS
  visit counts). Classical opponents emit neither.

`value` perspective and scale are not pinned by v1 and differ by producer: the
Rust API's `value` is an engine-internal estimate (observed in `[-1, 1]`), the
Python service's is the mover-relative value head in `[-1, 1]`. `win_probability`
is **not** part of this response; the Python service emits it only in its
separate `quantik-play.analysis.v1` analysis response.

## Rename migration (initiative QW-019, decision D3)

Registered as the bare `engine-response.v1`. Servers must emit the bare name
from the release carrying the initiative. Before that both implementations
emitted `quantik.engine-response.v1`; the fixtures were captured then, with only
the `schema` value rewritten to the bare name.

## Fixtures

`fixtures/engine-response/engine-response-v1-captured.jsonl`: real responses
from `quantik-api-rust` (minimax, mcts, beam; with and without `config`) and
from the Python play service (`minimax-d2`, `beam-w32`, and the `cpool@0`
network opponent which carries `value` and `policy`), captured by driving the
visualizer's `createRemoteEngine` against locally running servers.
