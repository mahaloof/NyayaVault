# Interactive browser acceptance

Executed on 2026-10-05 using the Codex in-app browser against the running production Next.js frontend and FastAPI backend at 127.0.0.1:3000 / :8000.

The standalone Playwright runner was blocked by macOS browser-process restrictions. Its two launch failures remain in browser-test-results.json; they are not silently relabeled as passes.

The alternative interactive browser check successfully performed:

1. Investigator A login.
2. Selection of CASE-2026-001 and registration of the actual sample TXT file as EVD-BROWSER-001.
3. Display of completed upload/encryption/metadata/custody steps and trusted SHA-256.
4. Verification of decrypted stored original: equal trusted/calculated hashes and EVIDENCE INTEGRITY VERIFIED.
5. Confirmed handoff to Investigator B with a reason and visible custody timeline.
6. Logout and login as Investigator B.
7. Candidate upload of the modified TXT file: differing calculated fingerprint and INTEGRITY VERIFICATION FAILED.

Evidence UUID: fc5f4191-cb5f-429b-a118-4ded57a7e9ed.
Original hash: 3f37a64133433f7a51dd3e95948f438929c302d639c34ab360b0baded75eae40.
Modified hash: 7d5bca68817339e524b6e025f6f778afe7fce795f3e29d9ea39f7f49efdfd78c.

Initial dev-mode routing failed because filesystem watchers hit EMFILE; production build/start fixed it. Browser automation pointer activation was unreliable in the embedded browser, so the check used normal keyboard activation (Enter/Space), dropdown selection and file-chooser uploads. This is not a claim that the standalone browser suite passed.

A stale evidence status badge after verification was found and corrected to use the actual returned result. The source was rebuilt after this correction.

Final check: the corrected badge displayed INTEGRITY ALERT immediately after the modified-file comparison. Audit filtering showed both verification results and the custody transfer; the dashboard showed one registered item, one integrity alert and one transfer. Screenshots were saved in docs/.

Responsive check at a 390px viewport: document scroll width was 390px (no horizontal document overflow). The viewport override was reset afterward. Live dashboard measurements are preserved in live-demo-metrics.json.
