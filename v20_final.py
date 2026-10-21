"""Finite final acceptance for Alpha Radar. No fitting or automatic orders.

Synthetic checks certify software behavior only. Historical cross-checks on a
current roster never establish future profitability or historical membership.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import zipfile
import numpy as np
import pandas as pd

PROTOCOL_VERSION = '20.3-final'
CLEAN_STAGES = frozenset(('C1', 'C2'))
# Engineering acceptance thresholds, registered before C1/C2. Not fitted values.
PROTOCOL = {
    'version': PROTOCOL_VERSION,
    'horizons': [5, 20, 60],
    'primary_horizon': 60,
    'minimum_annual_high_bars': 252,
    'minimum_download_coverage': .92,
    'same_pool_definition': 'DATE_T_ELIGIBLE_WITH_OBSERVED_CORE_FACTORS_NO_SCORE_FLOOR',
    'core_weights': {'p197_liquidity': .8, 'p197_annual_high': .2},
    'confirm_weights': {'p202_rel20': .4, 'p197_downside': .3, 'p197_trend_eff': .3},
    'timing_weights': {'p202_rel5': .35, 'p202_volume_impulse': .30, 'p202_entry_quality': .35},
    'core_floor': 55., 'confirm_floor': 50., 'timing_floor': 55.,
    'rsi_overheat': 82., 'bias_overheat_pct': 12., 'top_k': 5,
    'wave_plan': [{'key': 'C1', 'stocks': 150, 'dates': 48, 'seed': 316227, 'universe_seed': 282843},
                  {'key': 'C2', 'stocks': 150, 'dates': 48, 'seed': 331777, 'universe_seed': 324161}],
    'partial_selection': 'EMPTY_SLOTS_REMAIN_CASH_NO_BACKFILL',
    'unknown_market': 'NO_ALLOCATION_EVIDENCE',
    'future_missing_exit': 'KEEP_SELECTED_STOCK_AND_MARK_OUTCOME_UNKNOWN',
    'basis': 'ADJUSTED_PROVIDER_OR_INTENTIONAL_CASH',
    'minimum_matched_cases_per_wave': 24,
    'minimum_matched_fraction': .90,
    'minimum_participation': .50,
    'minimum_quarter_blocks': 6,
    'minimum_global_disjoint_cases': 6,
    'minimum_mean_excess': .002,
    'minimum_policy_absolute_mean': 0.,
    'additional_active_round_trip_stress': .005,
    'interval': 'PAIRED_95_PERCENT_IID_AND_WEIGHTED_QUARTER_BLOCK',
    'nonoverlap': 'GLOBAL_C1_C2_CALENDAR_BEFORE_OUTCOME_FILTERING',
    'historical_inference': 'EXPOSED_ERA_CURRENT_ROSTER_RESEARCH_NOT_FUTURE_HOLDOUT',
    'unsupported_claims': ['GLOBAL_OPTIMUM', 'FULL_MARKET_COVERAGE', '40_120_DAY_VALIDATION',
                           'LIMIT_UP_PREDICTION', 'INTRADAY_EXECUTION_ACCEPTANCE', 'FUTURE_PROFIT'],
    'automatic_weight_adoption': False, 'automatic_orders_authorized': False,
}


def protocol_hash():
    return hashlib.sha256(json.dumps(PROTOCOL, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def protocol_manifest(cfg=None):
    from v192_checkpoint import code_digest
    return {'protocol': PROTOCOL, 'protocol_hash': protocol_hash(), 'code_hash': code_digest(),
            'registered_at': datetime.now(timezone.utc).isoformat(),
            'settings': asdict(cfg) if cfg is not None else None,
            'status': 'REGISTERED_NOT_PERFORMANCE_VALIDATED'}


def finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def benchmark_record(day, date, h, cfg):
    """A suspended benchmark is unavailable, NOT a zero return benchmark."""
    b = day.loc[day.ticker.eq(cfg.benchmark)]
    row = b.iloc[0] if len(b) == 1 else {}
    outcome = str(row.get(f'outcome_state_{h}', 'NO_BENCHMARK_BAR'))
    value = finite(row.get(f'net_{h}'))
    if not outcome.startswith('ASSUMED_OPEN_FILL'):
        value = None
    return {'date': str(pd.Timestamp(date).date()), 'horizon': h, 'strategy': 'benchmark_0050',
            'mean_net': value, 'complete': value is not None, 'selected': int(len(b) == 1),
            'case_reason': outcome, 'price_basis': row.get(f'return_basis_{h}', 'UNKNOWN'),
            'path_complete': bool(row.get(f'path_complete_{h}', False)),
            'mean_mae': finite(row.get(f'mae_{h}')), 'mean_position_mdd': finite(row.get(f'mdd_{h}')),
            'filled': int(value is not None), 'slots': 1}


def allocation_decision(market_state, selected_at_t):
    """Only T information is accepted. Future returns/completeness are not inputs."""
    if market_state not in ('CASH', 'INDEX_LEAD', 'STOCK_SELECTION'):
        return 'UNKNOWN'
    if market_state == 'STOCK_SELECTION' and selected_at_t == 0:
        return 'CASH_NO_SETUP'
    return market_state


def policy_record(cascade, market_state, bm):
    decision = allocation_decision(market_state, int(cascade.get('selected', 0)))
    if decision in ('CASH', 'CASH_NO_SETUP'):
        p = dict(cascade, selected=0, slots=5, filled=0, missing=0, complete=True,
                 mean_net=0., mean_mae=0., mean_position_mdd=0., path_complete=True,
                 price_basis='CASH', outcome_states={'PLANNED_CASH': 5})
    elif decision == 'INDEX_LEAD':
        p = dict(bm)
    elif decision == 'STOCK_SELECTION':
        # Even if its future exit is missing, do not replace the selected stock.
        p = dict(cascade)
    else:
        p = dict(cascade, selected=0, filled=0, complete=False, mean_net=None,
                 path_complete=False, price_basis='UNKNOWN')
    p.update(strategy='v202_policy', v202_policy_state=decision,
             case_reason='FINAL_T_ONLY_' + decision,
             decision_uses_future_outcomes=False)
    return p


def _pool_record(day, date, h, cfg):
    from v19_backtest import preselected_result
    q = day.loc[day.eligible.fillna(False) & day.ticker.ne(cfg.benchmark)].copy()
    for col in ('p197_liquidity','p197_annual_high'):
        q=q.loc[np.isfinite(pd.to_numeric(q.get(col,pd.Series(np.nan,index=q.index)),errors='coerce'))]
    # Same date-T rankable universe, no ex-post removal of missing exits.
    if q.empty:
        return {'date': str(pd.Timestamp(date).date()), 'horizon': h, 'strategy': 'equal_weight_universe',
                'selected': 0, 'complete': False, 'mean_net': None, 'price_basis': 'UNKNOWN'}
    # Do not use Settings validation to restrict the size of this diagnostic pool.
    class PoolCfg:
        top_k = len(q)
    r, _ = preselected_result(q, date, h, PoolCfg(), 'equal_weight_universe')
    r['definition'] = 'ALL_DATE_T_CORE_RANKABLE_STOCKS_EQUAL_WEIGHT_SAME_FILL_CONVENTION'
    return r


def clean_case(day, date, h, cfg):
    """Frozen O(n log n) replay; no legacy nested weight tournament."""
    from v20_model import build_v202_scores, rank_v202_day, v202_market_state, v20_anchor
    from v19_backtest import preselected_result, selected_result
    from v19_config import TECH, prior
    records, trades = [], []
    date_text = str(pd.Timestamp(date).date())
    eligible = day.loc[day.eligible.fillna(False) & day.ticker.ne(cfg.benchmark)].copy()
    scores = build_v202_scores(eligible)
    core = scores.loc[scores.v202_core.ge(PROTOCOL['core_floor']) & np.isfinite(scores.v202_core)]
    core = core.sort_values(['v202_core', 'ticker'], ascending=[False, True])
    # Freeze the core roster BEFORE the gates. Gates remove; they never refill.
    core = core.head(cfg.top_k).copy()
    core['score'] = core['v202_core']; core['factor_coverage'] = 1.
    confirm = core.loc[core.v202_confirm.ge(50)]
    timing = confirm.loc[confirm.v202_timing.ge(55) & ~confirm.v202_overheat &
                         confirm.bias20.notna() & confirm.rsi.notna()]
    actual = core if h == 60 else confirm if h == 20 else timing
    for name, q in [('v203_no_gates', core), ('v203_confirm_only', confirm),
                    ('v203_full_gates', timing), ('v202_core_cascade', actual)]:
        r, tr = preselected_result(q, date, h, cfg, name)
        r['decision_at'] = date_text; r['decision_uses_future_outcomes'] = False
        records.append(r); trades.extend(tr.to_dict('records'))
    cr = next(r for r in records if r['strategy'] == 'v202_core_cascade')
    bm = benchmark_record(day, date, h, cfg)
    records.extend([bm, _pool_record(day, date, h, cfg), policy_record(cr, v202_market_state(day), bm)])
    # Limited falsification set: perturb weights, remove each core factor.
    # Diagnostic results NEVER select weights or authorize deployment.
    shadows = {'liquidity_only': {'p197_liquidity': 1.},
               'high_only': {'p197_annual_high': 1.},
               'core75_25': {'p197_liquidity': .75, 'p197_annual_high': .25},
               'core85_15': {'p197_liquidity': .85, 'p197_annual_high': .15}}
    for label, w in shadows.items():
        score = sum(pd.to_numeric(scores[k], errors='coerce') * v for k, v in w.items())
        q = scores.assign(score=score, factor_coverage=1.)
        q = q.loc[q.score.ge(55) & np.isfinite(q.score)].sort_values(['score', 'ticker'], ascending=[False, True]).head(cfg.top_k)
        r, tr = preselected_result(q, date, h, cfg, 'v203_diagnostic_' + label)
        r['diagnostic_only'] = True; records.append(r)
        trades.extend(tr.to_dict('records'))
    # Kept for stage/reporter compatibility, with explicit engine attribution.
    records.append(dict(cr, strategy='adaptive', engine='FINAL_CORE_CASCADE'))
    baseline, _ = selected_result(day, date, prior(h, TECH), h, cfg, 'baseline')
    baseline['engine'] = 'LEGACY_CONTROL_ONLY'; records.append(baseline)
    factors = []
    for f in ('p197_liquidity', 'p197_annual_high', 'p197_downside', 'p197_trend_eff',
              'p202_rel5', 'p202_rel20', 'p202_rel60', 'p202_volume_impulse', 'p202_entry_quality'):
        q = eligible.reindex(columns=[f, f'net_{h}']).replace([np.inf, -np.inf], np.nan).dropna()
        ic = None
        if len(q) >= 10 and q[f].nunique() > 1 and q[f'net_{h}'].nunique() > 1:
            ic = finite(q[f].rank().corr(q[f'net_{h}'].rank()))
        factors.append({'date': date_text, 'horizon': h, 'factor': f, 'observed_pairs': len(q),
                        'eligible_count': len(eligible), 'rank_ic': ic,
                        'diagnostic_only': True, 'future_missing_not_imputed': True})
    return {'records': records, 'trades': trades,
            'fit': {'date': date_text, 'cutoff': date_text, 'horizon': h,
                    'status': 'FINAL_FIXED_NO_REFIT', 'weights': v20_anchor(h), 'allocation_allowed': False},
            'trials': [], 'factors': [], 'final_factors': factors}


def global_disjoint(reports, h):
    """Greedy chronological selection across BOTH waves, before observing returns."""
    calendars = set()
    for r in reports:
        calendars.update(str(x)[:10] for x in r.get('calendar_dates', []))
    cal = sorted(calendars); loc = {d: i for i, d in enumerate(cal)}
    windows = []
    for r in reports:
        stage = (r.get('settings') or {}).get('research_stage', '')
        for d in r.get('cutoffs', []):
            d = str(d)[:10]
            if d in loc and loc[d] + h < len(cal):
                windows.append((loc[d], loc[d] + h, stage, d))
    picked = set(); last_exit = -1
    for start, end, stage, d in sorted(windows):
        if start > last_exit:
            picked.add((stage, d)); last_exit = end
    return picked


def _index(report):
    ix = {}; dup = []
    for r in report.get('results', []):
        k = (str(r.get('date'))[:10], int(r.get('horizon', -1)), r.get('strategy'))
        if k in ix: dup.append(k)
        ix[k] = r
    return ix, dup


def _ok(row):
    return bool(row and row.get('complete') is True and finite(row.get('mean_net')) is not None)


def comparable(a, b):
    if not _ok(a) or not _ok(b): return False
    # Equal labels RAW/MIXED/UNKNOWN are not proof of comparable total returns.
    return a.get('price_basis') in ('ADJUSTED_PROVIDER', 'CASH') and b.get('price_basis') == 'ADJUSTED_PROVIDER'


def observations(report, h, left, right):
    ix, _ = _index(report)
    stage = (report.get('settings') or {}).get('research_stage', '')
    out = []
    for d in report.get('cutoffs', []):
        d = str(d)[:10]; a = ix.get((d, h, left)); b = ix.get((d, h, right))
        if comparable(a, b):
            slots = max(1, int(a.get('slots') or 5))
            exposure = min(1., max(0., float(a.get('filled') or 0)/slots))
            if left == 'v202_policy' and a.get('v202_policy_state') in ('INDEX_LEAD', 'CASH', 'CASH_NO_SETUP'):
                exposure = 0.  # Stress only the active-stock leg, not the same benchmark.
            out.append((stage, d, float(a['mean_net'])-float(b['mean_net']), exposure))
    return out


def stats(obs, disjoint=None, seed=203, reps=6000):
    empty = {'cases': 0, 'mean': None, 'median': None, 'bootstrap_90_low': None,
             'bootstrap_95_low': None, 'quarter_cluster_95_low': None, 'quarter_cluster_90_low': None,
             'quarter_clusters': 0, 'disjoint_cases': 0, 'disjoint_mean': None,
             'disjoint_bootstrap_95_low': None, 'extra_cost_50bp_mean': None, 'wave_means': {}}
    if not obs: return empty
    a = np.asarray([r[2] for r in obs], float)
    rng = np.random.default_rng(seed); reps = max(1000, int(reps))
    draws = a[rng.integers(len(a), size=(reps, len(a)))].mean(1)
    out = dict(empty, cases=len(a), mean=float(a.mean()), median=float(np.median(a)),
               bootstrap_90_low=float(np.quantile(draws, .05)), bootstrap_95_low=float(np.quantile(draws, .025)),
               bootstrap_95_high=float(np.quantile(draws, .975)))
    q = defaultdict(list); waves = defaultdict(list)
    for stage, d, v, exposure in obs:
        q[str(pd.Timestamp(d).to_period('Q'))].append(v); waves[stage].append(v)
    out['wave_means'] = {w: float(np.mean(v)) for w, v in sorted(waves.items())}
    out['quarter_clusters'] = len(q)
    if len(q) >= 2:
        sums = np.array([sum(v) for _, v in sorted(q.items())]); counts = np.array([len(v) for _, v in sorted(q.items())])
        ids = rng.integers(len(q), size=(reps, len(q)))
        # Cluster sums/counts preserve the date-weighted estimand; not mean-of-means.
        qb = sums[ids].sum(1)/counts[ids].sum(1)
        out.update(quarter_cluster_90_low=float(np.quantile(qb, .05)),
                   quarter_cluster_95_low=float(np.quantile(qb, .025)),
                   quarter_cluster_95_high=float(np.quantile(qb, .975)))
    ds = [v for w, d, v, _ in obs if (w, d) in (disjoint or set())]
    out['disjoint_cases'] = len(ds)
    if ds:
        out['disjoint_mean'] = float(np.mean(ds))
    if len(ds) >= 2:
        ar = np.array(ds); db = ar[rng.integers(len(ar), size=(reps, len(ar)))].mean(1)
        out['disjoint_bootstrap_95_low'] = float(np.quantile(db, .025))
    ordered = sorted(obs, key=lambda r: (r[1], r[0])); mid = len(ordered)//2
    for name, rows in [('first_half', ordered[:mid]), ('second_half', ordered[mid:])]:
        out[name+'_mean'] = float(np.mean([x[2] for x in rows])) if rows else None
    out['leave_one_date_out_min_mean'] = float(min((a.sum()-v)/(len(a)-1) for v in a)) if len(a) > 1 else None
    out['extra_cost_50bp_mean'] = float(np.mean([v-PROTOCOL['additional_active_round_trip_stress']*e for _, _, v, e in obs]))
    out['interval_warning'] = 'DESCRIPTIVE_DEPENDENCE_SENSITIVITY_NOT_NEW_BLIND_SIGNIFICANCE'
    return out


def summarize_final(reports, reps=6000):
    issues = []; waves = []; rows = []; stages = []
    seen = set(); fingerprints = set(); code_hashes = set()
    for r in reports:
        s = r.get('settings') or {}; stage = s.get('research_stage'); stages.append(stage)
        if stage not in CLEAN_STAGES: issues.append('WRONG_STAGE')
        if r.get('version') != PROTOCOL_VERSION: issues.append('WRONG_ENGINE_VERSION')
        if r.get('final_protocol_hash') != protocol_hash(): issues.append('PROTOCOL_NOT_MATCHED')
        code_hashes.add(r.get('final_code_hash'))
        if r.get('data_kind') != 'PROVIDER_HISTORY': issues.append('NOT_REAL_PROVIDER_HISTORY')
        if not str((r.get('manifest') or {}).get('scope', '')).startswith('V202_TWSE_TPEX_OFFICIAL_CURRENT'):
            issues.append('OFFICIAL_CURRENT_ROSTER_NOT_VERIFIED')
        if not r.get('calendar_dates'): issues.append('MISSING_CALENDAR')
        _, duplicate_rows = _index(r)
        if duplicate_rows: issues.append('DUPLICATE_RESULT_ROWS')
        cutoffs = [str(d)[:10] for d in r.get('cutoffs', [])]
        if len(cutoffs) != len(set(cutoffs)): issues.append('DUPLICATE_CUTOFFS')
        if seen.intersection(cutoffs): issues.append('CROSS_WAVE_EXACT_DATE_REUSE')
        seen.update(cutoffs)
        if set(cutoffs).intersection(str(x)[:10] for x in s.get('excluded_cutoffs', [])):
            issues.append('EXPOSED_DATE_REUSE')
        if len(cutoffs) != 48: issues.append('WRONG_DATE_COUNT')
        if r.get('execution_status') != 'STAGE_COMPLETE': issues.append('EXECUTION_INCOMPLETE')
        q = (r.get('manifest') or {}).get('universe_quality') or {}
        roster_hash = r.get('final_roster_hash') or q.get('catalog_fingerprint')
        if roster_hash: fingerprints.add(roster_hash)
        else: issues.append('MISSING_ROSTER_FINGERPRINT')
        wave_spec=next((w for w in PROTOCOL['wave_plan'] if w['key']==stage),{})
        for key in ('stocks','dates','seed','universe_seed'):
            if s.get(key)!=wave_spec.get(key): issues.append('WAVE_SETTINGS_NOT_MATCHED')
        if s.get('top_k')!=5 or list(s.get('horizons') or [])!=[5,20,60]:
            issues.append('HORIZON_OR_SLOT_SETTINGS_CHANGED')
        if finite(q.get('download_coverage')) is None or float(q.get('download_coverage',0)) < PROTOCOL['minimum_download_coverage']:
            issues.append('INSUFFICIENT_DOWNLOAD_COVERAGE')
        waves.append({'wave': stage, 'cutoffs': len(cutoffs), 'data_hash': r.get('data_hash'),
                      'historical_membership_verified': False})
    if len(stages) != 2 or set(stages) != set(CLEAN_STAGES): issues.append('REQUIRES_EXACTLY_C1_C2')
    if len(code_hashes) != 1 or None in code_hashes: issues.append('CODE_HASH_NOT_MATCHED')
    if len(fingerprints) > 1: issues.append('ROSTER_CHANGED_BETWEEN_WAVES')
    for h in (5, 20, 60):
        disjoint = global_disjoint(reports, h)
        row = {'horizon': h, 'global_predeclared_disjoint_count': len(disjoint)}
        for left, right, label in [('v202_core_cascade', 'equal_weight_universe', 'selection_vs_same_pool'),
                                    ('v202_core_cascade', 'benchmark_0050', 'selection_vs_0050'),
                                    ('v202_policy', 'benchmark_0050', 'policy_vs_0050'),
                                    ('v203_confirm_only', 'v203_no_gates', 'confirm_gate_increment'),
                                    ('v203_full_gates', 'v203_no_gates', 'full_gate_increment')]:
            obs = sum([observations(r, h, left, right) for r in reports], [])
            row[label] = stats(obs, disjoint, seed=20300+h, reps=reps)
            lv=[];rv=[]
            for report in reports:
                ix,_=_index(report)
                for d in report.get('cutoffs',[]):
                    a=ix.get((str(d)[:10],h,left));b=ix.get((str(d)[:10],h,right))
                    if comparable(a,b):lv.append(float(a['mean_net']));rv.append(float(b['mean_net']))
            row[label]['candidate_mean_net']=float(np.mean(lv)) if lv else None
            row[label]['reference_mean_net']=float(np.mean(rv)) if rv else None
        participation = {}; selected = {}; missing = {}
        for r in reports:
            stage = (r.get('settings') or {}).get('research_stage', '')
            ix, _ = _index(r); ds = r.get('cutoffs', [])
            vals = [ix.get((str(d)[:10], h, 'v202_core_cascade'), {}) for d in ds]
            participation[stage] = sum(int(x.get('selected') or 0)>0 for x in vals)/max(1, len(ds))
            selected[stage] = sum(int(x.get('selected') or 0) for x in vals)
            missing[stage] = sum(not _ok(x) for x in vals)
        row.update(participation_by_wave=participation, selected_slots_by_wave=selected, incomplete_cases_by_wave=missing)
        verdicts = {}
        for label in ('selection_vs_same_pool', 'policy_vs_0050'):
            m = row[label]; m['wave_case_counts'] = {}
            left, right = ('v202_core_cascade', 'equal_weight_universe') if label.startswith('selection') else ('v202_policy', 'benchmark_0050')
            for r in reports:
                stage = (r.get('settings') or {}).get('research_stage', '')
                m['wave_case_counts'][stage] = len(observations(r, h, left, right))
            reasons = list(issues)
            if set(m['wave_case_counts']) != set(CLEAN_STAGES): reasons.append('MISSING_WAVE')
            if any(n < max(PROTOCOL['minimum_matched_cases_per_wave'], math.ceil(48*.9)) for n in m['wave_case_counts'].values()):
                reasons.append('INSUFFICIENT_MATCHED_COVERAGE')
            if any(p < .5 for p in participation.values()): reasons.append('INSUFFICIENT_PARTICIPATION')
            if m['quarter_clusters'] < 6: reasons.append('TOO_FEW_TIME_BLOCKS')
            if m['disjoint_cases'] < 6: reasons.append('TOO_FEW_GLOBAL_DISJOINT_CASES')
            if reasons:
                verdict = 'INSUFFICIENT_EVIDENCE'
            elif not all(v > 0 for v in m['wave_means'].values()) or (m['mean'] or -1) < .002:
                verdict = 'NOT_PASSED'; reasons.append('MEAN_OR_CROSS_WAVE_DIRECTION_FAILED')
            elif any(finite(m.get(k)) is None or m[k] <= 0 for k in ('bootstrap_95_low', 'quarter_cluster_95_low', 'disjoint_bootstrap_95_low', 'extra_cost_50bp_mean')):
                verdict = 'NOT_PASSED'; reasons.append('UNCERTAINTY_OR_COST_STRESS_FAILED')
            elif label=='policy_vs_0050' and (m.get('candidate_mean_net') is None or m['candidate_mean_net']<=0):
                verdict='NOT_PASSED';reasons.append('POLICY_ABSOLUTE_RETURN_NONPOSITIVE')
            else: verdict = 'PASSED_HISTORICAL_RESEARCH_ONLY'
            verdicts[label] = {'status': verdict, 'reasons': sorted(set(reasons))}
        row['acceptance'] = verdicts
        row['selection_validity'] = verdicts['selection_vs_same_pool']['status']
        row['selection_cross_wave_positive'] = bool(len(row['selection_vs_same_pool']['wave_means'])==2 and all(v>0 for v in row['selection_vs_same_pool']['wave_means'].values()))
        rows.append(row)
    core = next(r for r in rows if r['horizon']==60)
    core_pass = all(x['status']=='PASSED_HISTORICAL_RESEARCH_ONLY' for x in core['acceptance'].values())
    core_insufficient = any(x['status']=='INSUFFICIENT_EVIDENCE' for x in core['acceptance'].values())
    return {'version': PROTOCOL_VERSION, 'status': 'FINAL_ACCEPTANCE_FINISHED', 'waves': waves, 'horizons': rows,
            'protocol_hash': protocol_hash(), 'integrity_issues': sorted(set(issues)),
            'core_verdict': 'PASSED_HISTORICAL_RESEARCH_ONLY' if core_pass else 'INSUFFICIENT_EVIDENCE' if core_insufficient else 'NOT_PASSED',
            'full_original_goal': 'NOT_CERTIFIED', 'unsupported_claims': PROTOCOL['unsupported_claims'],
            'automatic_weight_adoption': False, 'automatic_orders_authorized': False,
            'next_action': 'STOP_THIS_PROTOCOL_AFTER_TWO_WAVES_DO_NOT_SEARCH_UNTIL_PASS'}


def write_final_bundle(root, reports, summary, manifest):
    from v19_data import atomic_json
    root = Path(root); out = root/'final_acceptance'; out.mkdir(parents=True, exist_ok=True)
    atomic_json(out/'FINAL_RESULTS.json', summary); atomic_json(out/'FINAL_PROTOCOL.json', manifest)
    for report in reports:
        stage=(report.get('settings') or {}).get('research_stage','unknown')
        diagnostics=report.get('final_factor_diagnostics',[])
        atomic_json(out/(stage+'_FACTOR_DIAGNOSTICS.json'), diagnostics)
        atomic_json(out/(stage+'_DECISIONS.json'), [r for r in report.get('results',[])
                    if str(r.get('strategy','')).startswith(('v202_','v203_'))])
    text = ['# Final acceptance - Alpha Radar '+PROTOCOL_VERSION, '',
            'Core verdict: **'+summary['core_verdict']+'**',
            'Original full-market / intraday / 40-120-day goals: NOT CERTIFIED.', '',
            'This is the last scheduled historical cross-check of this protocol, not proof of optimality.', '',
            '| Horizon | Selection excess | Policy excess | Global disjoint selection cases | Selection verdict |',
            '|---|---:|---:|---:|---|']
    for h in summary['horizons']:
        s=h['selection_vs_same_pool'];p=h['policy_vs_0050']
        fmt=lambda x: '--' if x is None else f'{x:+.2%}'
        text.append(f"| {h['horizon']} | {fmt(s['mean'])} | {fmt(p['mean'])} | {s['disjoint_cases']} | {h['selection_validity']} |")
    text += ['', '## Integrity issues', json.dumps(summary['integrity_issues']), '',
             '## Interpretation', 'PASSED means limited historical support. NOT_PASSED means the frozen acceptance criteria failed.',
             'INSUFFICIENT_EVIDENCE means the data do not support certification; never substitute zero or loosen the rules.',
             'No result automatically changes weights, starts another wave, or permits orders.']
    (out/'FINAL_ACCEPTANCE.md').write_text('\n'.join(text), encoding='utf-8')
    for r in reports:
        stage=(r.get('settings') or {}).get('research_stage','unknown')
        atomic_json(out/(stage+'_results.json'),r)
        source=r.get('final_artifact_directory')
        if source:
            import shutil
            source=Path(source).resolve()
            if source.is_relative_to((root/'runs').resolve()):
                for name in ('selected_trades.csv','final_input_prices.csv.gz','input_manifest.json'):
                    if (source/name).is_file():shutil.copy2(source/name,out/(stage+'_'+name))
    contents = sorted(p for p in out.iterdir() if p.is_file() and p.name!='SHA256.json')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in contents}
    atomic_json(out/'SHA256.json',hashes)
    dest=root/'V20_FINAL_RESULTS.zip';temp=dest.with_suffix('.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
        for p in contents+[out/'SHA256.json']:z.write(p,p.name)
    temp.replace(dest)
    return str(dest)
