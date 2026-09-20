# Engine Response v1

Status: **registered** — schema `schemas/engine-response-v1.json`
(JSON Schema 2020-12), fixtures `fixtures/engine-response/*.jsonl`.

`engine-response.v1` is the JSON body an engine service returns for
[`engine-request.v1`](engine-request-v1.md). It captures the format actually
emitted today; reconciling the implementations is out of scope here
(initiative QW-019 decision D5; richer responses belong to QW-018).

> **Design record (QW-018 W1), DECIDED 2026-09-20.** The sections below
> "Registered today" are unchanged. Everything from "Extended response:
> design" onward is the accepted design: no schema, fixture or server
> implements it yet (W2 to W4). Each of the five sections keeps its options and
> rejected alternatives; the option marked **RECOMMENDED** is the one that was
> **DECIDED** on 2026-09-20 (all five recommendations accepted as written).

## Decisions

All five decided 2026-09-20; each recommended option was accepted as written.

1. **Candidate shape (section 1): DECIDED.** `candidates: [{action_index,
   score, unit}]`, best first, per-candidate `unit`.
2. **PV shape (section 2): DECIDED.** Flat `pv` array of action indices whose
   first element is `action_index`.
3. **`certainty` (section 3): DECIDED.** Required, `estimate | proof`. Minimax
   earns `proof` only when every score in the response is proven.
4. **`engine_version` (section 4): DECIDED.** `model_id` for checkpoint-backed
   engines; for pure-core engines the identifier of the quantik-core build that
   ran (git revision where the server has one, installed release string where
   not), plus an optional `engine_config`. Versions are not comparable as
   strings across implementations; consumers key on `(engine_kind,
   engine_version, engine_config)` and never parse or diff the version.
5. **Compatibility (section 5): DECIDED.** Register `engine-response.v2` with
   `certainty` required; v1 stays frozen.

## Follow-ups

- **W2 (contracts):** register `schemas/engine-response-v2.json` and fixtures;
  v1 schema and fixtures untouched.
- **W3 (quantik-api-rust):** core accessor exposing per-root-move minimax
  scores (today only in `last_root_scored`, `minimax.rs:124`, `:240-251`), and
  an MCTS visit list that is not collapsed by the transposition table.
- **quantik-models-py:** pooling key changes from the opponent id to
  `(engine_kind, engine_version, engine_config)`; the play service sends
  `model_id` and `engine_config` per section 4.
- **W2, documentation:** when it registers the schema, W2 moves the "Extended
  response: design" half of this file to `docs/engine-response-v2.md`. Not
  renamed in this PR.
- **W4 (visualizer):** tolerate absent fields; absent `certainty` renders as
  unlabelled.

## Registered today (v1, unchanged)

### Fields

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

### Which implementation emits what

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

### Rename migration (initiative QW-019, decision D3)

Registered as the bare `engine-response.v1`. Servers must emit the bare name
from the release carrying the initiative. Before that both implementations
emitted `quantik.engine-response.v1`; the fixtures were captured then, with only
the `schema` value rewritten to the bare name.

### Fixtures

`fixtures/engine-response/engine-response-v1-captured.jsonl`: real responses
from `quantik-api-rust` (minimax, mcts, beam; with and without `config`) and
from the Python play service (`minimax-d2`, `beam-w32`, and the `cpool@0`
network opponent which carries `value` and `policy`), captured by driving the
visualizer's `createRemoteEngine` against locally running servers.

# Extended response: design

## Evidence this design rests on

- The Rust gateway builds `MoveResponse` with five required fields, `engine_version: CORE_REVISION`, and an
  optional `value` (`quantik-api-rust/src/lib.rs:94-102`, `:172-179`).
- `search_minimax` returns `Ok((result.best_move, None))` (`lib.rs:192`).
  `MinimaxResult` carries `score`, `depth_reached`, `nodes` and `pv`
  (`quantik-core-rust/crates/quantik-core/src/minimax.rs:76-83`); score and PV
  are thrown away at the call site.
