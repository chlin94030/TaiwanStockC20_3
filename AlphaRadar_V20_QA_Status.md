# V20.3-final actual QA

{
  "source_baseline_zip_sha256": "3907d60d8c8614e803ac66be895eaa8ed05199daaf05f1a2ac1c60c4b24ada9a",
  "release_version": "20.3-final",
  "code_hash": "1baab1b7742dfbef22aa286a37f51a738132a32f0bb3b16d74f3f369b4027d9b",
  "protocol_hash": "7b76dac3aa5f77c135157d9a929330c7705b7133deef06b3d6aad0bb30d0cf69",
  "all_regression": {
    "passed": 347,
    "failed": 0,
    "seconds": 83.93,
    "log": "all_regression.log"
  },
  "baseline_selected_regression": {
    "passed": 161,
    "seconds": 20.34
  },
  "synthetic_end_to_end": {
    "input_rows": 6720,
    "symbols": 16,
    "date_horizon_cases": 6,
    "decisions": 78,
    "factor_diagnostics": 54,
    "selected_trade_rows": 196,
    "cold_seconds": 2.2319697390000783,
    "resume_seconds": 1.8384051430000454,
    "resumed_cases": 6,
    "legacy_fit_calls": 0,
    "synthetic_not_performance_certified": true,
    "final_outcome": "INSUFFICIENT_EVIDENCE"
  },
  "runtime": {
    "python": "3.13.5",
    "numpy": "2.3.5",
    "pandas": "2.2.3",
    "pytest": "9.0.2",
    "streamlit": "NOT_INSTALLED",
    "yfinance": "NOT_INSTALLED",
    "pyarrow": "NOT_INSTALLED",
    "plotly": "6.5.2",
    "requests": "2.32.5",
    "lxml": "6.1.1"
  },
  "production_cloud_browser_tested": false,
  "new_C1_C2_real_market_run_completed_here": false,
  "package_install_from_requirements_verified": false,
  "global_optimum_proven": false,
  "full_original_goals_certified": false
}

See QA_TESTS.zip, the external evidence kit, and V20_VALIDATION_SUMMARY.md.
