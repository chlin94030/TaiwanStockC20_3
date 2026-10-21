"""V20 staged research profiles and execution-stage gate.

The stage profiles are resource controls, not investment parameters.

Cloud progression:
    40x4 -> 60x6 -> 80x8 -> 100x12 -> 120x14 -> 150x18 -> 150x24 temporal + cross-universe confirmation -> one-click auto campaign

V20.3-final retains separated execution/research gates and adds an S8 cross-universe falsification stage after the S7 temporal cross-check:

* execution_status: did this stage actually finish its requested computation?
* research_status: how complete/convincing were the historical outcomes?

A RESEARCH_PARTIAL report can therefore be STAGE_COMPLETE when all requested
cutoff/horizon computations were attempted, the report was finalized, and the
stock-history coverage cleared the predeclared floor.  Missing outcomes remain
visible as research-quality warnings; they no longer create a permanent UI lock.
"""
from __future__ import annotations
from dataclasses import replace
import math

RELEASE = '20.3-final'
GATE_SCHEMA = 4

STAGES = (
    dict(key='S1', label='第1階段｜微型穩定性檢查', stocks=40, dates=4,
         request_budget=140, batch_size=15, factor_audit=False, search_budget=40,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='low'),
    dict(key='S2', label='第2階段｜小型穩定性檢查', stocks=60, dates=6,
         request_budget=220, batch_size=20, factor_audit=False, search_budget=48,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='low'),
    dict(key='S3', label='第3階段｜中小型驗證', stocks=80, dates=8,
         request_budget=300, batch_size=20, factor_audit=False, search_budget=64,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='low'),
    dict(key='S4', label='第4階段｜100檔驗證', stocks=100, dates=12,
         request_budget=420, batch_size=25, factor_audit=False, search_budget=80,
         optional_allowed=True, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='medium'),
    dict(key='S5', label='第5階段｜120檔擴大穩定性', stocks=120, dates=14,
         request_budget=500, batch_size=20, factor_audit=False, search_budget=88,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='medium'),
    dict(key='S6', label='第6階段｜150檔Cloud邊界驗證', stocks=150, dates=18,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='high'),
    # V19.8.7 keeps the same 150-stock memory footprint but changes the time
    # sample: a different seed + stratified dates.  This is more informative
    # than immediately enlarging the stock pool after S6.
    dict(key='S7', label='第7階段｜150檔不同時間點交叉確認', stocks=150, dates=24,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='high',
         seed=271828, sampling_method='stratified'),
    # V19.8.7 does not enlarge memory after S7. S8 perturbs BOTH the stock-pool
    # seed and the time seed, while keeping the frozen S4/S6 candidate weights
    # unchanged.  It is a falsification/robustness stage, not a rescue search.
    dict(key='S8', label='第8階段｜150檔跨股票樣本壓力測試', stocks=150, dates=24,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='high',
         seed=314159, universe_seed=161803, sampling_method='stratified'),
 )

# V20.3-final keeps A1-A3 readable for already-saved V20.1 reports, but NEW one-click
# campaigns use C1/C2.  The C waves first clean the live roster, then validate a
# core-first cascade with proportional (not sector-equalized) sampling.  Two
# 48-date waves give 96 fresh exact cutoffs without increasing the proven
# 150-stock Cloud memory ceiling.
LEGACY_AUTO_WAVES = (
    dict(key='A1', label='V20.1舊自動驗證1/3｜150檔×30日期', stocks=150, dates=30,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='high',
         seed=141421, universe_seed=223607, sampling_method='stratified'),
    dict(key='A2', label='V20.1舊自動驗證2/3｜150檔×36日期', stocks=150, dates=36,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='high',
         seed=173205, universe_seed=244949, sampling_method='stratified'),
    dict(key='A3', label='V20.1舊自動驗證3/3｜150檔×42日期', stocks=150, dates=42,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.90, risk_tier='high',
         seed=223607, universe_seed=264575, sampling_method='stratified'),
)

AUTO_WAVES = (
    dict(key='C1', label='V20.3-final清理驗證 1/2｜150檔×48日期', stocks=150, dates=48,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.92, risk_tier='high',
         seed=316227, universe_seed=282843, sampling_method='stratified', universe_mode='proportional'),
    dict(key='C2', label='V20.3-final清理驗證 2/2｜150檔×48日期', stocks=150, dates=48,
         request_budget=650, batch_size=20, factor_audit=False, search_budget=96,
         optional_allowed=False, finance_allowed=False, full_artifacts=False,
         cloud_enabled=True, min_download_coverage=.92, risk_tier='high',
         seed=331777, universe_seed=324161, sampling_method='stratified', universe_mode='proportional'),
)