- MCTS reports only `2.0 * win_probability - 1.0` (`lib.rs:205`); beam
  reports `leaf.value` flipped to the root mover's perspective
  (`lib.rs:227-232`) and discards `RankedRootMove` (`beam_search.rs:105-119`).
- The gateway rejects a client whose legal set differs from quantik-core's
  (`lib.rs:152`). Candidates are filtered by the server's own set, never the
  client's.
- Python: `choose_move` puts `opponent.opponent_id` in `engine_version`
  (`quantik-models-py/src/quantik_models/play/service.py:295-300`) and adds
  `value` and `policy` from `_assess` (`service.py:413-438`), which excludes
  opponents with no `model_id`.
- The visualizer reads exactly one field, `action_index`
  (`quantik-qfen-visualizer/src/engines.js:64-67`). It never checks
  `schema` and never reads `engine_version`. Any extra field is ignored.

## 1. Ranked candidates and their units (DECIDED 2026-09-20)

**Decided by the packet, not by this section:** scores stay in the engine's own
units, labelled (QW-018 decisions.md D2). Not normalised.

Constraints from the code. MCTS visit counts come from `root_move_visits`,
which with the default transposition table merges symmetric root moves and
silently omits the others (`mcts.rs:157-174`; the empty board's 64 moves
collapse to 3 entries). The core's minimax scores every root move with a full
`(-inf, +inf)` window (`minimax.rs:334-346`), so its per-move scores are
exact values within the searched depth, not bounds, and are kept in
`last_root_scored` (`minimax.rs:124`, `:240-251`) but not exposed on
`MinimaxResult`. The network gives 64 logits and one value per forward pass;
the existing Python `policy` is a masked prior (fixture rows sum to about 1
with zeros on illegal slots).

**Option A: array of `{action_index, score, unit}`, best first (RECOMMENDED, DECIDED).**

```json
"candidates": [
  {"action_index": 17, "score": 812,  "unit": "visits"},
  {"action_index": 43, "score": 301,  "unit": "visits"}
]
```

- `unit` is one of `visits`, `logit`, `prior`, `value`.
  - `visits`: non-negative integer count from the root.
  - `logit`: raw network output, unmasked scale, comparable only within one
    response.
  - `prior`: probability in `[0, 1]` (masked, renormalised policy).
  - `value`: mover-relative expected result in `[-1, 1]`; `1` is a forced win
    for the side to move at the root. Whether it is a guess or a proof is
    `certainty`'s job, never `unit`'s.
- Order is the engine's own ranking, best first; rank is the array index. A
  consumer never re-sorts by `score` across units.
- Only legal actions. The list is a ranked subset, not a partition of the
  legal set: consumers must not assume it is complete (see MCTS collapse
  above). A server states nothing about omitted moves.
