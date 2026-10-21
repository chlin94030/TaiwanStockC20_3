# Alpha Radar V20.3-final: ten-perspective audit and finite acceptance

## Decision

V20.2.1 is not certified as an optimized, profitable, production-ready strategy. This review reproduced six implementation counterexamples in its actual source, then corrected the affected paths. V20.3-final is a **final historical-acceptance candidate**, not a declaration that all original investment goals have been achieved.

The goal of the finite protocol is to stop the version-and-seed search cycle. The app executes C1 and C2 once, with the same frozen definition, and reports PASSED_HISTORICAL_RESEARCH_ONLY, NOT_PASSED, or INSUFFICIENT_EVIDENCE. Completion is a separate execution status. No verdict starts C3, changes weights, or authorizes an order.

### Evidence actually inspected

The source baseline is AlphaRadar_V20_2_1_Full_100_Files.zip, 100 root files. Its SHA256 is `3907d60d8c8614e803ac66be895eaa8ed05199daaf05f1a2ac1c60c4b24ada9a`. The uploaded V20_2_1_VALIDITY_AUDIT.md and V20_2_VALIDATION_SUMMARY.md were compared with the code rather than treated as proof that the code satisfied their statements. The latest available real uploaded result is V20.1 A3, v19_results (9).json, supported by v19_validation (9)(1).md. No V20.3 C1/C2 provider-history performance result has been obtained in this review environment.

The legacy A3 hierarchical audit reports 5/20/60-day mean excess returns of approximately -0.324%, -1.791%, and +2.130%, respectively. These are arithmetic means of sampled holding-period results, not compound portfolio returns, and they concern a different old implementation. The 60-day quarter-cluster 90% lower bound was about -3.762%. Those values cannot be inherited as evidence for the corrected 80/20, strict-252-bar, no-backfill cascade.

## Ten perspectives

| # | Perspective | Finding | Final treatment and limit |
|---|---|---|---|
| 1 | Original objectives and acceptance target | A 60-day core plus 20/5-day filters is not the same product as independently optimized short/mid/long alpha engines. The present experiments do not validate original 40/120-day horizons, full-market screening, intraday execution or limit-up prediction. | Keep the finite historical target explicit. `full_original_goal=NOT_CERTIFIED` is never turned into a full-product pass by a positive 60-day test. |
| 2 | Universe and point-in-time data | Official current company masters improve current roster provenance but do not reconstruct historical membership. A delisted name is not automatically an invalid historical constituent. | Preserve the current-snapshot limitation. Freeze the official roster across the two waves and retain the original requested cohort when reading the cache; do not re-sample only the successfully downloaded survivors. |
| 3 | Factor arithmetic and units | Market breadth compared a synthetic/adjusted `calc_close` against a raw-price `ma60`. In a reproduction, every stock was below its raw MA60, but reported breadth was 100%. The old annual-high calculation allowed only 180 observations. | Use raw close against raw MA60. Require 252 historical bars for the final annual-high factor and sufficient date-T factor coverage for sampling. Shorter factor histories are not marketed as a complete 252-session high. |
| 4 | Causality and decision timing | The old policy switched to 0050 when the selected basket's *future* outcome was incomplete. Changing only future data availability changed the allocation state. | Freeze stock/index/cash routing from date-T inputs. A missing selected exit remains an unknown outcome; it never becomes a retroactive index trade. Missing market context becomes UNKNOWN, not STOCK_SELECTION. |
| 5 | Weight evidence and filter efficacy | 80/20 is a frozen candidate, not a proven optimum. Negative standalone 5/20-day alpha does not demonstrate that those components are useful filters. Same-day subtraction of one benchmark return cannot change cross-sectional rank order. | Keep core 80% liquidity / 20% annual-high. Compare no gates, confirmation gate and full entry gate on the **same holding horizon**. Include liquidity-only, high-only, 75/25 and 85/15 as diagnostic controls. Never auto-adopt their winner. Expose raw benchmark-relative returns separately from percentile ranks. |
| 6 | Portfolio accounting and benchmark fairness | The old cascade could filter a whole pool then backfill the top list. Whole-basket completeness hid the difference between an unselected cash slot and a missing selected exit. The old audit accepted incompatible price bases. | Lock the top five core names before gates. Rejected slots stay cash; no lower-ranked refill. Divide portfolio returns by five funded slots, not by only the filled names. Compare with the date-T rankable same pool and 0050 on compatible adjusted-price bases. A suspended benchmark is missing, not a zero-return reference. |
| 7 | Dependence, statistical uncertainty and selection bias | Combining independently constructed C1/C2 non-overlapping subsets can create overlapping combined observations. A reproduction combined six purportedly disjoint observations that admitted only three globally disjoint windows. Earlier confirmation checked selection more strongly than allocation. | Select one global chronological subset before inspecting outcomes. Show date-weighted quarter-block resampling and 95% lower bounds, minimum block/sample coverage, and both selection and policy verdicts. These are descriptive robustness checks, not proof of independent blind significance. |
| 8 | Tradability, costs and risk | Daily next-open fills, fees and slippage are assumptions. A daily-bar holding-period study does not validate intraday reversal, limit-up fill probability, stop execution, or a fully capital-constrained continuously rebalanced NAV curve. | Retain explicit no-fill/missing outcomes, fixed cash slots and an additional 50-basis-point active-stock round-trip stress. Report participation. Keep intraday and full portfolio-risk certification outside the pass label. No leverage or automatic order authority is added. |
| 9 | Software state, speed and reproducibility | Checkpoint code hashing omitted the active V20 ranking module. Frozen C1/C2 unnecessarily called legacy nested weight fitting. Job identities and pause/progress persistence needed stronger controls. | Hash production Python sources, bind reports to version/protocol/run identity, preserve pause requests under a lock, and skip the old fitter in final waves. Export decision records, selected trades, compact price inputs and hashes for independent replay. |
| 10 | Finite operation and final judgment | More seeds or repeated candidate selection on an exposed era do not manufacture a fresh future holdout. A completed campaign could otherwise invite another rerun until it looked good. | One action runs exactly C1 and C2; finished campaigns do not restart through the normal button. Retry only bounded technical failures. Export one final bundle and stop irrespective of the financial verdict. A failed protocol rejects this frozen design, not every possible price/volume strategy. |