ALL_PROFILES = STAGES + LEGACY_AUTO_WAVES + AUTO_WAVES

OFFLINE_EXTENSIONS = (
    dict(key='L1', label='離線擴大｜200檔', stocks=200, dates=24),
    dict(key='L2', label='離線擴大｜300檔', stocks=300, dates=40),
    dict(key='L3', label='離線擴大｜450檔', stocks=450, dates=65),
    dict(key='L4', label='離線完整｜600檔', stocks=600, dates=100),
)


def get_stage(key: str):
    for stage in ALL_PROFILES:
        if stage['key'] == key:
            return dict(stage)
    raise ValueError('UNKNOWN_V1986_STAGE')


def stage_index(key: str) -> int:
    return next(i for i, stage in enumerate(ALL_PROFILES) if stage['key'] == key)


def apply_stage(cfg, key: str, *, optional_data=False, financial_history=False):
    stage = get_stage(key)
    optional = bool(optional_data and stage['optional_allowed'])
    finance = bool(financial_history and stage['finance_allowed'] and optional)
    return replace(
        cfg,
        stocks=int(stage['stocks']),
        dates=int(stage['dates']),
        request_budget=int(stage['request_budget']),
        download_batch_size=int(stage['batch_size']),
        progressive_universe=True,
        factor_audit=bool(stage['factor_audit']),
        sparse_budget=int(stage['search_budget']),
        optional_data=optional,
        financial_history=finance,
        export_full_artifacts=bool(stage['full_artifacts']),
        export_history_database=bool(stage['full_artifacts']),
        min_download_coverage=float(stage['min_download_coverage']),
        seed=int(stage.get('seed', cfg.seed)),
        universe_seed=int(stage.get('universe_seed', cfg.universe_seed)),
        sampling_method=str(stage.get('sampling_method', cfg.sampling_method)),
        universe_mode=str(stage.get('universe_mode', cfg.universe_mode)),
        research_stage=str(stage['key']),
    )


def stage_from_settings(settings: dict | None):
    """Return the canonical stage represented by a report's settings.

    Exact stock/date matching prevents an older S5 label from being mistaken
    for the newer 120x14 bridge stage.  A legacy 150x18 S5 safely maps to S6.
    """
    settings = settings or {}
    key = str(settings.get('research_stage') or '')
    try:
        stocks = int(settings.get('stocks') or 0)
        dates = int(settings.get('dates') or 0)
    except (TypeError, ValueError):
        return None
    for stage in ALL_PROFILES:
        if stage['key'] == key and stocks == int(stage['stocks']) and dates == int(stage['dates']):
            return key
    for stage in ALL_PROFILES:
        if stocks == int(stage['stocks']) and dates == int(stage['dates']):
            return str(stage['key'])
    return None


def next_stage_key(key: str | None):
    if key is None:
        return STAGES[0]['key']
    keys=[x['key'] for x in STAGES]
    if key not in keys:
        return None
    i=keys.index(key)
    return STAGES[i + 1]['key'] if i + 1 < len(STAGES) else None


