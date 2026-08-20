# Phase 11 Final Evidence Freeze Report

## A Provider Safety
provider calls: 0
API spend: $0

## B Package Location
evidence/final/phase11

## C Package Version
phase11-final-evidence-v1

## D Dataset Identity
DatasetVersion: 2f8c7bba-08b1-4d8b-8b0e-b564e8a61886
Dataset SHA: b2fff1524b199fb2d302b7c4ebd752a9a47d32bab68a232ab06b7b1e07fa1510
match: MATCH

## E Scientific Fingerprints
prompt hash: e1d041bd6a1ec4f27efe6a3377d98ec0321af02b59ee9abedf64bf349ac9b299
routing fingerprint: bf8d0d1ef228f60e07ceff2e1da43eeefe8ae5538d439b5d9a4c325294b7030b
retry policy: controlled-retry-v2

## F Manifests
RQ1: 550e0ec5-e531-45fa-a1ea-422cc9710001
RQ2: 0581763f-1fff-4092-a2f2-c60170eb8dbf
RQ3: 816ba9b6-1dd4-40ac-abed-15e3e4dd896a
RQ4: f63360e4-04c8-4815-86b5-eefeed78cb5b
RQ5: 494cf45e-f974-4f92-bc8f-f490d82d0f91
RQ6: 5491bd7b-2f59-4922-a4c2-ecbe38c57e0a
RQ7: 55e58905-2265-49b3-87b7-1d55daa073ea

## G Experiments
count: 7
IDs: 3b8ef1ab-f149-4458-9580-02c41fdea781, 3f6294f6-cf5e-4c27-8c21-f162b93c594d, 4d65d88e-3e9f-4e0c-9460-b2a10f57c3ca, a3484b84-870d-4f01-85ad-df7d160c7efd, d02a90f5-8096-48aa-9297-ee51e93a10ca, eccc037f-d331-47d7-a186-983ae58f3369, f7ebd809-6ad4-4ba0-8f19-2f24200ddeed

## H Unit Freeze
planned: 13400
exported: 13400
unique: 13400
status accounting: 12602 SUCCEEDED / 523 valid PARTIAL / 275 FAILED

## I Pass Freeze
planned pass slots: 16600
valid returned: 16228
failed slots: 372
accounted: MATCH

## J Run Freeze
CONTROLLED: 13400
SUCCEEDED: 12602
valid PARTIAL: 523
FAILED: 275

## K PassAttempt Freeze
count: 17257
state breakdown: {"FAILED_FINAL": 341, "FAILED_RETRYABLE": 657, "SUCCEEDED": 16259}

## L Superseded RQ5 Audit History
runs: 226
passes: 452
attempts: 500
isolated from science: YES

## M Pilot Isolation
PILOT runs: 11; not included in final scientific metrics.

## N AnalysisRuns
RQ1 ID: 63cd1939-05f4-42cf-a933-4094ac652eea
RQ2 ID: 25949bbe-b962-4808-9830-f106bb3d1d42
RQ3 ID: 4a5a5c97-6b63-4d33-9129-3d7048e96a87
RQ4 ID: 13510c83-354c-49b1-811f-5e96a6b985e7
RQ5 ID: bbfbcf03-1791-4892-a39c-418831260f35
RQ6 ID: ca9a1668-58b9-4a9d-8b0d-991c2b7a38ec
RQ7 ID: d3773e0c-80dc-4235-aa46-ffd89af9face

## O Phase 10 Artifacts Included
tables: YES
charts: YES
report: YES
metrics summary: YES
provenance: YES

## P Traceability Index
metrics indexed: 46
broken references: 0

## Q Database Snapshot
path: backups/judgelab-phase11-final-evidence-20260820.dump
size: 25729866
SHA256: 931819ea2a90b0f87216dc11cb825c0dde8dee478f0e3cbe1b6d51503a27a7f8
pg_dump exit: 0
pg_restore validation: PASS

## R SHA256 Package Integrity
files hashed: 80
root digest: f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13
verification: PASS

## S Secret Scan
result: PASS

## T Self-Consistency Trace Tests
RQ1: PASS
RQ2: PASS
RQ3: PASS
RQ4: PASS
RQ5: PASS
RQ6: PASS
RQ7: PASS

## U Provider-Free Tests
passed: 141
failed: 0
skipped: 4 (provider opt-in tests only)

## V Repository Freeze
commit: phase11-final-evidence-frozen-v1 tag target
tag: phase11-final-evidence-frozen-v1
working tree: clean at freeze
package root hash: f1a1d6ffcb6f6fd5a5dd48f7b51a731d6b765a68ff76501bf6c0ef356e53ce13

## W Phase 12 Ready?
YES

## FINAL VERDICT

PHASE 11 COMPLETE — FINAL EVIDENCE PACKAGE FROZEN AND VERIFIED — READY FOR PHASE 12