## Reproduced original defects

The evidence kit contains `original_counterexamples.json` and `probe_original.py` (the latter runs against its included `base/` source). Exact original source locations include:

- `base/v19_backtest.py`, old clean-wave branch: `elif state=='INDEX_LEAD' or not cr.get('complete')`. A complete stock outcome returned +8% with STOCK_SELECTION; replacing only its future completeness flag changed the policy to INDEX_LEAD and +3%.
- `base/v197_ten_pillars.py:112`: `(good.calc_close > good.ma60)`. A consistent raw-price calculation yielded 0% breadth; the original calculation yielded 100%.
- `base/v20_model.py`, old combined disjoint audit: unioning separately disjoint dates allowed cross-wave overlap.
- `base/v20_model.py`, `audit_v202_report`: a RAW_PRICE_ONLY candidate versus ADJUSTED_PROVIDER reference was counted as a comparable case.
- `base/v192_checkpoint.py`, `code_digest`: editing v20_model.py did not change the digest.
- `base/v20_model.py`, `v202_market_state`: a frame without market regime or breadth was assigned STOCK_SELECTION.

The corrected counterparts live in `v20_final.py`, `v20_model.py`, `v197_ten_pillars.py`, `v192_sampling.py`, `v192_checkpoint.py` and `v19_service.py`. New adversarial tests cover those defects, future-return mutation, no-backfill gate behavior, partial cash slots, missing benchmark volume, wrong protocol/version/seed/roster, global non-overlap and stop-after-completion.

## Frozen strategy and what the scores mean

Core score: 80% observed same-date liquidity percentile + 20% observed annual-high percentile. Core floor: 55. Freeze the top five core candidates first. Confirmation score: 40% 20-session cross-sectional return rank, 30% downside-resilience rank and 30% trend-efficiency rank; threshold 50. Timing score: 35% 5-session return rank, 30% volume impulse and 35% entry quality; threshold 55. Timing additionally excludes RSI over 82 or 20-day bias over 12%, and requires those inputs to be known.

The 60-day row evaluates the core; the 20-day row applies confirmation; the 5-day row applies both gates. Separate no-gate/confirmation/full-gate records at every horizon test whether filtering actually adds value. The gate comparisons are diagnostic until evidence exists; they do not convert the 5/20-day layers into proven alpha engines. Scores are neither probabilities nor calibrated forecasts.

Subtracting the same benchmark return from every stock on date T leaves cross-sectional ordering unchanged: `rank(r_i - r_b) = rank(r_i)`. The final code retains raw horizon-specific excess fields for interpretation. It does not label a within-date rank as beta-adjusted alpha.

## Final historical-acceptance contract

C1: 150 requested equities, 48 stratified cutoff dates, date seed 316227, universe seed 282843. C2: 150 requested equities, 48 stratified dates, seeds 331777 and 324161. Both use 5/20/60-session horizons, the same official current roster snapshot, the same frozen code and protocol, and saved exact-cutoff exclusions. Different seeds do not imply disjoint stock membership or independent market eras.

