# Canonical source-correct study data

Normal reproducibility uses `data/canonical/source_corrected_study_v1.json`
and the immutable raw LMSYS snapshot `data/human_judgment.jsonl`.

The canonical manifest contains 1,568 controlled reference records. Each
record identifies its upstream question, turn, source-model pair, expected
answer hashes, human preference reference label, reconciliation status, and a
stable logical identity. The exact answer text is resolved only from the raw
snapshot by `(question_id, turn, model, SHA-256)`.

It covers 80 distinct MT-Bench questions with preserved upstream `question_id`
values 81–160. MT-Bench is two-turn: the fresh dataset therefore has 80
turn-1 and 80 turn-2 prompt records, or 160 turn-level prompt records in total.
That total must not be interpreted as 160 distinct MT-Bench questions.

`scripts/build_dataset.py` fails closed for a missing source record, ambiguous
source identity, or a prompt/answer hash mismatch. It never reads a historical
database or chooses an answer by database ID or insertion order.

The two explicitly recorded forensic turn-2 disambiguations retain their
committed human preference reference label from the frozen reconciliation; no
different raw row is used to infer a replacement label.
