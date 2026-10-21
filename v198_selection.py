"""V19.8.7 horizon-specific research hypotheses, S7 verdict, and frozen-candidate falsification.

V19.8.7 does **not** reinterpret exposed S1-S7 history as a blind holdout.
The S4 and S6 exposed replays are used once to freeze a simple,
low-dimensional forward candidate:

* 5 sessions: 52-week position (100%)
* 20 sessions: 52-week position (100%)
* 60 sessions: liquidity capacity (70%) + 52-week position (30%)

A contemporaneous market CAUTION gate can abstain to cash.  Before the freeze
date, historical adaptive fits keep the original causal/prequential V19.8
behavior; the frozen weights are only retrospective shadow diagnostics.  On or
after the freeze date they are allowed as a *forward research ranking* but are
still not authorization for automatic orders.
"""
from __future__ import annotations

from collections import defaultdict
import numpy as np
import pandas as pd

from v19_config import Settings, TECH, prior

FREEZE_DATE = '2026-10-16'
OPTIMIZATION_SOURCE = 'S4_100x12_PLUS_S6_150x18_ROBUST_MAXIMIN'
# Exact signal dates already exposed while freezing V19.8.6.  The chosen profile
# for each horizon maximizes the *worst-stage* bootstrap lower bound across the
# available S4 and S6 replays (tie-break: worst-stage mean excess).  S7 excludes
# every exact development cutoff below; it is still a historical cross-check,
# not a truly independent future holdout.
S4_DEVELOPMENT_CUTOFFS = (
    '2024-08-16','2024-11-06','2024-12-04','2025-03-20','2025-06-23','2025-07-03',
    '2025-08-07','2025-10-15','2025-11-12','2026-01-16','2026-06-30','2026-07-02',
)
S6_DEVELOPMENT_CUTOFFS = (
    '2024-08-19','2024-11-06','2024-12-03','2025-02-25','2025-03-18','2025-03-24',
    '2025-04-09','2025-06-19','2025-06-30','2025-07-11','2025-08-04','2025-10-09',
    '2025-10-13','2025-11-06','2026-01-12','2026-05-20','2026-06-22','2026-06-24',
)
DEVELOPMENT_CUTOFFS = tuple(sorted(set(S4_DEVELOPMENT_CUTOFFS) | set(S6_DEVELOPMENT_CUTOFFS)))
# S7 was a predeclared temporal cross-check and did NOT confirm the core 20/60
# gate.  These exact dates are now exposed too; S8 must exclude them rather than
# reusing them until a convenient result appears.
S7_CROSSCHECK_CUTOFFS = (
    '2024-08-21','2024-09-12','2024-10-09','2024-11-18','2024-11-20','2024-12-25',
    '2025-02-06','2025-03-11','2025-03-27','2025-04-29','2025-06-20','2025-06-25',
    '2025-07-30','2025-09-19','2025-10-08','2025-11-21','2025-12-11','2026-01-21',
    '2026-02-02','2026-03-20','2026-04-13','2026-05-21','2026-06-11','2026-06-29',
)
EXPOSED_CUTOFFS_THROUGH_S7 = tuple(sorted(set(DEVELOPMENT_CUTOFFS) | set(S7_CROSSCHECK_CUTOFFS)))
# S8 used a different stock-pool seed and time seed. V20.1's auto campaign
# confirmation stage excludes all of these exact dates as well.
S8_CROSSCHECK_CUTOFFS = (
    '2024-08-20','2024-09-19','2024-10-21','2024-10-30','2024-11-28','2025-01-08',
    '2025-02-14','2025-03-21','2025-04-15','2025-05-02','2025-06-16','2025-07-15',
    '2025-08-08','2025-09-08','2025-10-21','2025-10-31','2025-12-18','2026-01-05',
    '2026-01-27','2026-03-18','2026-04-22','2026-05-13','2026-06-05','2026-07-14',
)
EXPOSED_CUTOFFS_THROUGH_S8 = tuple(sorted(set(EXPOSED_CUTOFFS_THROUGH_S7) | set(S8_CROSSCHECK_CUTOFFS)))
S7_VERDICT = {
    5: 'REJECTED_FOR_0050_ALPHA_AND_TIME_STABILITY',
    20: 'SELECTION_IMPROVED_BUT_0050_ALPHA_FAILED',
    60: 'PROMISING_ALPHA_BUT_TIME_DEPENDENT_NOT_CONFIRMED',
}
HORIZON_GOVERNANCE = {
    5: 'EXPERIMENTAL_FORWARD_TRACKING',
    20: 'PRIMARY_FORWARD_CANDIDATE',
    60: 'SECONDARY_TIME_CONCENTRATION_WATCH',
}
OPTIMIZED_PROFILE_BY_HORIZON = {
    5: 'high_52',
    20: 'high_52',
    60: 'liquid_high_70_30',
}


