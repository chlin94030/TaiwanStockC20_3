"""Alpha Radar V20 hierarchical research model.

V20 is an architectural reset after V19.8.x repeated historical falsification.
It deliberately stops treating 5/20/60-day models as three independent alpha
engines.  Instead:

* 60-day CORE = evidence anchor.  Development replay across S4/S6/S7/S8
  favored a dual-sleeve portfolio: 40% pure liquidity-capacity sleeve and 60%
  liquidity+52-week-leadership sleeve.
* 20-day CONFIRM = 40% annual-high position + 40% relative-to-0050 strength +
  20% downside resilience.  S8 was encouraging, but this layer is a confirmer,
  not the primary source of expected alpha.
* 5-day TIMING = 50% trend efficiency + 50% relative strength.  It is only an
  entry-timing layer and is explicitly prevented from overruling weak CORE.

All inputs are point-in-time ranks already created by v197_ten_pillars.  No
missing optional fundamental/chip evidence is filled with zero.  Scores are
research rankings, not probabilities or automatic orders.
"""
from __future__ import annotations

from collections import defaultdict
import math
import numpy as np
import pandas as pd

V20_VERSION = '20.3-final'
V20_FREEZE_DATE = '2026-10-21'
V20_SOURCE = 'V20_2_CORE_FIRST_CLEAN_UNIVERSE_DUAL_BENCHMARK_PROTOCOL'

H = 'p197_annual_high'
T = 'p197_trend_eff'
R = 'p197_relative'
D = 'p197_downside'
L = 'p197_liquidity'

# The live single-score proxy keeps ranking simple on mobile.  The evidence
# portfolio itself is the two-sleeve construction below; 82/18 is the linear
# exposure implied by 40%*(100L) + 60%*(70L+30H), not a claim that the two
# ranking procedures are mathematically identical.
# V20.3-final live ranking no longer lets weak 5/20-day signals replace the only
# repeatedly useful stock-selection anchor.  All horizons start from CORE; the
# shorter horizons are filters/timing gates in rank_v202_day().
CORE_RANK = {L: .80, H: .20}
LIVE_ANCHORS = {
    5: dict(CORE_RANK),
    20: dict(CORE_RANK),
    60: dict(CORE_RANK),
}


PROFILE_NAMES = {
    5: 'v202_core_first_tactical_gate',
    20: 'v202_core_first_confirm_gate',
    60: 'v202_core_80_20',
}


LAYER_NAMES = {
    5: 'Tactical｜短線進場時機',
    20: 'Next Compounder｜中線確認',
    60: 'Core｜中長線核心',
}

# Reliability weights for a same-day composite view.  The 60-day layer owns
# the majority because it is the only layer for which the V19.8.x reports allow
# an apples-to-apples cross-stage portfolio-sleeve comparison.
HIERARCHY_WEIGHTS = {'core': .60, 'confirm': .25, 'timing': .15}
CORE_SLEEVES = {
    'capacity': {'allocation': .40, 'weights': {L: 1.00}},
    'leader': {'allocation': .60, 'weights': {L: .70, H: .30}},
}

# Derived from the attached S4/S6/S7/S8 development reports by mixing the two
# 60-day shadow-portfolio returns 40/60 and applying the already predeclared
# CAUTION->cash policy.  These are exposed-history diagnostics, not holdout P&L.
DEVELOPMENT_EVIDENCE = {
    '60d_dual_sleeve_excess_vs_0050': {
        'S4': .03063, 'S6': .03965, 'S7': .00801, 'S8': .00641,
        'pooled': .01789, 'worst_stage': .00641,
        'note': 'EXPOSED_DEVELOPMENT_REPLAY_NOT_FUTURE_HOLDOUT',
    },
    'S8_new_factor_diagnostics': {
        '5d_trend_relative_50_50_excess': .0075,
        '20d_high_relative_defense_40_40_20_excess': .0310,
        '60d_liquid_capacity_excess': .0202,
        'note': 'S8_ONLY_DIAGNOSTIC_NOT_CROSS_STAGE_CONFIRMED',
    },
}


def nearest_horizon(h: int) -> int:
    h = int(h)
    return min(LIVE_ANCHORS, key=lambda x: abs(x - h))


def v20_anchor(h: int) -> dict[str, float]:
    """Return V20 live ranking weights for a requested horizon."""
    return dict(LIVE_ANCHORS[nearest_horizon(h)])


def v20_profile_name(h: int) -> str:
    return PROFILE_NAMES[nearest_horizon(h)]