def _finite_float(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _download_coverage(report: dict, stage: dict):
    """Find the most direct observed history coverage without inventing data."""
    q = (((report.get('universe_diagnostics') or {}).get('universe_quality')) or {})
    manifest = report.get('manifest') or {}
    candidates = (
        q.get('download_coverage'),
        manifest.get('requested_target_coverage'),
        manifest.get('download_completeness'),
    )
    for value in candidates:
        value = _finite_float(value)
        if value is not None:
            return max(0.0, min(1.0, value)), 'reported'

    # Backward-compatible fallback for already-saved V19.8.x reports.  symbols
    # includes the benchmark when it was available, so subtract at most one.
    symbols = report.get('symbols')
    try:
        symbols = max(0, int(symbols or 0) - 1)
        requested = max(1, int(stage['stocks']))
        return max(0.0, min(1.0, symbols / requested)), 'symbols_fallback'
    except (TypeError, ValueError):
        return 0.0, 'missing'


def evaluate_stage_gate(report: dict | None):
    """Evaluate execution completion independently from research quality.

    Hard execution requirements:
      1. canonical stage identity is known;
      2. downloaded stock-history coverage clears the stage floor;
      3. all requested cutoff dates were drawn;
      4. every requested cutoff x horizon computation was attempted;
      5. the finalized report contains the post-analysis diagnostics marker.

    The number of *outcome-complete* adaptive cases is intentionally NOT a hard
    gate.  It is reported separately as research quality.  This is what allows
    a 23/24 or 35/36 research result to proceed without pretending the missing
    case is complete.
    """
    report = report or {}
    settings = report.get('settings') or {}
    key = stage_from_settings(settings)
    if not key:
        return {
            'schema': GATE_SCHEMA,
            'stage': None,
            'execution_status': 'NOT_STAGED',
            'research_status': str(report.get('status') or 'NOT_RUN'),
            'checks': [],
            'blocking_reasons': ['STAGE_IDENTITY_NOT_RECOGNIZED'],
        }

    stage = get_stage(key)
    horizons = settings.get('horizons') or (5, 20, 60)
    try:
        horizons = tuple(int(x) for x in horizons)
    except (TypeError, ValueError):
        horizons = (5, 20, 60)

    cutoffs = [str(x) for x in (report.get('cutoffs') or []) if str(x)]
    unique_cutoffs = list(dict.fromkeys(cutoffs))
    requested_dates = int(stage['dates'])
    expected_cases = requested_dates * len(horizons)
    attempted_cases = len(report.get('fits') or [])
    complete_cases = int(report.get('complete_adaptive_cases') or 0)
    reported_expected = int(report.get('expected_adaptive_cases') or 0)
    coverage, coverage_source = _download_coverage(report, stage)
    min_coverage = float(stage['min_download_coverage'])
    research_status = str(report.get('status') or 'NOT_RUN')

    # A finalized V19 report contains these keys only after the analysis loop
    # and summary/report phase have returned successfully.
    finalized = (
        'summary' in report
        and 'case_diagnostics' in report
        and ('all_factor_coverage' in report or 'factor_summary' in report)
    )

    checks = [
        {
            'key': 'history_coverage',
            'label': '股票歷史資料完整度',
            'ok': coverage >= min_coverage,
            'actual': coverage,
            'required': min_coverage,
            'source': coverage_source,
        },
        {
            'key': 'cutoff_dates',
            'label': '基準日',
            'ok': len(unique_cutoffs) >= requested_dates,
            'actual': len(unique_cutoffs),
            'required': requested_dates,
        },
        {
            'key': 'case_attempts',
            'label': '日期×週期運算',
            'ok': attempted_cases >= expected_cases and reported_expected >= expected_cases,
            'actual': attempted_cases,
            'required': expected_cases,
        },
        {
            'key': 'report_finalized',
            'label': '報告與診斷彙整',
            'ok': bool(finalized),
            'actual': 1 if finalized else 0,
            'required': 1,
        },
        {
            'key': 'analysis_status',
            'label': '分析流程狀態',
            'ok': research_status in ('RESEARCH_COMPLETE', 'RESEARCH_PARTIAL'),
            'actual': research_status,
            'required': 'RESEARCH_COMPLETE 或 RESEARCH_PARTIAL',
        },
    ]
    blocking = [x['key'] for x in checks if not x['ok']]
    execution_status = 'STAGE_COMPLETE' if not blocking else 'STAGE_INCOMPLETE'
    research_case_ratio = complete_cases / expected_cases if expected_cases else 0.0

    warnings = []
    if research_status == 'RESEARCH_PARTIAL':
        warnings.append('RESEARCH_PARTIAL_OUTCOMES')
    if complete_cases < expected_cases:
        warnings.append('SOME_ADAPTIVE_OUTCOMES_INCOMPLETE')
    optional = report.get('optional_factor_coverage') or {}
    if key == 'S4' and settings.get('optional_data') and optional and max(optional.values() or [0]) <= 0:
        warnings.append('OPTIONAL_DATA_REQUESTED_BUT_ZERO_COVERAGE')

    return {
        'schema': GATE_SCHEMA,
        'stage': key,
        'stage_label': stage['label'],
        'execution_status': execution_status,
        'research_status': research_status,
        'download_coverage': coverage,
        'min_download_coverage': min_coverage,
        'cutoff_dates': len(unique_cutoffs),
        'requested_dates': requested_dates,
        'attempted_cases': attempted_cases,
        'expected_cases': expected_cases,
        'complete_adaptive_cases': complete_cases,
        'research_case_completion': research_case_ratio,
        'checks': checks,
        'blocking_reasons': blocking,
        'warnings': warnings,
    }


def stage_is_complete(report: dict | None) -> bool:
    return evaluate_stage_gate(report).get('execution_status') == 'STAGE_COMPLETE'
