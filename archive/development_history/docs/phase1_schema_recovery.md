# Phase 1 schema recovery contract

The live research database was inspected read-only before implementation.  Its
reported revision is `0004_controlled_experiments`.  The source migrations in
`alembic/versions/` recreate the same logical table chain on an isolated fresh
database and are deliberately forward-only.

The fingerprint source is `backend/schema_fingerprint.py`. It records column
types/nullability/defaults, keys, foreign keys, unique/check constraints,
indexes, revision, and table counts without performing a write.

Evidence classes are intentionally separate:

- `LEGACY_EXPLORATORY`: historical `judge_decisions` and existing artifacts.
- `LIVE_SANDBOX`: legacy rows whose prompt category is `live`,
  `live_calibrated`, or `ensemble_eval`.
- `PLANNED`: an `experiment_manifest` with status `PLANNED`/`FROZEN` and no
  controlled run.
- `CONTROLLED`: a `runs` row created only by `ControlledPersistence`; its
  `metadata_json` includes `evidence_class=CONTROLLED`, the immutable unit ID,
  unit fingerprint, manifest ID, and condition code.

The physical `runs` table has no `experimental_unit_id` column.  The recovered
persistence layer therefore preserves the immutable unit ID in `metadata_json`
and validates the same experiment/prompt/pair configuration before creating a
run. This is an intentional schema-compatible representation, not a claim of a
missing foreign key.

Outcome semantics use the physical schema without overloading `winner_id`:

| Semantic outcome | `runs.final_result_type` | `final_parse_status` / `passes.parse_status` |
|---|---|---|
| ANSWER_A | ANSWER_A | PARSED |
| ANSWER_B | ANSWER_B | PARSED |
| TIE | TIE | PARSED |
| UNKNOWN | UNKNOWN | MISSING_RESPONSE |
| INVALID_RESPONSE | ERROR | INVALID |
| API_ERROR | ERROR | PROVIDER_ERROR |
| TIMEOUT | ERROR | TIMEOUT |

The distinction for the three error classes is preserved through parse status
and error metadata; it is not represented as a tie.