def v20_layer_name(h: int) -> str:
    return LAYER_NAMES[nearest_horizon(h)]


def v20_shadow_profiles(h: int) -> dict[str, dict[str, float]]:
    """Profiles emitted during future validation runs.

    The 60-day dual sleeve is audited from the two component shadow portfolios,
    rather than pretending an 82/18 score is identical to a sleeve portfolio.
    """
    h = nearest_horizon(h)
    if h == 5:
        return {PROFILE_NAMES[5]: v20_anchor(5)}
    if h == 20:
        return {PROFILE_NAMES[20]: v20_anchor(20)}
    return {
        'v20_core_capacity': {L: 1.0},
        'v20_core_leader_70_30': {L: .70, H: .30},
        PROFILE_NAMES[60]: v20_anchor(60),
    }


def market_gate_state(day: pd.DataFrame | None) -> str:
    if day is None or len(day) == 0 or 'p197_market_gate' not in day:
        return 'UNKNOWN'
    q = day.loc[day.get('eligible', True), 'p197_market_gate'] if 'eligible' in day else day['p197_market_gate']
    q = q.dropna().astype(str)
    return str(q.mode().iat[0]) if not q.empty else 'UNKNOWN'


def _num(x):
    try:
        y = float(x)
    except (TypeError, ValueError):
        return None
    return y if math.isfinite(y) else None


def build_layer_scores(frame: pd.DataFrame) -> pd.DataFrame:
    """Add V20 layer/composite scores without inventing missing evidence."""
    p = frame.copy()
    for col in (H, T, R, D, L):
        if col not in p:
            p[col] = np.nan
    p['v20_timing'] = .50 * pd.to_numeric(p[T], errors='coerce') + .50 * pd.to_numeric(p[R], errors='coerce')
    p['v20_confirm'] = (.40 * pd.to_numeric(p[H], errors='coerce') +
                        .40 * pd.to_numeric(p[R], errors='coerce') +
                        .20 * pd.to_numeric(p[D], errors='coerce'))
    p['v20_core_capacity'] = pd.to_numeric(p[L], errors='coerce')
    p['v20_core_leader'] = .70 * pd.to_numeric(p[L], errors='coerce') + .30 * pd.to_numeric(p[H], errors='coerce')
    p['v20_core'] = .40 * p['v20_core_capacity'] + .60 * p['v20_core_leader']
    p['v20_composite_raw'] = (.60 * p['v20_core'] + .25 * p['v20_confirm'] + .15 * p['v20_timing'])

    # Overheat/chase risk is a live execution overlay.  It is intentionally
    # small enough not to turn the timing layer into a fourth momentum score.
    bias = pd.to_numeric(p.get('bias20'), errors='coerce') if 'bias20' in p else pd.Series(np.nan, index=p.index)
    rsi = pd.to_numeric(p.get('rsi'), errors='coerce') if 'rsi' in p else pd.Series(np.nan, index=p.index)
    penalty = np.clip(bias.fillna(0).to_numpy() - 10.0, 0, 12) * .65
    penalty += np.clip(rsi.fillna(50).to_numpy() - 78.0, 0, 12) * .25
    p['v20_overheat_penalty'] = penalty
    p['v20_composite'] = p['v20_composite_raw'] - p['v20_overheat_penalty']
    return p


def entry_state(row, market_gate: str = 'UNKNOWN') -> str:
    """Research entry state; never an order instruction."""
    if str(market_gate) == 'CAUTION':
        return 'CASH_OR_NO_NEW_POSITION'
    bias = _num(row.get('bias20'))
    rsi = _num(row.get('rsi'))
    if (bias is not None and bias > 12) or (rsi is not None and rsi > 82):
        return 'WAIT_PULLBACK_OVERHEAT'
    core = _num(row.get('v20_core'))
    confirm = _num(row.get('v20_confirm'))
    timing = _num(row.get('v20_timing'))
    if core is None or confirm is None or timing is None:
        return 'INSUFFICIENT_V20_PRICE_EVIDENCE'
    if core < 55:
        return 'WATCH_CORE_NOT_STRONG'
    if market_gate == 'NEUTRAL' and confirm < 50:
        return 'WATCH_NEEDS_CONFIRMATION'
    if timing < 45:
        return 'WAIT_TIMING'
    return 'READY_FOR_MANUAL_REVIEW'