- Entries in one response share one unit in practice; the field is per
  entry so a lone entry, or a copied fragment, is self-describing. A
  validator may enforce uniformity (W2's call). Mixed units in one list are
  reserved, not forbidden.
- Length cap: recommend at most 8 entries by default (matches
  `_top_moves` `limit=8`, `service.py:441`), never more than 64.
  `config` may raise it later; that is not specified here.
- The existing `policy` (64-slot vector) is kept unchanged. A `net-policy`
  response may emit both; `candidates` with `unit: prior` is the
  self-describing form, `policy` the dense one. No removal is proposed.

**Option B: one list-level unit** (`candidates_unit: "visits"`, entries are
`{action_index, score}`). Rejected: the packet asks for the unit to be labelled
per candidate, and a candidate lifted out of the list (into a log or a game
record) loses its unit. It is smaller on the wire; that is the only gain.

**Option C: a 64-slot vector like `policy`** with a `score_unit` sibling.
Rejected: cannot express rank or "not evaluated" without a sentinel (an
unvisited move and a zero-visit move are different claims), and it forces
every engine to invent 64 numbers. It suits dense training targets, which the
selfplay contract already covers.

**Rejected alternative shared by all options: normalising to probabilities.**
Already rejected in decisions.md D2; restated because it is tempting.
`(value + 1) / 2` is exact (no draws) and clients may derive it, but visit
counts and logits normalise differently and a normalised number hides its
producer.

Dependency for W3 (outside this item's paths): minimax and MCTS candidate
lists need new core accessors (a public root-move score list on
`MinimaxResult`; `root_move_visits` with `use_transposition_table: false` or
an orbit-expanding wrapper). This design does not require either to ship
first: an engine with no candidates simply omits the field.

## 2. Principal variation (DECIDED 2026-09-20)

**Option A: flat array of action indices, `pv` (RECOMMENDED, DECIDED).**

```json
"pv": [17, 40, 5, 33]
```

- Index 0 is the root mover's move and equals `action_index` whenever both
  are present. Later entries alternate sides. Every element is an
  `action-index.v1` value (`shape * 16 + position`, as `lib.rs:236-238`).
- A PV is a line the search believes best, not a claim of uniqueness. It may
  be shorter than the depth reached (transposition-table cutoffs), and may be
  empty only by omission, never as `[]`.
- Consumers verify by replay from the request position; a server must only
  send a line it could replay legally.

Engines with a PV today: `minimax` (`MinimaxResult.pv`, `minimax.rs:81`) and
`beam` (`best_leaf.moves`, `lib.rs:222-232`). Engines with none: `mcts` (the
result exposes no line, only a move and a win rate), `net-policy` (one
forward pass), `net-mcts`, `random`, `uniform-mcts`. For these the field is
omitted, never empty. This list is a statement about the pinned core
(`CORE_REVISION` `2b35565`); an engine that gains a line may start emitting it
without a contract change.

**Option B: array of `{action_index, side}`.** Rejected: `side` is derivable
from the root's `side_to_move` and parity; carrying it invites disagreement.

**Option C: a QFEN line (positions, not moves).** Rejected: 4 to 16 QFEN
strings per response where 4 to 16 bytes suffice, and the request already
gives the start position. Useful for debugging, not for the wire.

The PV inherits the response's `certainty`: a `proof` PV is a line that
realises the proven value; an `estimate` PV is a hunch. It carries no
certainty of its own.

## 3. `certainty` (DECIDED 2026-09-20)

**Decided (packet):**

- `certainty` is a **required** top-level field of the extended response.
- Exactly two values: `"estimate"` and `"proof"`. No third value, no number,
  no null, no absence.
- Every engine sets it on every response. An engine cannot omit it and cannot
  blur the two: it never reports `proof` on the strength of a heuristic, a
  network output or a sampled search.
- It qualifies every number in the response (`value`, `policy`, every
  `candidates[].score` with `unit: value`, and the PV), not only `value`.
- Assignment: a network `tanh` value is **always** `estimate`. Every MCTS
  value (visit-based or net-guided), every beam value, every network prior and
  logit is `estimate`. A result from an exhaustive search of the exact game
  tree, or from the exact oracle, is `proof`. The rest of this section
  decides only how `minimax` earns `proof`.

Why minimax needs a rule at all. `search_minimax` clamps `max_depth` to
`1..=16` with default 6 (`lib.rs:184`), so a default request is a heuristic
search that falls back to `evaluate` at the depth cutoff. Yet the core also
says a result is proven when the score is in the mate range,
`|score| >= win - 16` (`minimax.rs:98-107`), which can happen at any depth,
and depth 16 with no time limit always terminates on true terminal nodes
(`MinimaxEngine::solve`, `minimax.rs:150-160`).

**Option A: `proof` iff every score reported is proven (RECOMMENDED, DECIDED).**
`minimax` reports `proof` when the best move's score is mate-range or the
search ran to terminal depth without a time cut (`solve`), **and** every
`value`-unit candidate in the response is likewise proven; otherwise
`estimate`. Conservative and needs no per-entry mark. Its cost: a search that
proves the best move but leaves heuristic scores on the losing moves reads
as `estimate`. The server may recover `proof` by emitting only the proven
entries, or by omitting `candidates`.

**Option B: `proof` iff the headline claim (`action_index` and `value`) is
proven; candidates are advisory.** Rejected: a client that shows one badge for
the response would put `proof` next to a list containing heuristic numbers,
which is exactly the blur the field exists to prevent.

**Option C: `proof` only from a dedicated exact route** (e.g. an `oracle`
engine kind that calls `solve`), never from `minimax`. Simpler to state, and
`minimax` becomes `estimate` always. Rejected: it discards free proofs (a mate
found at depth 3 is a proof) and makes the same search return a different
label depending on a route name. Kept as a fallback if the core team does not
want to expose the mate-range test.

Extra rules, all options:

- Perspective is mover-relative, `[-1, 1]`, for `value`. `value` is currently
  "implementation-defined" in v1 and differs by producer (see above); the
  extended response pins it, and `proof` applies to that pinned value.
- `proof` about a value is not `proof` about uniqueness of `action_index`.
- A server that cannot decide, sends `estimate`. There is no default that
  favours `proof`.
- Terminal and legal-move-free positions never reach a response
  (`lib.rs:152` and the service refuse them).

## 4. `engine_version` (DECIDED 2026-09-20)

**The divergence, concretely.** Rust sends the git revision of
quantik-core, `2b35565dddc8e0f77222af2f8fcd382b013f2fee`, for every engine
(`lib.rs:21`, `:176`). Python sends the opponent id: `minimax-d2`,
`beam-w32`, `cpool@0` (`service.py:300`; fixture rows in
`fixtures/engine-response/engine-response-v1-captured.jsonl`). The two
strings answer different questions ("which code" versus "which configured
player"), and neither says which *network* played for a model engine unless
the opponent id is parsed (`{model_id}@0` for `net-policy`, `{model_id}@128`
for `net-mcts`, `opponents.py:157`, `:178`).

Two further facts shape the rule:

- The visualizer never reads this field (`engines.js:64-67`). The play app
  stamps `p*_engine_version` itself from `opponent.id` (`play/app/src/play.js:44-49`,
  `:171-173`), so recorded games do not depend on the response today. The
  divergence is latent, and the fix only pays off once a client records what
  the server said.
- `p*_engine_kind` is stored beside `p*_engine_version` (`play/store.py:53-56`).
  For network opponents `(engine_kind, model_id)` determines the opponent id
  exactly (`net-policy` is `@0`, `net-mcts` is `@128`, one constant,
  `opponents.py:178`), so dropping the `@N` suffix loses no
  information. For `minimax-d2` versus `minimax-d3` (same kind) it does lose
  the depth.

**Option A: model_id for model engines, core revision for everything else,
plus an optional `engine_config` string (RECOMMENDED, DECIDED).**

The one rule: **`engine_version` names the versioned artefact that decided the
move. It is the `model_id` for a checkpoint-backed engine, and the
quantik-core revision of the code that ran for an engine that is pure core
code. It is never an opponent id, a display label, a filename or a config
string.** Strength-relevant configuration that is not part of the artefact
(`depth=2`, `beam_width=32`, `simulations=128`) goes in a new optional
`engine_config` string in the extended schema (free text, for humans and
pooling keys). Per implementation:

- `quantik-api-rust`: no change to `engine_version` (already the core
  revision); may add `engine_config` from the request config actually used.
- Python play service: model engines (`net-policy`, `net-mcts`) send bare
  `model_id` (`cpool`, no `@N`), with `engine_kind` distinguishing them and
  `engine_config` = `simulations=128`. Classical opponents (`minimax-d2`,
  `beam-w32`, `random`, `uniform-mcts128`) send the quantik-core version they
  ran on, with `engine_config` = `depth=2` and so on.
- Consequence to schedule: the play app and `runs/eval/*/games.json` currently
  pool on the opponent id (`service.py:295-299` comment). Pooling keys
  become `(engine_kind, engine_version, engine_config)`; this is a
  quantik-models-py follow-up, not done here.

**Option B: packet-strict, no `engine_config`.** `model_id` for model engines,
core revision for the rest, config dropped. Rejected: `minimax-d2` and
`minimax-d3` become indistinguishable in a recorded game, which is the same
unattributability problem the packet is fixing, just moved from network to
depth.

**Option C: status quo, documented as per-implementation** (Rust core
revision; Python opponent id). Rejected: it leaves `engine_version` with two
meanings under one name, and a recorded game names a network only by parsing a
string convention. It is the cheapest option (zero code) and remains
defensible if the record path stays client-stamped.

**Option D: opponent id everywhere.** Rejected for the Rust gateway, which has
no opponent concept, and it would put a configuration name into the field
that the packet says must identify a network.

**Resolved (part of the decision).** For pure-core engines `engine_version` is
whatever identifies the quantik-core build that ran: the git revision where
the server has one (the Rust gateway, `CORE_REVISION`), the installed
`quantik-core` release string where it does not (the Python service).

Consequence: `engine_version` values are **not comparable as strings across
implementations**. A git revision and a release string name the same build
in different vocabularies. Consumers key on `(engine_kind, engine_version,
engine_config)` and never parse, order or diff the version.

## 5. Backward compatibility (DECIDED 2026-09-20)

**The tension.** `certainty` is required, but the registered v1 is closed
(`additionalProperties: false`), lists five required fields, and the existing
fixtures have no `certainty`. `docs/versioning.md:25-27` allows additive
fields only when optional and treats a new required field as breaking. Also,
`RESPONSE_SCHEMA` is `quantik.engine-response.v1` in the Rust gateway
(`lib.rs:23`) while the registered id is the bare `engine-response.v1` (QW-019
D3): both servers must change their `schema` string on the next release
anyway, so there is already one coordinated cutover.

**Option A: register `engine-response.v2`, v1 stays frozen (RECOMMENDED, DECIDED).**

- New schema `schemas/engine-response-v2.json` (W2), closed, `certainty`
  required, with `candidates`, `pv`, `engine_config` optional. v1 schema and
  its captured fixtures are untouched and keep validating.
- A server emits `"schema": "engine-response.v2"` when it can fill `certainty`
  for that engine; once cut over it always does. It never emits a v2 body
  without `certainty`.
- Old client, new server: the visualizer reads only `action_index`
  (`engines.js:64-67`) and ignores the rest, so it is unaffected. A strict old
  validator sees an unknown `schema` value and refuses; that is the honest
  outcome, since a strict v1 consumer opted out of unknown data.
- New client, old server: the client accepts both ids. For a v1 body it sees
  no `candidates`, `pv`, or `certainty`, and must treat them as absent:
  render no candidates and no PV. Absent `certainty` means "unlabelled", not
  `estimate` and not `proof`: it shows no proof affordance and no claim in
  either direction.
- Servers keep answering `engine-request.v1` unchanged (requests are not
  extended by this item). A server that wants to keep serving strict v1
  clients longer may add a request-side opt-in later; not specified.

**Option B: add `certainty` as required to the existing v1 schema; rewrite
the captured fixtures.** Rejected: it turns every historical response into an
invalid document, contradicts `versioning.md:25-27`, and makes an old server
non-conformant the day the schema lands. It is the least code.

**Option C: keep v1, `certainty` optional at the top level, required only when
`candidates`, `pv` or `policy` are present (a JSON Schema conditional).**
Rejected: `mcts` and `beam` responses already carry `value` with no
`certainty`, so the very conflation (a tanh and a proof reaching the client as
the same claim) stays legal, and the packet says no engine may omit it. It is
the only option that is a pure additive change; choose it only if breaking
the id is judged worse than a legal unlabelled `value`.

Note on W2's step 2: this section is the answer it was told to wait for.
Option A means W2 adds a new schema and fixtures and leaves the v1 files
alone; Options B and C change v1 files in place.