def optimized_anchor(h):
    """Frozen low-dimensional candidate chosen from predeclared V19.8 profiles."""
    H='p197_annual_high';L='p197_liquidity'
    if h <= 7:
        return {H: 1.0}
    if h <= 30:
        return {H: 1.0}
    return {L: .70, H: .30}


def profiles_for_v198(h,cfg=Settings()):
    """Predeclared V19.8 diagnostic profiles retained for apples-to-apples replay."""
    core={'legacy_control':prior(h,TECH)}
    H='p197_annual_high';D='p197_downside';C='p197_compression';L='p197_liquidity'
    if h<=7:
        core.update({
            'high_52':{H:1.0},
            'lower_tail':{D:1.0},
            'high_defense_65_35':{H:.65,D:.35},
            'high_defense_break_45_35_20':{H:.45,D:.35,C:.20},
        })
    elif h<=30:
        core.update({
            'high_52':{H:1.0},
            'squeeze_breakout':{C:.6,H:.4},
            'defensive_breakout_35_40_25':{H:.35,D:.40,C:.25},
            'high_defense_60_40':{H:.60,D:.40},
        })
    else:
        core.update({
            'liquid_capacity':{L:1.0},
            'liquid_high_70_30':{L:.70,H:.30},
            'liquid_defense_70_30':{L:.70,D:.30},
            'liquid_breakout_65_35':{L:.65,C:.35},
        })
    if cfg.optional_data:
        # Observed fundamentals/chip data are accepted ONLY when available at T.
        # Strict disclosure policy is enforced by the base feature/data layers.
        if h<=30:
            core['trust_high_research']={'p197_trust':.45,H:.55}
        else:
            core['quality_liquid_research']={'p197_quality':.45,L:.35,H:.20}
    return core



def diagnostic_profiles_v1987(h, cfg=Settings()):
    """Predeclared S8 diagnostics; never auto-selected or auto-promoted.

    S7 showed that 52-week position alone did not deliver stable 5/20-session
    alpha versus 0050.  S8 therefore *diagnoses* whether explicit relative-to-
    benchmark strength helps, while keeping the frozen V19.8.6 weights intact.
    Any winner here becomes development evidence only and would need a later,
    newly frozen confirmation stage.
    """
    if str(getattr(cfg, 'research_stage', '') or '') != 'S8':
        return {}
    H='p197_annual_high'; D='p197_downside'; L='p197_liquidity'
    R='p197_relative'; T='p197_trend_eff'
    if h <= 7:
        return {
            's8_relative_only': {R: 1.0},
            's8_high_relative_50_50': {H: .50, R: .50},
            's8_trend_relative_50_50': {T: .50, R: .50},
        }
    if h <= 30:
        return {
            's8_relative_only': {R: 1.0},
            's8_high_relative_50_50': {H: .50, R: .50},
            's8_high_relative_defense_40_40_20': {H: .40, R: .40, D: .20},
        }
    return {
        's8_liquid_relative_70_30': {L: .70, R: .30},
    }

def market_gate_state(day) -> str:
    """Return the contemporaneous cross-sectional market gate for one cutoff."""
    if day is None or len(day)==0 or 'p197_market_gate' not in day:
        return 'UNKNOWN'
    q=day.loc[day.get('eligible', True), 'p197_market_gate'] if 'eligible' in day else day['p197_market_gate']
    q=q.dropna().astype(str)
    return str(q.mode().iat[0]) if not q.empty else 'UNKNOWN'


def forward_candidate_should_cash(day, info: dict | None) -> bool:
    """CAUTION is a risk abstention, not a claim that stock ranking got better."""
    return bool(((info or {}).get('v20_forward_candidate') or (info or {}).get('v1986_forward_candidate')) and market_gate_state(day)=='CAUTION')