def decorate_candidates(rows: pd.DataFrame, market_gate: str = 'UNKNOWN') -> pd.DataFrame:
    if rows is None or rows.empty:
        return rows
    out = build_layer_scores(rows)
    out['v20_entry_state'] = [entry_state(row, market_gate) for _, row in out.iterrows()]
    return out


def _bootstrap(values: np.ndarray, seed: int, reps: int = 12000):
    if len(values) == 0:
        return (None, None, None, None)
    rng = np.random.default_rng(seed)
    draws = values[rng.integers(0, len(values), size=(max(2000, int(reps)), len(values)))].mean(axis=1)
    lo, med, hi = np.quantile(draws, [.05, .50, .95])
    return float(lo), float(med), float(hi), float(np.mean(draws > 0))


def audit_v20_report(report: dict, bootstrap_reps: int = 12000) -> dict:
    """Audit V20 shadow profiles from one validation report.

    5/20-day profiles are evaluated directly.  The 60-day result is the exact
    report-level two-sleeve mixture: 40% capacity portfolio + 60% leader
    portfolio.  A CAUTION date is held as cash, matching the existing risk gate.
    """
    records = report.get('results') or []
    by = {(str(r.get('date')), int(r.get('horizon') or -1), str(r.get('strategy'))): r
          for r in records if r.get('date') is not None}
    out = []
    for h in (5, 20, 60):
        dates = sorted({str(r.get('date')) for r in records if int(r.get('horizon') or -1) == h})
        rows = []
        for d in dates:
            bm = by.get((d, h, 'benchmark_0050'))
            if bm is None or not bm.get('complete') or _num(bm.get('mean_net')) is None:
                continue
            gate = by.get((d, h, 'ten_market_cash_RESEARCH_ONLY'))
            caution = bool(gate and gate.get('case_reason') == 'PREDECLARED_MARKET_RISK_CASH')
            if caution:
                cnet = 0.0
            elif h == 60:
                a = by.get((d, h, 'ten_shadow_v20_core_capacity'))
                b = by.get((d, h, 'ten_shadow_v20_core_leader_70_30'))
                if not a or not b or not a.get('complete') or not b.get('complete'):
                    continue
                av, bv = _num(a.get('mean_net')), _num(b.get('mean_net'))
                if av is None or bv is None or a.get('price_basis') != bm.get('price_basis') or b.get('price_basis') != bm.get('price_basis'):
                    continue
                cnet = .40 * av + .60 * bv
            else:
                strategy = 'ten_shadow_' + PROFILE_NAMES[h]
                cand = by.get((d, h, strategy))
                if not cand or not cand.get('complete') or _num(cand.get('mean_net')) is None:
                    continue
                if cand.get('price_basis') != bm.get('price_basis'):
                    continue
                cnet = float(cand['mean_net'])
            bnet = float(bm['mean_net'])
            rows.append((d, cnet, bnet, cnet - bnet))
        if not rows:
            out.append({'horizon': h, 'status': 'NO_COMPARABLE_V20_CASES'})
            continue
        ex = np.asarray([x[3] for x in rows], float)
        half = max(1, len(ex)//2)
        years = defaultdict(list)
        quarters = defaultdict(list)
        for d, _, _, e in rows:
            years[d[:4]].append(e)
            quarters[str(pd.Timestamp(d).to_period('Q'))].append(e)
        lo, med, hi, prob = _bootstrap(ex, 20000+h, bootstrap_reps)
        qvals = np.asarray([np.mean(v) for v in quarters.values()], float)
        qlo, qmed, qhi, qprob = _bootstrap(qvals, 21000+h, bootstrap_reps) if len(qvals) >= 2 else (None, None, None, None)
        out.append({
            'horizon': h,
            'profile': PROFILE_NAMES[h] if h != 60 else 'v20_core_dual_sleeve_40_60',
            'paired_cases': len(rows),
            'mean_net': float(np.mean([x[1] for x in rows])),
            'benchmark_mean': float(np.mean([x[2] for x in rows])),
            'mean_excess': float(ex.mean()),
            'median_excess': float(np.median(ex)),
            'win_fraction_vs_0050': float(np.mean(ex > 0)),
            'first_half_mean_excess': float(ex[:half].mean()),
            'second_half_mean_excess': float(ex[half:].mean()) if half < len(ex) else None,
            'bootstrap_90_low': lo, 'bootstrap_90_median': med, 'bootstrap_90_high': hi,
            'bootstrap_probability_positive': prob,
            'quarter_cluster_90_low': qlo, 'quarter_cluster_90_median': qmed,
            'quarter_cluster_90_high': qhi, 'quarter_cluster_probability_positive': qprob,
            'year_mean_excess': {k: float(np.mean(v)) for k, v in sorted(years.items())},
            'new_holdout': False,
        })
    return {
        'version': V20_VERSION,
        'source': V20_SOURCE,
        'status': 'V20_HISTORICAL_RESEARCH_ONLY',
        'automatic_orders_authorized': False,
        'horizons': out,
    }


def evidence_summary() -> dict:
    return {
        'version': V20_VERSION,
        'freeze_date': V20_FREEZE_DATE,
        'source': V20_SOURCE,
        'hierarchy_weights': dict(HIERARCHY_WEIGHTS),
        'anchors': {str(k): dict(v) for k, v in LIVE_ANCHORS.items()},
        'core_sleeves': CORE_SLEEVES,
        'development_evidence': DEVELOPMENT_EVIDENCE,
        'automatic_orders_authorized': False,
    }



def summarize_auto_campaign(reports: list[dict]) -> dict:
    """Aggregate already-frozen V20 audits across automatic validation waves.

    This is deliberately diagnostic: it never tunes weights on the same waves.
    A horizon is marked CONSISTENT only when every available wave has positive
    mean excess and the pooled bootstrap 90% lower bound is positive.  The
    stricter quarter-cluster lower bound is reported separately rather than
    silently substituted with IID evidence.
    """
    wave_rows=[]
    pooled={5:[],20:[],60:[]}
    for i,report in enumerate(reports,1):
        if not report:
            continue
        audit=report.get('v20_audit') or audit_v20_report(report)
        wave=str((report.get('settings') or {}).get('research_stage') or f'W{i}')
        by_h={int(x.get('horizon')):x for x in audit.get('horizons',[]) if x.get('horizon') is not None}
        row={'wave':wave,'horizons':{}}
        for h in (5,20,60):
            x=by_h.get(h) or {}
            row['horizons'][str(h)]={
                'paired_cases':int(x.get('paired_cases') or 0),
                'mean_excess':_num(x.get('mean_excess')),
                'bootstrap_90_low':_num(x.get('bootstrap_90_low')),
                'quarter_cluster_90_low':_num(x.get('quarter_cluster_90_low')),
            }
        wave_rows.append(row)

        # Reconstruct paired excesses from the frozen V20 shadow profiles so
        # the pooled bootstrap is based on cases, not averages of averages.
        records=report.get('results') or []
        by={(str(r.get('date')),int(r.get('horizon') or -1),str(r.get('strategy'))):r
            for r in records if r.get('date') is not None}
        for h in (5,20,60):
            dates=sorted({str(r.get('date')) for r in records if int(r.get('horizon') or -1)==h})
            for d in dates:
                bm=by.get((d,h,'benchmark_0050'))
                if not bm or not bm.get('complete') or _num(bm.get('mean_net')) is None:
                    continue
                gate=by.get((d,h,'ten_market_cash_RESEARCH_ONLY'))
                caution=bool(gate and gate.get('case_reason')=='PREDECLARED_MARKET_RISK_CASH')
                if caution:
                    cand=0.0
                elif h==60:
                    a=by.get((d,h,'ten_shadow_v20_core_capacity'))
                    b=by.get((d,h,'ten_shadow_v20_core_leader_70_30'))
                    if not a or not b or not a.get('complete') or not b.get('complete'):
                        continue
                    av,bv=_num(a.get('mean_net')),_num(b.get('mean_net'))
                    if av is None or bv is None or a.get('price_basis')!=bm.get('price_basis') or b.get('price_basis')!=bm.get('price_basis'):
                        continue
                    cand=.40*av+.60*bv
                else:
                    c=by.get((d,h,'ten_shadow_'+PROFILE_NAMES[h]))
                    if not c or not c.get('complete') or _num(c.get('mean_net')) is None or c.get('price_basis')!=bm.get('price_basis'):
                        continue
                    cand=float(c['mean_net'])
                pooled[h].append(float(cand)-float(bm['mean_net']))

    summary=[]
    for h in (5,20,60):
        arr=np.asarray(pooled[h],float)
        if len(arr)==0:
            summary.append({'horizon':h,'status':'NO_CASES','paired_cases':0})
            continue
        lo,med,hi,prob=_bootstrap(arr,30000+h,12000)
        means=[]
        for row in wave_rows:
            val=(row.get('horizons') or {}).get(str(h),{}).get('mean_excess')
            if val is not None:
                means.append(float(val))
        all_positive=bool(means and all(v>0 for v in means))
        consistent=bool(all_positive and lo is not None and lo>0)
        summary.append({
            'horizon':h,'paired_cases':int(len(arr)),
            'pooled_mean_excess':float(arr.mean()),
            'pooled_median_excess':float(np.median(arr)),
            'pooled_bootstrap_90_low':lo,'pooled_bootstrap_90_high':hi,
            'pooled_probability_positive':prob,
            'wave_mean_excesses':means,
            'all_wave_means_positive':all_positive,
            'status':'CONSISTENT_ACROSS_AUTO_WAVES' if consistent else 'NOT_YET_CONSISTENT',
        })
    return {
        'version':V20_VERSION,
        'status':'V20_AUTO_CAMPAIGN_COMPLETE' if wave_rows else 'NO_AUTO_WAVES',
        'waves':wave_rows,'horizons':summary,
        'weights_retuned_on_same_waves':False,
        'automatic_orders_authorized':False,
    }


# ---------------------------------------------------------------------------
# V20.3-final: fix the validation target before searching more coefficients.
# ---------------------------------------------------------------------------
V202_FACTORS = ('p202_rel5','p202_rel20','p202_rel60','p202_volume_impulse','p202_entry_quality')
V202_CLEAN_STAGES = frozenset(('C1','C2'))


def add_v202_factors(panel: pd.DataFrame, cfg) -> pd.DataFrame:
    """Add a deliberately small set of horizon-matched, point-in-time factors.

    V19/V20.1 reused a 60-session relative-strength factor in 5/20-day layers.
    V20.3-final separates 5/20/60-session relative strength and adds two execution
    diagnostics.  Values are same-date cross-sectional percentile ranks, just
    like the p197 pillars.  Missing benchmark bars stay missing.
    """
    p=panel.copy()
    for c in V202_FACTORS:
        p[c]=np.nan
    if {'date','ticker','calc_close'}.issubset(p):
        cal=pd.DatetimeIndex(p.date.drop_duplicates()).sort_values()
        for ticker,ix in p.groupby('ticker',sort=False).groups.items():
            g=p.loc[ix].sort_values('date')
            c=pd.Series(pd.to_numeric(g.calc_close,errors='coerce').to_numpy(),index=pd.DatetimeIndex(g.date)).reindex(cal)
            for h in (5,20,60):
                r=c/c.shift(h)-1
                p.loc[g.index,f'ret{h}']=r.reindex(pd.DatetimeIndex(g.date)).to_numpy()
    benchmark=p[p.ticker.eq(cfg.benchmark)][['date','ret5','ret20','ret60']].drop_duplicates('date').set_index('date')
    for h in (5,20,60):
        stock=pd.to_numeric(p.get(f'ret{h}'),errors='coerce')
        bm=p.date.map(pd.to_numeric(benchmark.get(f'ret{h}'),errors='coerce') if f'ret{h}' in benchmark else pd.Series(dtype=float))
        p[f'p202_excess{h}_raw']=stock-bm
        p[f'p202_rel{h}']=stock-bm

    vr=pd.to_numeric(p.get('volume_ratio'),errors='coerce').clip(lower=0,upper=5)
    acc=pd.to_numeric(p.get('accumulation'),errors='coerce')
    # Volume expansion is useful only when it is not simply a one-bar blowoff.
    p['p202_volume_impulse']=np.log1p(vr)+(acc-50)/100.0

    orderly=pd.to_numeric(p.get('orderly_pullback'),errors='coerce')
    rsi=pd.to_numeric(p.get('rsi'),errors='coerce')
    bias=pd.to_numeric(p.get('bias20'),errors='coerce')
    rsi_quality=(100-(rsi-60).abs()*2.2).clip(0,100)
    bias_quality=(100-(bias-4).abs()*5.0).clip(0,100)
    entry=.45*orderly+.30*rsi_quality+.25*bias_quality
    entry=entry.mask((bias>12)|(rsi>82),entry-50)
    p['p202_entry_quality']=entry

    stocks=p.get('eligible',pd.Series(False,index=p.index)).fillna(False).astype(bool)&p.ticker.ne(cfg.benchmark)
    for col in V202_FACTORS:
        x=pd.to_numeric(p[col],errors='coerce').replace([np.inf,-np.inf],np.nan).where(stocks)
        valid=x.groupby(p.date).transform('count')>=int(getattr(cfg,'min_universe',10))
        p[col]=(x.groupby(p.date).rank(pct=True,method='average')*100).where(valid)
    return p


def v202_market_state(day: pd.DataFrame | None) -> str:
    """Separate stock-selection skill from index/cash allocation.

    CAUTION -> cash.  INDEX_LEAD means the large-cap index is in a bull regime
    while the sampled stock breadth is not broad enough to justify forcing a
    small/mid-cap basket to beat 0050.  This state uses date-T observations only.
    """
    if day is None or day.empty:
        return 'UNKNOWN'
    eligible=day.loc[day.get('eligible',True)] if 'eligible' in day else day
    regime='UNKNOWN'
    if 'regime' in eligible and not eligible['regime'].dropna().empty:
        regime=str(eligible['regime'].dropna().astype(str).mode().iat[0])
    breadth=None
    if 'p197_market_breadth' in eligible:
        q=pd.to_numeric(eligible['p197_market_breadth'],errors='coerce').dropna()
        if not q.empty: breadth=float(q.median())
    if regime not in ('BULL','BEAR','NEUTRAL') or breadth is None:
        return 'UNKNOWN'
    if regime=='BEAR' or (breadth is not None and breadth<.35):
        return 'CASH'
    if regime=='BULL' and breadth is not None and breadth<.55:
        return 'INDEX_LEAD'
    return 'STOCK_SELECTION'


def build_v202_scores(frame: pd.DataFrame) -> pd.DataFrame:
    p=frame.copy()
    needed=(H,L,T,D,'p202_rel5','p202_rel20','p202_rel60','p202_volume_impulse','p202_entry_quality')
    for c in needed:
        if c not in p:p[c]=np.nan
    def n(c): return pd.to_numeric(p[c],errors='coerce')
    from v20_final import PROTOCOL
    p['v202_core']=sum(n(k)*v for k,v in PROTOCOL['core_weights'].items())
    p['v202_confirm']=sum(n(k)*v for k,v in PROTOCOL['confirm_weights'].items())
    p['v202_timing']=sum(n(k)*v for k,v in PROTOCOL['timing_weights'].items())
    bias=pd.to_numeric(p.get('bias20'),errors='coerce') if 'bias20' in p else pd.Series(np.nan,index=p.index)
    rsi=pd.to_numeric(p.get('rsi'),errors='coerce') if 'rsi' in p else pd.Series(np.nan,index=p.index)
    p['v202_overheat']=(bias>PROTOCOL['bias_overheat_pct'])|(rsi>PROTOCOL['rsi_overheat'])
    return p


def rank_v202_day(day, horizon, cfg, top_k=None):
    """Same fixed core roster in replay and display. Gates never backfill it."""
    if int(horizon) not in (5,20,60):
        raise ValueError('UNSUPPORTED_FINAL_HORIZON: only 5/20/60 are validated here')
    if day is None or day.empty:return pd.DataFrame()
    mask=day.get('eligible',pd.Series(False,index=day.index)).fillna(False).astype(bool)
    q=build_v202_scores(day.loc[mask & day.ticker.ne(cfg.benchmark)].copy())
    if q.empty:return q
    k=int(top_k or cfg.top_k)
    q=q.loc[q.v202_core.ge(55) & np.isfinite(q.v202_core)]
    q=q.sort_values(['v202_core','ticker'],ascending=[False,True]).head(k).copy()
    if int(horizon) in (5,20):q=q.loc[q.v202_confirm.ge(50)]
    if int(horizon)==5:
        q=q.loc[q.v202_timing.ge(55)&(~q.v202_overheat)&q.bias20.notna()&q.rsi.notna()]
    q['score']=q.v202_core;q['factor_coverage']=1.
    return q


def v202_shadow_profiles(h: int) -> dict[str,dict[str,float]]:
    """Small predeclared challenger set; no brute-force weight search."""
    h=nearest_horizon(h)
    core={L:.80,H:.20}
    if h==5:
        return {
            'v202_core_80_20':core,
            'v202_timing_rel5_volume_entry_35_30_35':{'p202_rel5':.35,'p202_volume_impulse':.30,'p202_entry_quality':.35},
            'v202_linear_core70_timing30':{L:.56,H:.14,'p202_rel5':.105,'p202_volume_impulse':.09,'p202_entry_quality':.105},
        }
    if h==20:
        return {
            'v202_core_80_20':core,
            'v202_confirm_rel20_downside_trend_40_30_30':{'p202_rel20':.40,D:.30,T:.30},
            'v202_linear_core70_confirm30':{L:.56,H:.14,'p202_rel20':.12,D:.09,T:.09},
        }
    return {
        'v202_core_80_20':core,
        'v202_liquidity_only':{L:1.0},
        'v202_leader_70_30':{L:.70,H:.30},
        'v202_relative60_core':{L:.65,H:.15,'p202_rel60':.20},
    }


def _record_index(report: dict):
    return {(str(r.get('date')),int(r.get('horizon') or -1),str(r.get('strategy'))):r
            for r in (report.get('results') or []) if r.get('date') is not None}


def _dated_bootstrap_stats(pairs, seed: int, bootstrap_reps: int=12000, disjoint_dates=None):
    """Summarize dated excesses with IID, calendar-quarter and disjoint checks.

    The IID interval is kept for continuity, but overlapping 20/60-session
    windows can make it optimistic.  Quarter-cluster and predeclared disjoint
    subsets are therefore emitted beside it and are used by campaign validity
    labels.  None of these statistics retunes weights.
    """
    clean=[]
    for date,value in pairs:
        value=_num(value)
        if value is not None:
            clean.append((str(date),float(value)))
    if not clean:
        return {
            'cases':0,'mean':None,'median':None,
            'bootstrap_90_low':None,'bootstrap_90_high':None,'bootstrap_probability_positive':None,
            'quarter_clusters':0,'quarter_cluster_90_low':None,'quarter_cluster_90_high':None,
            'quarter_cluster_probability_positive':None,
            'disjoint_cases':0,'disjoint_mean':None,'disjoint_bootstrap_90_low':None,
            'disjoint_probability_positive':None,
        }
    a=np.asarray([v for _,v in clean],float)
    lo,med,hi,prob=_bootstrap(a,seed,bootstrap_reps)
    quarters=defaultdict(list)
    for d,v in clean:
        try:key=str(pd.Timestamp(d).to_period('Q'))
        except (ValueError,TypeError):key=str(d)[:7]
        quarters[key].append(v)
    qvals=np.asarray([np.mean(v) for _,v in sorted(quarters.items())],float)
    if len(qvals)>=2:
        qlo,qmed,qhi,qprob=_bootstrap(qvals,seed+1000,bootstrap_reps)
    else:qlo=qmed=qhi=qprob=None
    dset=set(str(x) for x in (disjoint_dates or []))
    dvals=np.asarray([v for d,v in clean if d in dset],float)
    if len(dvals)>=2:
        dlo,dmed,dhi,dprob=_bootstrap(dvals,seed+2000,bootstrap_reps)
    elif len(dvals)==1:
        dlo=dmed=dhi=float(dvals[0]);dprob=float(dvals[0]>0)
    else:dlo=dmed=dhi=dprob=None
    return {
        'cases':int(len(a)),'mean':float(a.mean()),'median':float(np.median(a)),
        'bootstrap_90_low':lo,'bootstrap_90_high':hi,'bootstrap_probability_positive':prob,
        'quarter_clusters':int(len(qvals)),'quarter_cluster_90_low':qlo,
        'quarter_cluster_90_high':qhi,'quarter_cluster_probability_positive':qprob,
        'disjoint_cases':int(len(dvals)),'disjoint_mean':float(dvals.mean()) if len(dvals) else None,
        'disjoint_bootstrap_90_low':dlo,'disjoint_bootstrap_90_high':dhi,
        'disjoint_probability_positive':dprob,
    }


def audit_v202_report(report: dict, bootstrap_reps: int=12000) -> dict:
    """Dual-benchmark audit with explicit overlap/participation diagnostics.

    Stock-ranking skill is tested against the same sampled pool.  Allocation
    skill is tested separately against 0050.  Because sampled 20/60-session
    holding windows overlap, IID bootstrap is not accepted as the only
    uncertainty measure; quarter-cluster and predeclared disjoint subsets are
    reported beside it.
    """
    from v20_final import comparable
    records=report.get('results') or []; by=_record_index(report); out=[]
    plan=report.get('sampling_plan') or {}
    disjoint_map=plan.get('disjoint_cutoffs') or {}
    for h in (5,20,60):
        excess_ew=[];excess_0050=[];policy_0050=[];raw=[]
        policy_states=defaultdict(int)
        dates=sorted({str(r.get('date')) for r in records if int(r.get('horizon') or -1)==h})
        benchmark_complete=0;cascade_complete=0;policy_complete=0
        for d in dates:
            c=by.get((d,h,'v202_core_cascade')); ew=by.get((d,h,'equal_weight_universe')); bm=by.get((d,h,'benchmark_0050')); pol=by.get((d,h,'v202_policy'))
            if bm and bm.get('complete') and _num(bm.get('mean_net')) is not None:
                benchmark_complete+=1
            if c and c.get('complete') and _num(c.get('mean_net')) is not None:
                cascade_complete+=1
                cv=float(c['mean_net']);raw.append(cv)
                if comparable(c,ew):
                    excess_ew.append((d,cv-float(ew['mean_net'])))
                if comparable(c,bm):
                    excess_0050.append((d,cv-float(bm['mean_net'])))
            if comparable(pol,bm):
                policy_complete+=1
                state=str(pol.get('v202_policy_state') or 'UNKNOWN')
                policy_states[state]+=1
                policy_0050.append((d,float(pol['mean_net'])-float(bm['mean_net'])))
        disjoint=disjoint_map.get(str(h)) or []
        out.append({
            'horizon':h,
            'requested_dates':len(dates),
            'benchmark_complete_dates':benchmark_complete,
            'cascade_complete_dates':cascade_complete,
            'cascade_participation_rate':(sum(int(by.get((d,h,'v202_core_cascade'),{}).get('selected') or 0)>0 for d in dates)/len(dates) if dates else None),
            'policy_complete_dates':policy_complete,
            'policy_state_counts':dict(sorted(policy_states.items())),
            'selection_vs_same_pool':_dated_bootstrap_stats(excess_ew,20220+h,bootstrap_reps,disjoint),
            'selection_vs_0050':_dated_bootstrap_stats(excess_0050,20240+h,bootstrap_reps,disjoint),
            'policy_vs_0050':_dated_bootstrap_stats(policy_0050,20260+h,bootstrap_reps,disjoint),
            'model_mean_net':float(np.mean(raw)) if raw else None,
        })
    return {
        'version':V20_VERSION,'status':'V2021_CLEAN_CORE_FIRST_RESEARCH','horizons':out,
        'primary_selection_benchmark':'SAME_POOL_EQUAL_WEIGHT',
        'allocation_benchmark':'0050.TW','weights_retuned_on_same_report':False,
        'overlap_policy':'REPORT_IID_PLUS_QUARTER_CLUSTER_AND_PREDECLARED_DISJOINT',
        'automatic_orders_authorized':False,
    }


def summarize_v202_campaign(reports):
    from v20_final import summarize_final
    return summarize_final(reports)


def live_v202_candidates(panel: pd.DataFrame, horizon: int, cfg, limit: int=20) -> tuple[pd.DataFrame,str]:
    """Current-date V20.3-final research candidates and allocation context."""
    if panel is None or panel.empty:return pd.DataFrame(),'UNKNOWN'
    date=panel.date.max(); day=panel[panel.date.eq(date)].copy();state=v202_market_state(day)
    if state in ('CASH','INDEX_LEAD','UNKNOWN'):
        return pd.DataFrame(),state
    q=rank_v202_day(day,horizon,cfg,top_k=int(cfg.top_k)).copy()
    if q.empty:return q,state
    q['setup']=np.where((q.get('reversal',0)>65)&(q.get('bias20',0)<5),'REVERSAL',
                        np.where(q.get('breakout',0)>65,'BREAKOUT','WATCH'))
    if {'revenue_yoy','eps_ttm','gross_margin'}.issubset(q):
        good=(q.revenue_yoy>0)&(q.eps_ttm>0)&(q.gross_margin>0)
        q.loc[good&(q.bias20<0)&(q.reversal>55),'setup']='GROWTH_PULLBACK'
    if {'support10','close','atr'}.issubset(q):
        q['stop_reference']=np.maximum(q.support10,q.close-1.8*q.atr)
        q['stop_reference']=np.minimum(q.stop_reference,q.close*.99)
        q['stop_distance_pct']=100*(q.close-q.stop_reference)/q.close
        q['reference_low']=q.close-.5*q.atr;q['reference_high']=q.close+.25*q.atr
        q['chase_ceiling']=q.close+np.minimum(q.atr,q.close*.03)
    q['is_buy_signal']=False
    h=nearest_horizon(horizon)
    q['v202_entry_state']=np.where(q.get('v202_overheat',False),'WAIT_PULLBACK_OVERHEAT',
                           np.where(h==5,'TIMING_GATE_PASSED' if len(q) else 'WAIT_TIMING',
                           np.where(h==20,'CONFIRM_GATE_PASSED','CORE_RESEARCH_CANDIDATE')))
    return q.head(limit),state
