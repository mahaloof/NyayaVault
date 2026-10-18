# Fresh local demonstration — 17 October 2026

The user requested a complete reset of cases, evidence and blockchain history. This report records the empty state immediately after the reset; cases added later are not reflected here.

- All 9 cases (including archived cases), 17 evidence records and encrypted objects, 70 custody events and corresponding application transaction records were removed. Verification, audit, case membership, tag and OCR records were also cleared.
- All five user accounts, passwords, application configuration, encryption keys, Gemini settings, Fabric identities and application code were preserved.
- Both Fabric peers and the orderer were reset. The original channel genesis configuration was reused, and both organizations approved a fresh chaincode definition with a two-organization endorsement policy. No evidence events were replayed.
- Both peers have four setup-only blocks: genesis, two organization approvals and chaincode-definition commit. These are necessary network setup transactions, not old evidence history.
- Read-only verification confirmed zero application records and objects, empty history for all 17 former evidence IDs on both peers, connected Fabric, and available AI/OCR. No test case or evidence was created after reset. See [results](fresh-start-results.json).

## Start and use

Open http://127.0.0.1:3001 and refresh any previously open page. Existing accounts still work. Create a new case through Investigation cases, assign its users, then upload evidence.

Resume this existing deployment with `bash scripts/start-fabric.sh`. Normal backend startup seeds only missing user accounts, not cases. Do not run `scripts/populate-demo.py` unless you want demonstration records added again. The separate portable startup can populate demo records by default; use its `--no-demo` option (Windows: `-NoDemo`) to start it without examples.

## Private recovery backup

The pre-reset recovery folder and older Windows transfer ZIP were deleted at the user's request on 17 October 2026. They are no longer available for restoration. Historical reports retain their original backup paths as records of past checks, not as available recovery files.

To transfer the current installation, create a new private snapshot using the transfer scripts. Restore the database, keys, encrypted files and blockchain together into an empty target deployment.