def fit_before(panel,cutoff,h,cfg=Settings(),seed=1980,context=None):
    """Keep past V19.8 causal fits, activate the frozen candidate prospectively."""
    from v197_selection import fit_before as fit_prequential
    w,info,trace=fit_prequential(panel,cutoff,h,cfg,seed,context)
    info.update(factor_design='balanced_v198',
        hypothesis_status='PRE_REGISTERED_AFTER_EXPOSED_197_HISTORY_NOT_BLIND',
        non_target_profiles_can_be_zero=True,
        universe_expansion_does_not_prove_old_date_performance=True)

    cutoff_ts=pd.Timestamp(cutoff).normalize()

    # V20 is a later, explicit architecture freeze.  Historical cutoffs before
    # the V20 freeze still use the original prequential machinery; current/future
    # research rankings use V20's hierarchical anchors.
    from v20_model import V20_FREEZE_DATE, V20_SOURCE, v20_anchor, v20_profile_name, v20_layer_name
    if cutoff_ts >= pd.Timestamp(V20_FREEZE_DATE):
        anchor=v20_anchor(h)
        profile=v20_profile_name(h)
        prior_profile=info.get('selected_profile')
        info.update(
            selected_profile=profile, challenger_name=profile, challenger_weights=anchor,
            selected_factors=list(anchor), adopted_is_legacy_control=False, adopted_support=list(anchor),
            status='V202_CORE_FIRST_FORWARD_CANDIDATE', allocation_allowed=False,
            allocation_reason='V202_RESEARCH_RANKING_MANUAL_REVIEW_ONLY',
            v20_forward_candidate=True, v1986_forward_candidate=True,
            v20_freeze_date=V20_FREEZE_DATE, v20_source=V20_SOURCE,
            v20_profile=profile, v20_layer=v20_layer_name(h),
            v20_pre_freeze_selected_profile=prior_profile, rankings_are_probabilities=False,
        )
        trace.append({
            'stage':'v202_core_first_freeze','cutoff':str(cutoff_ts.date()),
            'horizon':int(h),'profile':profile,'weights':anchor,
            'freeze_date':V20_FREEZE_DATE,'source':V20_SOURCE,
            'not_independent_new_holdout':True,'automatic_orders_authorized':False,
        })
        return anchor,info,trace

    freeze_ts=pd.Timestamp(FREEZE_DATE)
    if cutoff_ts < freeze_ts:
        return w,info,trace

    anchor=optimized_anchor(h)
    profile=OPTIMIZED_PROFILE_BY_HORIZON[min(OPTIMIZED_PROFILE_BY_HORIZON, key=lambda x:abs(x-h))]
    prior_profile=info.get('selected_profile')
    info.update(
        selected_profile='v1986_'+profile,
        challenger_name='v1986_'+profile,
        challenger_weights=anchor,
        selected_factors=list(anchor),
        adopted_is_legacy_control=False,
        adopted_support=list(anchor),
        status='V1986_FROZEN_FORWARD_CANDIDATE',
        # Keep the governance/guarded portfolio in cash until genuinely new
        # evidence arrives.  The adaptive/research path still tracks the frozen
        # candidate, so forward evidence is collected without silently promoting it.
        allocation_allowed=False,
        allocation_reason=('S7_REJECTED_RESEARCH_SHADOW_ONLY' if int(h)<=30 else 'S7_60D_PROMISING_NOT_CONFIRMED'),
        v1986_forward_candidate=True,
        v1986_freeze_date=FREEZE_DATE,
        v1986_optimization_source=OPTIMIZATION_SOURCE,
        v1986_profile=profile,
        v1986_governance=HORIZON_GOVERNANCE.get(int(h),'FORWARD_RESEARCH_ONLY'),
        v1987_s7_verdict=S7_VERDICT.get(int(h),'UNASSESSED'),
        v1986_pre_freeze_selected_profile=prior_profile,
        rankings_are_probabilities=False,
    )
    trace.append({
        'stage':'v1986_forward_freeze',
        'cutoff':str(cutoff_ts.date()),
        'horizon':int(h),
        'profile':profile,
        'weights':anchor,
        'freeze_date':FREEZE_DATE,
        'source':OPTIMIZATION_SOURCE,
        'not_independent_new_holdout':True,
        'automatic_orders_authorized':False,
        'governance':HORIZON_GOVERNANCE.get(int(h),'FORWARD_RESEARCH_ONLY'),
    })
    return anchor,info,trace


