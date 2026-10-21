"""Alpha Radar V19.8.7 staged offline validation/convergence runner.

Purpose: expand the same deterministic nested stock pool in small steps and run
one Python process per step so peak memory is released between steps.  This tool
never changes live weights automatically.  It only reports whether latest
research-factor weights appear stable across adjacent larger cohorts.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import resource
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

from v19_config import Settings
from v198_universe import progressive_balanced_sample


def parse_steps(text: str):
    out=[]
    for raw in str(text).split(','):
        raw=raw.strip().lower()
        if not raw:
            continue
        if 'x' not in raw:
            raise ValueError(f'Bad step {raw!r}; expected STOCKSxDATES, e.g. 40x4')
        a,b=raw.split('x',1)
        stocks,dates=int(a),int(b)
        if stocks < 5 or not 2 <= dates <= 100:
            raise ValueError(f'Bad step {raw!r}')
        out.append((stocks,dates))
    if not out:
        raise ValueError('No stages supplied')
    if any(out[i][0] >= out[i+1][0] or out[i][1] > out[i+1][1] for i in range(len(out)-1)):
        raise ValueError('Stages must increase in stocks and not decrease in dates')
    return out


def _read_inputs(bundle: str='', prices_csv: str=''):
    if bundle:
        from v191_reporting import read_bundle
        return read_bundle(bundle)
    if prices_csv:
        p=Path(prices_csv)
        prices=pd.read_csv(p)
        return prices,pd.DataFrame(),{'source':'prices_csv','path':str(p)}
    raise ValueError('Provide --replay-bundle or --prices-csv')


def _catalog(prices: pd.DataFrame, benchmark: str):
    p=prices.copy()
    p['ticker']=p['ticker'].astype(str)
    p=p[p.ticker!=benchmark]
    cols=[c for c in ('ticker','name','sector') if c in p.columns]
    cat=p[cols].drop_duplicates('ticker').copy()
    if 'name' not in cat: cat['name']=cat['ticker']
    if 'sector' not in cat: cat['sector']='UNKNOWN'
    return cat[['ticker','name','sector']].to_dict('records')


def _subset(prices, evidence, stocks: int, seed: int, mode: str, benchmark: str):
    cat=_catalog(prices,benchmark)
    n=min(stocks,len(cat))
    selected=progressive_balanced_sample(cat,n,seed,mode)
    tickers={x['ticker'] for x in selected}|{benchmark}
    p=prices[prices.ticker.astype(str).isin(tickers)].copy()
    if evidence is None or evidence.empty or 'ticker' not in evidence.columns:
        e=pd.DataFrame() if evidence is None else evidence.copy()
    else:
        e=evidence[evidence.ticker.astype(str).isin(tickers)].copy()
    return p,e,n,len(cat)


def _clean_weights(report):
    result={}
    for h,obj in (report.get('weights') or {}).items():
        w={str(k):float(v) for k,v in (obj.get('weights') or {}).items()
           if v is not None and math.isfinite(float(v)) and abs(float(v))>1e-12}
        result[str(h)]={'weights':w,'fit_status':str((obj.get('fit') or {}).get('status',''))}
    return result


def _summary_rows(report):
    return {str(x.get('horizon')):{
        'paired_model_cases':int(x.get('paired_model_cases') or 0),
        'matched_benchmark_cases':int(x.get('matched_benchmark_cases') or 0),
        'adaptive_mean':x.get('adaptive_mean'),
        'mean_excess':x.get('mean_excess')
    } for x in (report.get('summary') or [])}


def _worker(args):
    from v19_backtest import analyze
    prices,evidence,manifest=_read_inputs(args.replay_bundle,args.prices_csv)
    base=Settings(
        stocks=max(5,args.stocks), dates=args.dates, horizons=tuple(int(x) for x in args.horizons.split(',')),
        seed=args.seed, universe_seed=args.universe_seed, universe_mode=args.universe_mode,
        factor_design='balanced_v198', factor_audit=args.factor_audit,
        sparse_budget=args.search_budget, optional_data=False, financial_history=False,
        progressive_universe=True, export_full_artifacts=False, export_history_database=False,
        research_stage='', as_of=args.as_of or '',
    )
    cfg=replace(base,as_of=base.end())
    prices,evidence,actual,available=_subset(prices,evidence,args.stocks,args.universe_seed,args.universe_mode,cfg.benchmark)
    cfg=replace(cfg,stocks=actual)
    t0=time.perf_counter()
    def progress(stage,i,total,msg):
        if args.verbose and (i==0 or i==total):
            print(f'[{stage}] {i}/{total} {msg}',flush=True)
    report,panel,trades=analyze(prices,evidence,cfg,progress,manifest,checkpoint_dir=None)
    elapsed=time.perf_counter()-t0
    rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux ru_maxrss is KiB. macOS reports bytes; runner is intended primarily for Linux/Cloud-compatible hosts.
    rss_mib=float(rss_kib)/1024.0 if sys.platform!='darwin' else float(rss_kib)/(1024.0*1024.0)
    payload={
        'requested_stocks':args.stocks,'actual_equities':actual,'available_equities':available,
        'symbols':int(panel.ticker.nunique()),'dates_requested':args.dates,
        'cutoffs':len(report.get('cutoffs') or []),'expected_cases':report.get('expected_adaptive_cases'),
        'complete_cases':report.get('complete_adaptive_cases'),'status':report.get('status'),
        'elapsed_seconds':round(elapsed,3),'peak_rss_mib':round(rss_mib,1),
        'weights':_clean_weights(report),'performance':_summary_rows(report),
        'data_start':report.get('data_start'),'data_end':report.get('data_end'),
        'factor_design':cfg.factor_design,'automatic_weight_adoption':False,
    }
    out=Path(args.worker_output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print('STAGE_DONE '+str(out),flush=True)
    return 0


def _transition(prev,cur,l1_limit: float,jaccard_floor: float):
    rows=[]
    stable=True
    horizons=sorted(set(prev.get('weights',{}))&set(cur.get('weights',{})),key=lambda x:int(x))
    if not horizons:
        return {'stable':False,'reason':'NO_COMMON_HORIZON','horizons':[]}
    for h in horizons:
        a=prev['weights'][h]['weights']; b=cur['weights'][h]['weights']
        ka=set(a);kb=set(b);union=ka|kb
        jac=len(ka&kb)/len(union) if union else 1.0
        l1=sum(abs(float(a.get(k,0))-float(b.get(k,0))) for k in union)
        ok=jac>=jaccard_floor and l1<=l1_limit
        stable=stable and ok
        rows.append({'horizon':int(h),'support_jaccard':round(jac,4),'weight_l1':round(l1,4),'stable':ok})
    return {'stable':stable,'horizons':rows,'criteria':{'support_jaccard_min':jaccard_floor,'weight_l1_max':l1_limit}}


def _parent(args):
    steps=parse_steps(args.steps)
    outdir=Path(args.output);outdir.mkdir(parents=True,exist_ok=True)
    summaries=[];transitions=[];stable_streak=0
    for idx,(stocks,dates) in enumerate(steps,1):
        worker_out=outdir/f'stage_{idx:02d}_{stocks}x{dates}.json'
        cmd=[sys.executable,str(Path(__file__).resolve()),'--worker',
             '--stocks',str(stocks),'--dates',str(dates),'--horizons',args.horizons,
             '--seed',str(args.seed),'--universe-seed',str(args.universe_seed),
             '--universe-mode',args.universe_mode,'--search-budget',str(args.search_budget),
             '--worker-output',str(worker_out)]
        if args.replay_bundle: cmd += ['--replay-bundle',str(Path(args.replay_bundle).resolve())]
        if args.prices_csv: cmd += ['--prices-csv',str(Path(args.prices_csv).resolve())]
        if args.as_of: cmd += ['--as-of',args.as_of]
        if args.factor_audit: cmd += ['--factor-audit']
        if args.verbose: cmd += ['--verbose']
        env=os.environ.copy()
        for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
            env[key]='1'
        print(f'\n=== Stage {idx}/{len(steps)}: {stocks} stocks x {dates} dates ===',flush=True)
        reuse=False
        if worker_out.is_file():
            try:
                cached=json.loads(worker_out.read_text(encoding='utf-8'))
                reuse=(int(cached.get('requested_stocks',-1))==stocks and int(cached.get('dates_requested',-1))==dates)
            except Exception:
                reuse=False
        if reuse:
            print('Reusing completed stage checkpoint: '+str(worker_out),flush=True)
            rc=0
        else:
            try:
                rc=subprocess.run(cmd,env=env,timeout=None if args.stage_timeout<=0 else args.stage_timeout).returncode
            except subprocess.TimeoutExpired:
                rc=124
                print(f'Stage exceeded {args.stage_timeout}s timeout; previous stage outputs remain reusable.',flush=True)
        if rc!=0 or not worker_out.is_file():
            final={'release':'19.8.7','status':'STAGE_FAILED','failed_stage':idx,
                   'failed_spec':{'stocks':stocks,'dates':dates},'completed':summaries,'transitions':transitions}
            (outdir/'staged_convergence.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
            return rc or 2
        cur=json.loads(worker_out.read_text(encoding='utf-8'));summaries.append(cur)
        if len(summaries)>=2:
            tr=_transition(summaries[-2],summaries[-1],args.l1_limit,args.jaccard_floor)
            tr['from_stocks']=summaries[-2]['actual_equities'];tr['to_stocks']=cur['actual_equities']
            transitions.append(tr)
            stable_streak=stable_streak+1 if tr['stable'] else 0
            print('transition stable='+str(tr['stable'])+' | '+json.dumps(tr.get('horizons',[]),ensure_ascii=False),flush=True)
        print(f"done: actual={cur['actual_equities']} cutoffs={cur['cutoffs']} cases={cur['complete_cases']}/{cur['expected_cases']} elapsed={cur['elapsed_seconds']}s peakRSS={cur['peak_rss_mib']}MiB",flush=True)
        if cur['actual_equities'] < stocks:
            print('Available history pool exhausted; stopping before larger stages.',flush=True)
            break
        if args.stop_when_stable and stable_streak>=args.stable_transitions:
            print(f'Weight/support stability reached for {stable_streak} consecutive expansions; stopping by rule.',flush=True)
            break
    converged=stable_streak>=args.stable_transitions
    final={'release':'19.8.7','status':'CONVERGED_BY_DECLARED_RULE' if converged else 'COMPLETED_NO_CONVERGENCE_CLAIM',
           'criteria':{'support_jaccard_min':args.jaccard_floor,'weight_l1_max':args.l1_limit,
                       'consecutive_transitions_required':args.stable_transitions},
           'stages':summaries,'transitions':transitions,'automatic_weight_adoption':False,
           'note':'Stability is a research diagnostic, not profitability proof or permission to auto-change live weights.'}
    (outdir/'staged_convergence.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    md=['# Alpha Radar V19.8.7 staged convergence','',f"Status: **{final['status']}**",'',
        '| Stage | Equities | Cutoffs | Complete cases | Seconds | Peak RSS MiB |','|---|---:|---:|---:|---:|---:|']
    for i,s in enumerate(summaries,1):
        md.append(f"| {i} | {s['actual_equities']} | {s['cutoffs']} | {s['complete_cases']}/{s['expected_cases']} | {s['elapsed_seconds']} | {s['peak_rss_mib']} |")
    md += ['','## Adjacent-stage stability','']
    for i,t in enumerate(transitions,1): md.append(f"- {i}: {t['from_stocks']}→{t['to_stocks']} stocks — stable={t['stable']}; {t['horizons']}")
    md += ['','No weights are automatically promoted by this runner.']
    (outdir/'staged_convergence.md').write_text('\n'.join(md),encoding='utf-8')
    print('\nRESULT '+str((outdir/'staged_convergence.json').resolve()),flush=True)
    return 0


def main(argv=None):
    p=argparse.ArgumentParser(description='Alpha Radar V19.8.7 staged nested-cohort validation')
    p.add_argument('--replay-bundle',default='');p.add_argument('--prices-csv',default='')
    p.add_argument('--steps',default='40x4,60x6,80x8,100x12,120x14,150x18,200x24,300x40,450x65,600x100')
    p.add_argument('--horizons',default='5,20,60');p.add_argument('--seed',type=int,default=1920)
    p.add_argument('--universe-seed',type=int,default=1900)
    p.add_argument('--universe-mode',choices=['balanced','proportional'],default='balanced')
    p.add_argument('--search-budget',type=int,default=64);p.add_argument('--as-of',default='')
    p.add_argument('--output',default='data/v19/staged_v1983')
    p.add_argument('--jaccard-floor',type=float,default=.75);p.add_argument('--l1-limit',type=float,default=.20)
    p.add_argument('--stable-transitions',type=int,default=2)
    p.add_argument('--stop-when-stable',action='store_true')
    p.add_argument('--factor-audit',action='store_true');p.add_argument('--verbose',action='store_true')
    p.add_argument('--stage-timeout',type=int,default=900,help='Per-stage subprocess timeout in seconds; 0 disables')
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--stocks',type=int,default=40,help=argparse.SUPPRESS)
    p.add_argument('--dates',type=int,default=4,help=argparse.SUPPRESS)
    p.add_argument('--worker-output',default='',help=argparse.SUPPRESS)
    a=p.parse_args(argv)
    if not a.replay_bundle and not a.prices_csv: p.error('provide --replay-bundle or --prices-csv')
    if a.worker:
        if not a.worker_output: p.error('--worker-output is required in worker mode')
        return _worker(a)
    return _parent(a)


if __name__=='__main__':
    raise SystemExit(main())