The app registers its actual start timestamp, code hash, protocol hash and base settings before the first wave. It does not backdate that record to the last market observation. Old reports are exposure records, not evidence that the corrected design passed.

The primary 60-day acceptance has two separate required endpoints: selection versus the date-T rankable same pool, and policy versus 0050. For each endpoint, both waves must exist with matched version/protocol/source settings, at least 44 comparable dates per 48-date wave, at least 50% participation per wave, at least six observed calendar-quarter blocks, and at least six usable globally selected non-overlapping cases. Download coverage is governed by the 92% clean-wave threshold.

After those data checks, both wave mean excesses must be positive, the pooled mean excess must be at least 0.2 percentage point, the IID, weighted-quarter-block and global-disjoint 95% lower bounds must be positive, and the extra-cost stress mean must remain positive. Policy also requires a positive mean absolute net return. The 0.2-point floor is a minimum engineering acceptance floor, **not** the user's desired profit target or a claim of a substantial performance leap. Meeting it is not the same as meeting all original goals.

A data shortfall is INSUFFICIENT_EVIDENCE. An adequate but failing result is NOT_PASSED. Passing both primary endpoints is PASSED_HISTORICAL_RESEARCH_ONLY. None implies a global optimum, future profit, successful intraday execution or automatic trading permission. No same-wave parameter search, extra wave, threshold lowering or favorable-date substitution follows any verdict.

Quarter clusters and greedy non-overlap address specific dependence problems but do not remove all serial dependence, survivor bias or repeated historical research exposure. No formal multiple-testing-adjusted future alpha claim is made. The current final run is a bounded historical diagnostic.

## What was actually tested here

**347 tests passed, zero failed, in 83.93 seconds** in a complete run of the bundled test suite. The large legacy ten-date integration test that earlier releases had left unfinished was included in this run. The test suite is headless: its Streamlit interface tests use a fake UI contract, not a real Cloud browser.

The separate final-engine synthetic integration used 16 symbols including the benchmark and 6,720 input rows. It executed six date-horizon cases, produced 78 result records and 54 per-date factor diagnostics, exported compact inputs and trades, then resumed all six checkpoints with identical result records. Cold execution took approximately 2.23 seconds and replay approximately 1.84 seconds in this small fixture. An injected failure proved that the old nested fitter was called zero times. These timings must not be extrapolated to a 150-equity Cloud download or treated as financial performance.

The synthetic report was correctly classified as insufficient for real-market certification. The evidence kit contains the actual test log, environment versions, integration output and original counterexamples. The runtime used Python 3.13.5, NumPy 2.3.5 and pandas 2.2.3. Streamlit, yfinance and pyarrow were not installed in this review runtime; pinned production dependency installation and real Cloud rendering were not validated. Existing requirements were not silently replaced with different dependencies.

## Deployment and operation

For a repository already on V20.2.1, apply the patch at repository root. For a mixed source tree, use the full root-level package. Keep `data/`; back it up before deployment because hosting redeployments are not durable storage guarantees. Do not copy QA synthetic results into the app's market-data directory.

Open the full dashboard, then use the prominent final-acceptance button. S1-S8 controls are collapsed legacy diagnostics, not prerequisites. The final campaign uses a separate versioned state file. It reuses downloaded price caches when valid, excludes saved old cutoff dates, and never treats old C1/C2 output as corrected-version evidence.

A browser disconnect alone need not kill the app-owned worker. A hosting-process restart does kill in-process daemon threads; resuming requires the app to execute again and the checkpoint files to have survived. Streamlit Session State is WebSocket-scoped, so durable progress is written to files rather than entrusted to Session State. No always-on background-service guarantee is made.

After two waves the app offers `V20_FINAL_RESULTS.zip`: final protocol, per-wave reports, paired decisions, factor diagnostics, selected-trade CSVs and compact price inputs when those saved run artifacts remain available, plus hashes. Save this bundle. There is no need to submit many separate generic `v19_results` files.

## Method reference boundary

Official scikit-learn TimeSeriesSplit documentation was consulted for time ordering and a train/test gap; this implementation is a frozen historical replay rather than a claim that calling TimeSeriesSplit alone solves leakage. Official Streamlit threading and Session State documentation was consulted for worker/UI separation and WebSocket session lifetime. Source-code counterexamples and new calculations above are this review's own findings, not claims drawn from those external documents.

## Final limit

This release optimizes **causal correctness, procedural efficiency and the ability to make a finite decision**. It does not claim an optimized profit function has already been attained. At the end of the final campaign, preserve the result rather than fitting the same evidence until it passes. Rejection or insufficient evidence is a legitimate final outcome for this frozen design.