def _profile_strategy(h):
    p=OPTIMIZED_PROFILE_BY_HORIZON[min(OPTIMIZED_PROFILE_BY_HORIZON, key=lambda x:abs(x-h))]
    return 'ten_shadow_'+p


def _safe_num(v):
    try:
        v=float(v)
    except (TypeError,ValueError):
        return None
    return v if np.isfinite(v) else None


def optimized_audit(report: dict, bootstrap_reps: int=12000):
    """Multi-angle audit of the frozen candidate using only supplied report rows.

    This is deliberately a *development* diagnostic.  It summarizes the already
    exposed S6 shadow rows by chronology, calendar year, market-caution gate,
    leave-one-out sensitivity and a deterministic bootstrap.  It does not turn
    the exposed dates into a fresh holdout and it does not search new weights.
    """
    records=report.get('results') or []
    if not records:
        return {'status':'NO_RESULTS','freeze_date':FREEZE_DATE,'new_holdout':False,'horizons':[]}
    by_key={(str(r.get('date')),int(r.get('horizon')),str(r.get('strategy'))):r
            for r in records if r.get('date') is not None and r.get('horizon') is not None}
    horizons=[]
    for h in (5,20,60):
        profile=OPTIMIZED_PROFILE_BY_HORIZON[h]
        strategy='ten_shadow_'+profile
        dates=sorted({str(r.get('date')) for r in records if int(r.get('horizon') or -1)==h})
        rows=[]
        caution_dates=[]
        for d in dates:
            cand=by_key.get((d,h,strategy));bm=by_key.get((d,h,'benchmark_0050'))
            gate=by_key.get((d,h,'ten_market_cash_RESEARCH_ONLY'))
            caution=bool(gate and gate.get('case_reason')=='PREDECLARED_MARKET_RISK_CASH')
            if caution:caution_dates.append(d)
            if bm is None or not bm.get('complete') or _safe_num(bm.get('mean_net')) is None:
                continue
            if caution:
                cnet=0.0
            else:
                if cand is None or not cand.get('complete') or _safe_num(cand.get('mean_net')) is None:
                    continue
                # Non-cash comparisons require the same known price basis.
                if cand.get('price_basis') != bm.get('price_basis'):
                    continue
                cnet=float(cand['mean_net'])
            bnet=float(bm['mean_net'])
            rows.append((d,cnet,bnet,cnet-bnet))
        if not rows:
            horizons.append({'horizon':h,'profile':profile,'status':'NO_COMPARABLE_CASES'})
            continue
        excess=np.asarray([x[3] for x in rows],float)
        net=np.asarray([x[1] for x in rows],float)
        benchmark=np.asarray([x[2] for x in rows],float)
        n=len(excess)
        half=max(1,n//2)
        years=defaultdict(list)
        for d,_,_,e in rows:years[d[:4]].append(e)
        year_excess={y:float(np.mean(v)) for y,v in sorted(years.items())}
        loo=[]
        if n>1:
            total=float(excess.sum())
            loo=[(total-float(excess[i]))/(n-1) for i in range(n)]
        # Deterministic non-parametric bootstrap over already exposed paired dates.
        rng=np.random.default_rng(198600+h)
        reps=max(1000,int(bootstrap_reps))
        draws=rng.integers(0,n,size=(reps,n))
        boot=excess[draws].mean(axis=1)
        lo,med,hi=np.quantile(boot,[.05,.50,.95])
        all_years_positive=bool(year_excess and all(v>0 for v in year_excess.values()))
        loo_min=float(min(loo)) if loo else None
        # Evidence labels are intentionally conservative and do not authorize orders.
        second_half=float(excess[half:].mean()) if half<n else None
        first_half=float(excess[:half].mean())
        if n < 12:
            status='INSUFFICIENT_COMPARABLE_CASES'
        elif lo>0 and (loo_min is None or loo_min>0) and all_years_positive:
            # A large chronology shift is evidence of regime concentration, even
            # when the exposed-sample bootstrap is positive.
            if second_half is not None and abs(second_half-first_half)>.05:
                status='ROBUST_BUT_TIME_CONCENTRATED_NEEDS_CONFIRMATION'
            else:
                status='ROBUST_EXPOSED_SAMPLE_NOT_HOLDOUT'
        elif float(excess.mean())>0 and (loo_min is None or loo_min>0):
            status='PROMISING_NEEDS_NEW_TIMEPOINT_CONFIRMATION'
        else:
            status='UNSTABLE_EXPOSED_SAMPLE'
        # Compare the chosen profile with every predeclared shadow profile on
        # the same report.  This is robustness evidence, not a new search over
        # continuous weights.  Segment ranks use only dates shared by all
        # profiles, preventing a profile with extra easy dates from winning.
        shadow_strategies=sorted({str(r.get('strategy')) for r in records
                                  if int(r.get('horizon') or -1)==h
                                  and str(r.get('strategy','')).startswith('ten_shadow_')})
        profile_maps={}
        comparisons=[]
        for ss in shadow_strategies:
            rr=[]
            for d in dates:
                cand=by_key.get((d,h,ss));bm=by_key.get((d,h,'benchmark_0050'))
                gate=by_key.get((d,h,'ten_market_cash_RESEARCH_ONLY'))
                caution=bool(gate and gate.get('case_reason')=='PREDECLARED_MARKET_RISK_CASH')
                if bm is None or not bm.get('complete') or _safe_num(bm.get('mean_net')) is None:
                    continue
                if caution:
                    cnet=0.0
                else:
                    if cand is None or not cand.get('complete') or _safe_num(cand.get('mean_net')) is None:
                        continue
                    if cand.get('price_basis') != bm.get('price_basis'):
                        continue
                    cnet=float(cand['mean_net'])
                e=cnet-float(bm['mean_net']);rr.append((d,e))
            pm=dict(rr);profile_maps[ss]=pm
            if rr:
                arr=np.asarray([v for _,v in rr],float);nn=len(arr)
                prng=np.random.default_rng(198600+h+sum(ord(c) for c in ss))
                pboot=arr[prng.integers(0,nn,size=(max(1000,int(bootstrap_reps)),nn))].mean(axis=1)
                comparisons.append({
                    'profile':ss.replace('ten_shadow_',''),
                    'paired_cases':nn,
                    'mean_excess':float(arr.mean()),
                    'median_excess':float(np.median(arr)),
                    'win_fraction_vs_0050':float(np.mean(arr>0)),
                    'worst_excess':float(arr.min()),
                    'bootstrap_90_low':float(np.quantile(pboot,.05)),
                })
        common_dates=set(dates)
        for pm in profile_maps.values():common_dates &= set(pm)
        common_dates=sorted(common_dates)
        segment_ranks={}
        if common_dates and strategy in profile_maps:
            segments={'all':common_dates,
                      'first_half':common_dates[:max(1,len(common_dates)//2)],
                      'second_half':common_dates[max(1,len(common_dates)//2):]}
            for yy in sorted({d[:4] for d in common_dates}):
                segments[yy]=[d for d in common_dates if d.startswith(yy)]
            for label,ds in segments.items():
                if not ds:continue
                ranking=sorted(((float(np.mean([pm[d] for d in ds])),ss)
                                for ss,pm in profile_maps.items()),reverse=True)
                selected_rank=next((i+1 for i,(_,ss) in enumerate(ranking) if ss==strategy),None)
                segment_ranks[label]={'rank':selected_rank,'profiles':len(ranking),
                                      'selected_mean_excess':float(np.mean([profile_maps[strategy][d] for d in ds]))}
        comparisons.sort(key=lambda x:(x['bootstrap_90_low'],x['mean_excess']),reverse=True)
        selected_boot_rank=next((i+1 for i,x in enumerate(comparisons) if x['profile']==profile),None)
        if h==5 and status=='PROMISING_NEEDS_NEW_TIMEPOINT_CONFIRMATION':
            status='EXPERIMENTAL_SHORT_HORIZON_NEEDS_FORWARD_CONFIRMATION'

        # V19.8.7 robustness diagnostics: distinguish stock-selection skill from
        # benchmark allocation and account for temporal clustering.  These are
        # diagnostics only; they do not refit the frozen weights.
        raw_excess=[]; gain_legacy=[]; gain_universe=[]
        for d in dates:
            cand=by_key.get((d,h,strategy)); bm=by_key.get((d,h,'benchmark_0050'))
            legacy=by_key.get((d,h,'baseline')); uni=by_key.get((d,h,'equal_weight_universe'))
            if cand is None or bm is None or not cand.get('complete') or not bm.get('complete'):
                continue
            cv=_safe_num(cand.get('mean_net')); bv=_safe_num(bm.get('mean_net'))
            if cv is None or bv is None or cand.get('price_basis') != bm.get('price_basis'):
                continue
            raw_excess.append(cv-bv)
            if legacy is not None and legacy.get('complete') and _safe_num(legacy.get('mean_net')) is not None:
                gain_legacy.append(cv-float(legacy['mean_net']))
            if uni is not None and uni.get('complete') and _safe_num(uni.get('mean_net')) is not None:
                gain_universe.append(cv-float(uni['mean_net']))
        raw_mean_excess=float(np.mean(raw_excess)) if raw_excess else None
        raw_gain_legacy=float(np.mean(gain_legacy)) if gain_legacy else None
        raw_gain_universe=float(np.mean(gain_universe)) if gain_universe else None

        quarter_groups=defaultdict(list)
        for d,_,_,e in rows:
            quarter_groups[str(pd.Timestamp(d).to_period('Q'))].append(float(e))
        quarter_means={q:float(np.mean(v)) for q,v in sorted(quarter_groups.items())}
        quarter_vals=np.asarray(list(quarter_means.values()),float)
        qlo=qmed=qhi=qprob=None
        if len(quarter_vals)>=2:
            qrng=np.random.default_rng(198700+h)
            qreps=max(2000,int(bootstrap_reps))
            qdraw=quarter_vals[qrng.integers(0,len(quarter_vals),size=(qreps,len(quarter_vals)))].mean(axis=1)
            qlo,qmed,qhi=[float(x) for x in np.quantile(qdraw,[.05,.50,.95])]
            qprob=float(np.mean(qdraw>0))

        year_keys=sorted(years)
        leave_year=[]
        for yy in year_keys:
            vals=[float(e) for d,_,_,e in rows if not str(d).startswith(str(yy))]
            if vals: leave_year.append(float(np.mean(vals)))
        leave_year_min=min(leave_year) if leave_year else None
        terciles=[]
        for ids in np.array_split(np.arange(n),3):
            if len(ids): terciles.append(float(excess[ids].mean()))

        horizons.append({
            'horizon':h,
            'profile':profile,
            'weights':optimized_anchor(h),
            'governance':HORIZON_GOVERNANCE.get(h,'FORWARD_RESEARCH_ONLY'),
            'status':status,
            'paired_cases':n,
            'caution_cash_dates':caution_dates,
            'mean_net':float(net.mean()),
            'benchmark_mean':float(benchmark.mean()),
            'mean_excess':float(excess.mean()),
            'median_excess':float(np.median(excess)),
            'win_fraction_vs_0050':float(np.mean(excess>0)),
            'q25_excess':float(np.quantile(excess,.25)),
            'worst_excess':float(np.min(excess)),
            'leave_one_out_min_mean_excess':loo_min,
            'first_half_mean_excess':first_half,
            'second_half_mean_excess':second_half,
            'year_mean_excess':year_excess,
            'bootstrap_90_low':float(lo),
            'bootstrap_median':float(med),
            'bootstrap_90_high':float(hi),
            'bootstrap_probability_mean_excess_positive':float(np.mean(boot>0)),
            'raw_mean_excess_vs_0050':raw_mean_excess,
            'raw_mean_gain_vs_legacy':raw_gain_legacy,
            'raw_mean_excess_vs_equal_weight_universe':raw_gain_universe,
            'market_gate_alpha_delta':(float(excess.mean())-raw_mean_excess) if raw_mean_excess is not None else None,
            'quarter_mean_excess':quarter_means,
            'quarter_cluster_bootstrap_90_low':qlo,
            'quarter_cluster_bootstrap_median':qmed,
            'quarter_cluster_bootstrap_90_high':qhi,
            'quarter_cluster_probability_positive':qprob,
            'leave_one_year_out_min_mean_excess':leave_year_min,
            'tercile_mean_excess':terciles,
            's7_verdict':S7_VERDICT.get(h,'UNASSESSED'),
            'profile_comparison':comparisons,
            'selected_bootstrap_rank':selected_boot_rank,
            'segment_ranks':segment_ranks,
            'new_holdout':False,
        })
    stage=str((report.get('settings') or {}).get('research_stage') or '')
    sampled={str(x) for x in (report.get('cutoffs') or [])}
    exposed_for_stage=(EXPOSED_CUTOFFS_THROUGH_S7 if stage=='S8' else DEVELOPMENT_CUTOFFS)
    overlap=sorted(sampled & set(exposed_for_stage))
    overall='FORWARD_CANDIDATE_FROZEN_NEEDS_NEW_HOLDOUT'
    confirmation={
        'stage':stage,
        'exact_prior_exposed_cutoff_overlap':overlap,
        'cutoff_overlap_count':len(overlap),
        'is_independent_future_holdout':False,
        'core_horizons':([60] if stage=='S8' else [20,60]),
        'short_horizon_is_required':False,
        's7_verdict':dict(S7_VERDICT),
        'checks':{},
    }
    if stage=='S7':
        by_h={int(x.get('horizon')):x for x in horizons if x.get('horizon') is not None}
        def passes(x):
            if not x:return False
            vals=(x.get('mean_excess'),x.get('bootstrap_90_low'),x.get('leave_one_out_min_mean_excess'),
                  x.get('first_half_mean_excess'),x.get('second_half_mean_excess'))
            return all(v is not None and np.isfinite(float(v)) and float(v)>0 for v in vals)
        for h in (5,20,60):confirmation['checks'][str(h)]=passes(by_h.get(h))
        core_ok=(not overlap and confirmation['checks'].get('20',False)
                 and confirmation['checks'].get('60',False))
        overall=('S7_HISTORICAL_CROSSCHECK_PASS_NOT_FUTURE_HOLDOUT' if core_ok
                 else 'S7_HISTORICAL_CROSSCHECK_NOT_CONFIRMED')
        confirmation['core_crosscheck_pass']=bool(core_ok)
        confirmation['short_horizon_crosscheck_pass']=bool(not overlap and confirmation['checks'].get('5',False))
    elif stage=='S8':
        by_h={int(x.get('horizon')):x for x in horizons if x.get('horizon') is not None}
        x=by_h.get(60) or {}
        required=(x.get('mean_excess'),x.get('bootstrap_90_low'),x.get('leave_one_out_min_mean_excess'),
                  x.get('first_half_mean_excess'),x.get('second_half_mean_excess'),
                  x.get('quarter_cluster_bootstrap_90_low'),x.get('leave_one_year_out_min_mean_excess'),
                  x.get('raw_mean_gain_vs_legacy'),x.get('raw_mean_excess_vs_equal_weight_universe'))
        pass60=bool(not overlap and all(v is not None and np.isfinite(float(v)) and float(v)>0 for v in required))
        confirmation['checks']={'5':False,'20':False,'60':pass60}
        confirmation['rejected_horizons_not_eligible_for_s8_rescue']=[5,20]
        confirmation['s8_role']='FALSIFICATION_AND_CROSS_UNIVERSE_ROBUSTNESS_NOT_REOPTIMIZATION'
        confirmation['core_crosscheck_pass']=pass60
        overall=('S8_60D_CROSS_UNIVERSE_PASS_NOT_FUTURE_HOLDOUT' if pass60
                 else 'S8_60D_CROSS_UNIVERSE_NOT_CONFIRMED')
    return {
        'status':overall,
        'freeze_date':FREEZE_DATE,
        'optimization_source':OPTIMIZATION_SOURCE,
        'development_cutoffs':list(DEVELOPMENT_CUTOFFS),
        'market_policy':'CAUTION_TO_CASH',
        'new_holdout':False,
        'weights_are_probabilities':False,
        'automatic_orders_authorized':False,
        'confirmation_gate':confirmation,
        'horizons':horizons,
    }



def cross_stage_maximin(reports, bootstrap_reps: int=12000):
    """Select one predeclared profile per horizon across exposed stages.

    Primary score = largest worst-stage 5th percentile bootstrap excess vs 0050.
    Tie-breakers = largest worst-stage mean excess, then largest average mean excess.
    This intentionally searches only the small predeclared profile family; it does
    not optimize arbitrary continuous weights on the exposed outcomes.
    """
    audits=[]
    for report in reports:
        if report:
            audits.append(optimized_audit(report,bootstrap_reps=bootstrap_reps))
    out={'criterion':'MAXIMIZE_WORST_STAGE_BOOTSTRAP_5PCT_THEN_WORST_MEAN',
         'new_holdout':False,'automatic_orders_authorized':False,'horizons':[]}
    if not audits:return out
    for h in (5,20,60):
        stage_maps=[]
        for audit in audits:
            block=next((x for x in audit.get('horizons',[]) if int(x.get('horizon',-1))==h),None)
            if not block:continue
            stage_maps.append({x['profile']:x for x in block.get('profile_comparison',[])})
        if not stage_maps:continue
        common=set(stage_maps[0])
        for m in stage_maps[1:]:common &= set(m)
        rows=[]
        for profile in sorted(common):
            vals=[m[profile] for m in stage_maps]
            row={'profile':profile,'stages':len(vals),
                 'worst_stage_bootstrap_90_low':min(float(v['bootstrap_90_low']) for v in vals),
                 'worst_stage_mean_excess':min(float(v['mean_excess']) for v in vals),
                 'average_stage_mean_excess':float(np.mean([v['mean_excess'] for v in vals])),
                 'stage_metrics':[{'mean_excess':float(v['mean_excess']),
                                   'bootstrap_90_low':float(v['bootstrap_90_low']),
                                   'paired_cases':int(v['paired_cases'])} for v in vals]}
            rows.append(row)
        rows.sort(key=lambda x:(x['worst_stage_bootstrap_90_low'],x['worst_stage_mean_excess'],x['average_stage_mean_excess']),reverse=True)
        expected=OPTIMIZED_PROFILE_BY_HORIZON[h]
        out['horizons'].append({'horizon':h,'selected_profile':rows[0]['profile'] if rows else None,
                                'expected_frozen_profile':expected,
                                'selection_matches_frozen':bool(rows and rows[0]['profile']==expected),
                                'ranking':rows})
    return out

def optimized_markdown(report: dict) -> str:
    audit=report.get('v1987_robustness_audit') or report.get('v1986_optimized_audit') or optimized_audit(report)
    hs=audit.get('horizons') or []
    if not hs:return ''
    def pct(x):
        return '--' if x is None or not np.isfinite(float(x)) else f'{float(x)*100:+.2f}%'
    out=['## V19.8.7 frozen candidate robustness audit','',
         f"Freeze date: **{audit.get('freeze_date')}**; source: **{audit.get('optimization_source')}**.",
         'The S4/S6 weights remain frozen. S7 did not confirm 5/20-day alpha; V19.8.7 does not retune on S7. S8 is a falsification/cross-universe diagnostic, not automatic-order authorization.',
         'Market policy: CAUTION -> cash. The gate uses only information available at the cutoff.','',
         '| Horizon | Frozen profile | Weights | Cases | Net | 0050 | Excess | IID boot 90% | Quarter-cluster low | vs legacy | vs broad universe | First / second half | S7 verdict |',
         '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for x in hs:
        weights=', '.join(f'{k}={v:.0%}' for k,v in (x.get('weights') or {}).items())
        out.append(f"| {x.get('horizon')} | {x.get('profile')} | {weights} | {x.get('paired_cases',0)} | {pct(x.get('mean_net'))} | {pct(x.get('benchmark_mean'))} | {pct(x.get('mean_excess'))} | {pct(x.get('bootstrap_90_low'))} to {pct(x.get('bootstrap_90_high'))} | {pct(x.get('quarter_cluster_bootstrap_90_low'))} | {pct(x.get('raw_mean_gain_vs_legacy'))} | {pct(x.get('raw_mean_excess_vs_equal_weight_universe'))} | {pct(x.get('first_half_mean_excess'))} / {pct(x.get('second_half_mean_excess'))} | {x.get('s7_verdict')} |")
    return '\n'.join(out)
