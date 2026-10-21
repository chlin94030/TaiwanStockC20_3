# Alpha Radar V20.3-final

This is a frozen final historical-acceptance build, NOT a proven profitable model.

Keep and back up `data/`. Apply the Patch only over V20.2.1; otherwise use the Full root-level package. The full package has fewer than 100 root files. QA tests are bundled in QA_TESTS.zip and are not required to run the app.

Open the full dashboard and press the final-acceptance button once. No S1-S8 prerequisite; no manual A/B between C1 and C2. The normal button will not restart a completed final campaign. Stop and resume preserve compatible checkpoints while files remain available.

After the fixed two waves, save V20_FINAL_RESULTS.zip. Completion is not a pass. Expected results: PASSED_HISTORICAL_RESEARCH_ONLY, NOT_PASSED, or INSUFFICIENT_EVIDENCE. No automatic orders or parameter adoption.

To reproduce engineering tests locally in a suitable environment:

```bash
python -m zipfile -e QA_TESTS.zip .
python -m pytest -q
```

Production Cloud browser/dependency installation has not been certified in the audit environment. Consult V20_VALIDATION_SUMMARY.md and FINAL_PROTOCOL.json for the exact evidence boundary and frozen criteria.
