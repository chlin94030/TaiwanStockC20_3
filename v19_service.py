"""Persistent research jobs and display contracts for V19.

The app owns its worker, not the assistant. No orders are placed. Successful
reports survive a failed refresh; mobile reconnects do not resubmit the job.
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import asdict, replace
from datetime import datetime
import hashlib
import os
import threading
import time
import numpy as np
import pandas as pd
from v19_config import Settings, TZ, FACTORS, TECH, prior, VERSION
from v19_data import (download_history, import_legacy_sqlite, read_json, atomic_json,
                      atomic_csv, clean_prices, SourceError)
from v19_features import build_panel, current_candidates
from v19_backtest import analyze, add_outcomes, save_analysis
from v1983_stages import (GATE_SCHEMA, STAGES, AUTO_WAVES, evaluate_stage_gate,
                          stage_index, apply_stage)

_LOCK=threading.RLock()
_JOBS={}
_AUTO_LOCK=threading.RLock()
_AUTO_THREADS={}


def _active_steps(mode, optional_data=False):
    if mode == 'download_only':
        steps=[('universe',.08),('download',.87),('database',.05)]
        if optional_data:steps.insert(2,('optional',.05));steps[1]=('download',.82)
        return steps
    if mode == 'cache_validate':
        return [('prepare',.05),('features',.15),('validate',.65),('latest_fit',.10),('factor_report',.05)]
    steps=[('universe',.06),('download',.44),('database',.04),('features',.10),('validate',.25),('latest_fit',.06),('factor_report',.05)]
    if optional_data:
        steps.insert(2,('optional',.08));steps[1]=('download',.36)
    return steps


def _progress_meta(mode, stage, done, total, optional_data=False):
    steps=_active_steps(mode,optional_data)
    names=[x[0] for x in steps]
    if stage not in names:
        return {'overall_pct':0.0,'stage_pct':0.0,'step_index':0,'steps_total':len(steps)}
    idx=names.index(stage)
    total=max(1,int(total or 1));done=max(0,min(int(done or 0),total))
    ratio=done/total
    before=sum(w for _,w in steps[:idx]);weight=steps[idx][1]
    return {'overall_pct':max(0.0,min(1.0,before+weight*ratio)),
            'stage_pct':ratio,'step_index':idx+1,'steps_total':len(steps)}


def paths(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    return {'root':root,'state':root/'v19_job.json','last':root/'last_success.json','runroot':root/'runs'}


def job_status(root):
    p=paths(root);key=str(p['root'].resolve());obj=read_json(p['state'])
    with _LOCK:alive=bool(_JOBS.get(key) and _JOBS[key].is_alive())
    if obj.get('state')=='RUNNING' and not alive:
        pid=obj.get('pid')
        if pid==os.getpid() or time.time()-float(obj.get('updated_epoch',0))>120:
            obj=dict(obj,state='INTERRUPTED',message='Worker stopped; cached prices retained. Resume the job.')
    return obj


def _safe_run_report(runroot, directory):
    if not directory:
        return {}, None
    try:
        path=Path(directory).resolve()
        if not path.is_relative_to(runroot.resolve()):
            return {}, None
        report_path=path/'v19_results.json'
        if not report_path.is_file():
            return {}, None
        return read_json(report_path), report_path
    except (OSError, RuntimeError, ValueError):
        return {}, None


def _completed_stage_score(report, report_path):
    gate=evaluate_stage_gate(report)
    stage=gate.get('stage')
    if gate.get('execution_status')!='STAGE_COMPLETE' or not stage:
        return None
    try:
        rank=stage_index(stage)
        stamp=report_path.stat().st_mtime if report_path else 0.0
    except (OSError, ValueError):
        return None
    return (rank, stamp), gate


def read_last_report(root):
    """Return the highest completed staged report, repairing an old pointer.

    V19.8.4 only advanced ``last_success.json`` for RESEARCH_COMPLETE.  That
    left a fully executed S2/S3/S4 report stranded whenever one historical
    outcome was missing.  V19.8.7 scans recent run outputs once through this
    normal read path, reevaluates them with the execution gate, and repairs the
    pointer without rerunning downloads or backtests.
    """
    p=paths(root);last=read_json(p['last']);runroot=p['runroot'].resolve()
    best_report={};best_path=None;best_score=None;best_gate=None

    pointer_report,pointer_path=_safe_run_report(runroot,last.get('directory'))
    if pointer_report:
        scored=_completed_stage_score(pointer_report,pointer_path)
        if scored:
            best_score,best_gate=scored;best_report=pointer_report;best_path=pointer_path
            # Normal V19.8.7 rerenders take this fast path: one JSON read only.
            # The multi-run scan below is reserved for upgrading an old pointer.
            if (last.get('execution_status')=='STAGE_COMPLETE'
                    and int(last.get('gate_schema') or 0)>=GATE_SCHEMA):
                return pointer_report

    # Recent reports are enough for one-time migration/recovery.
    try:
        report_paths=sorted(runroot.glob('*/v19_results.json'),
                            key=lambda x:x.stat().st_mtime, reverse=True)[:80]
    except OSError:
        report_paths=[]
    for report_path in report_paths:
        if pointer_path is not None and report_path.resolve()==pointer_path.resolve():
            continue
        report=read_json(report_path)
        scored=_completed_stage_score(report,report_path)
        if not scored:
            continue
        score,gate=scored
        if best_score is None or score>best_score:
            best_score,best_gate=score,gate;best_report=report;best_path=report_path
            # Stop once the highest configured Cloud stage is found.
            if score[0]>=len(STAGES)-1:
                break

    if best_report and best_path is not None:
        current_dir=str(best_path.parent.resolve())
        if str(last.get('directory') or '')!=current_dir or last.get('execution_status')!='STAGE_COMPLETE':
            atomic_json(p['last'],{
                'directory':current_dir,
                'run_id':best_path.parent.name,
                'status':best_report.get('status'),
                'research_status':best_report.get('status'),
                'execution_status':'STAGE_COMPLETE','gate_schema':GATE_SCHEMA,
                'stage':best_gate.get('stage') if best_gate else None,
                'reconciled_by':'V19.8.7_STAGE_GATE',
            })
        return best_report

    # Preserve legacy non-staged behavior if no staged completion exists.
    if pointer_report:
        return pointer_report
    return {}


def read_latest_attempt_report(root):
    """Newest saved research report, whether or not it passed the stage gate."""
    p=paths(root);runroot=p['runroot'].resolve()
    try:
        report_paths=sorted(runroot.glob('*/v19_results.json'),
                            key=lambda x:x.stat().st_mtime, reverse=True)
    except OSError:
        return {}
    return read_json(report_paths[0]) if report_paths else {}


def merge_imported_evidence(root, evidence, cfg):
    if not cfg.optional_data:
        return pd.DataFrame()
    extras=Path(root)/'optional_evidence.csv'
    if extras.exists():
        imported=pd.read_csv(extras)
        if not {'ticker','available_at','source'}.issubset(imported):
            raise SourceError('optional CSV needs ticker, available_at, source')
        evidence=pd.concat([evidence,imported],ignore_index=True).drop_duplicates()
    return evidence


def _recent_price_rows(path, rows_per_ticker, cutoff=None):
    """Read compressed history in bounded chunks for the *interactive UI* only.

    Numerical backtests continue using the full unmodified history through
    load_inputs(..., recent_bars=None). Every chunk is reduced to the latest
    N rows per ticker, avoiding construction of an entire 3-year 600-stock
    DataFrame just to show the current screen.
    """
    if not path.exists():
        return pd.DataFrame()
    recent = pd.DataFrame()
    for chunk in pd.read_csv(path, chunksize=40_000):
        if 'ticker' not in chunk or 'date' not in chunk:
            raise SourceError('PRICE_CACHE_MISSING_TICKER_OR_DATE')
        if cutoff:
            chunk = chunk.loc[chunk['date'].astype(str).le(str(cutoff))]
        if chunk.empty:
            continue
        combined = pd.concat((recent, chunk), ignore_index=True)
        recent = (combined.sort_values(['ticker', 'date'], kind='stable')
                  .groupby('ticker', sort=False, group_keys=False)
                  .tail(rows_per_ticker))
    return recent.sort_values(['ticker','date'], kind='stable').reset_index(drop=True)


def load_inputs(root,cfg=Settings(),recent_bars=None):
    root=Path(root);pricepath=root/'history_prices.csv.gz';evpath=root/'historical_evidence.csv.gz'
    prices=(_recent_price_rows(pricepath, int(recent_bars), cfg.end()) if recent_bars
            else pd.read_csv(pricepath)) if pricepath.exists() else pd.DataFrame()
    if prices.empty:
        for candidate in (root.parent/'daily_prices.sqlite',root/'daily_prices.sqlite'):
            if candidate.exists():
                prices=import_legacy_sqlite(candidate,cfg.start(),cfg.end())
                if not prices.empty:break
    evidence=pd.read_csv(evpath) if cfg.optional_data and evpath.exists() else pd.DataFrame()
    evidence=merge_imported_evidence(root,evidence,cfg)
    manifest=read_json(root/'download_manifest.json')
    if (not prices.empty and str(manifest.get('scope','')).startswith('V202_TWSE_TPEX_OFFICIAL_CURRENT')):
        keep={str(x.get('ticker')) for x in manifest.get('pool',[]) if x.get('ticker')}|{cfg.benchmark}
        if len(keep)<=1:raise SourceError('FINAL_COHORT_MANIFEST_MISSING')
        prices=prices.loc[prices.ticker.isin(keep)].copy()
        if not evidence.empty:evidence=evidence.loc[evidence.ticker.isin(keep)].copy()
        return prices,evidence
    if not prices.empty:
        candidates=sorted(set(prices.ticker.astype(str))-{cfg.benchmark})
        if cfg.universe_mode!='full_current' and len(candidates)>cfg.stocks:
            from v198_universe import balanced_sample, progressive_balanced_sample
            metas=prices.drop_duplicates('ticker').set_index('ticker')
            rows=[{'ticker':x,'sector':str(metas.loc[x,'sector']) if 'sector' in metas else 'UNKNOWN'} for x in candidates]
            sampler=progressive_balanced_sample if cfg.progressive_universe else balanced_sample
            selected=sampler(rows,cfg.stocks,cfg.universe_seed,cfg.universe_mode)
            keep={x['ticker'] for x in selected}|{cfg.benchmark}
            prices=prices[prices.ticker.isin(keep)].copy()
            if not evidence.empty:evidence=evidence[evidence.ticker.isin(keep)].copy()
    return prices,evidence


def material_for_display(root,cfg=Settings(),recent_bars=None):
    prices,evidence=load_inputs(root,cfg,recent_bars=recent_bars)
    if prices.empty:return pd.DataFrame(),{}
    panel=build_panel(prices,evidence,cfg);panel,_=add_outcomes(panel,cfg)
    return panel,read_last_report(root)


def start_job(root,cfg=Settings(),mode='download_validate',resume=True):
    cfg=replace(cfg,as_of=cfg.end())  # Freeze the date before a long-running job.
    if mode not in ('download_validate','cache_validate','download_only'):raise ValueError('invalid job mode')
    p=paths(root);key=str(p['root'].resolve())
    with _LOCK:
        if _JOBS.get(key) and _JOBS[key].is_alive():return {'started':False,'state':'RUNNING'}
        lockpath=p['root']/'v19_job.lock'
        if lockpath.exists():
            lock=read_json(lockpath)
            stale=time.time()-float(lock.get('at',0))>5400
            try:
                pid=int(lock.get('pid',0));pid_alive=False
                if pid>0:os.kill(pid,0);pid_alive=True
            except (OSError,ValueError):pid_alive=False
            if pid_alive and not stale and int(lock.get('pid',0))!=os.getpid():return {'started':False,'state':'ANOTHER_PROCESS'}
            lockpath.unlink(missing_ok=True)
        fd=os.open(lockpath,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        with os.fdopen(fd,'w') as f:
            import json
            json.dump({'pid':os.getpid(),'at':time.time()},f)
        runid=datetime.now(TZ).strftime('%Y%m%d_%H%M%S_%f')+'_'+cfg.digest()
        cancel_file=p['root']/'v19_cancel.json'
        cancel_file.unlink(missing_ok=True)
        def cancelled():return read_json(cancel_file).get('run_id')==runid
        directory=p['runroot']/runid
        init_meta=_progress_meta(mode,'prepare',0,1,cfg.optional_data)
        state={'state':'RUNNING','mode':mode,'run_id':runid,'settings':asdict(cfg),'started_at':datetime.now(TZ).isoformat(),
               'resume_enabled':resume,'started_epoch':time.time(),'pid':os.getpid(),'stage':'prepare','done':0,'total':1,
               'message':'準備任務','updated_epoch':time.time(),**init_meta}
        atomic_json(p['state'],state)
        def progress(stage,done,total,message):
            from v192_checkpoint import RunCancelled
            if cancelled():raise RunCancelled('Paused at a safe checkpoint; downloads and completed cases retained')
            meta=_progress_meta(mode,stage,done,total,cfg.optional_data)
            state.update(stage=stage,done=done,total=total,message=message,updated_epoch=time.time(),**meta)
            atomic_json(p['state'],state)
        def worker():
            try:
                if mode=='cache_validate':
                    progress('prepare',1,1,'讀取既有快取')
                    prices,evidence=load_inputs(root,cfg);manifest=read_json(p['root']/'download_manifest.json')
                else:
                    progress('universe',0,3,'準備股票母池')
                    prices,evidence,manifest=download_history(p['root'],cfg,progress)
                    evidence=merge_imported_evidence(root,evidence,cfg)
                if prices.empty:raise SourceError('No price data obtained. See download_manifest.json; no fabricated results were generated.')
                if mode=='cache_validate' and cfg.factor_design=='balanced_v198' and len(set(prices.ticker)-{cfg.benchmark})<cfg.stocks*cfg.min_download_coverage and cfg.universe_mode!='full_current':
                    raise SourceError('CACHE_POOL_BELOW_REQUESTED_TARGET: currently '+str(len(set(prices.ticker)-{cfg.benchmark}))+
                                      ', target '+str(cfg.stocks)+'; use online download to expand the cache')
                if mode=='download_validate' and (manifest.get('download_completeness',1.)<cfg.min_download_coverage or
                    (cfg.factor_design=='balanced_v198' and cfg.universe_mode!='full_current' and
                     'pool_equities' in manifest and manifest.get('requested_target_coverage',0.)<cfg.min_download_coverage)) :
                    raise SourceError('INCOMPLETE_UNIVERSE: '+str(manifest.get('ready_equities'))+'/'+
                                      str(manifest.get('pool_equities'))+' downloaded; resume download and retain caches')
                if mode=='download_only':
                    coverage=float(manifest.get('download_completeness',1.) or 0.)
                    target=float(cfg.min_download_coverage)
                    if coverage < target:
                        state.update(state='NEEDS_MORE_DATA',
                                     message=f"本階段資料完整度 {coverage*100:.1f}% ，低於門檻 {target*100:.0f}%；再次按A可續抓。",
                                     friendly_message='本階段尚有股票未補齊；已成功下載的快取會保留，再按 A 即可續跑。',
                                     updated_epoch=time.time())
                    else:
                        state.update(state='DONE',message=f'本階段歷史資料已下載完成（完整度 {coverage*100:.1f}%）；下一步可執行快取驗證。',overall_pct=1.0,stage_pct=1.0,updated_epoch=time.time())
                else:
                    progress('features',0,1,'Building point-in-time price factors')
                    report,panel,trades=analyze(prices,evidence,cfg,progress,manifest,checkpoint_dir=p['root']/'checkpoints' if resume else None,cancel_check=cancelled)
                    # analyze() already embeds the V19.8.7 gate, but reevaluate here
                    # to support generic/legacy callers and to keep the service layer
                    # authoritative for stage navigation.
                    gate=evaluate_stage_gate(report)
                    report['execution_status']=gate.get('execution_status')
                    report['research_status']=report.get('status')
                    report['stage_gate']=gate
                    save_analysis(directory,report,panel,trades,prices,evidence)
                    atomic_json(directory/'stage_gate.json',gate)

                    staged=bool(gate.get('stage'))
                    execution_done=gate.get('execution_status')=='STAGE_COMPLETE'
                    # Non-staged CLI-compatible work keeps the old complete-only rule.
                    stage_done=execution_done if staged else report.get('status')=='RESEARCH_COMPLETE'
                    if stage_done and report.get('cutoffs'):
                        atomic_json(p['last'],{
                            'directory':str(directory.resolve()),'run_id':runid,
                            'status':report.get('status'),'research_status':report.get('status'),
                            'execution_status':'STAGE_COMPLETE' if staged else 'RESEARCH_COMPLETE',
                            'gate_schema':GATE_SCHEMA if staged else None,
                            'stage':gate.get('stage')})
                    done_state='DONE' if stage_done else 'NEEDS_MORE_DATA'
                    if staged and stage_done:
                        complete=gate.get('complete_adaptive_cases',0);expected=gate.get('expected_cases',0)
                        message=(f"{gate.get('stage')} STAGE_COMPLETE｜研究 {report.get('status')}｜"
                                 f"結果完整 {complete}/{expected}")
                        friendly=('本階段執行已完成，可進入下一階段。' if report.get('status')=='RESEARCH_COMPLETE'
                                  else '本階段執行已完成，可進入下一階段；部分歷史結果仍不完整，已保留為研究品質警示，不會冒充完整資料。')
                    elif staged:
                        message='STAGE_INCOMPLETE｜'+','.join(gate.get('blocking_reasons') or ['UNKNOWN'])
                        friendly='本階段尚未通過執行檢核；畫面會列出缺少的日期、運算或資料完整度。已完成快取不會清除。'
                    else:
                        message=report.get('reason') or report.get('status','NOT_RUN')
                        friendly='' if done_state=='DONE' else '本次研究尚未完整完成；既有成功結果仍保留。'
                    state.update(state=done_state,message=message,report_directory=str(directory.resolve()),
                                 execution_status=gate.get('execution_status'),research_status=report.get('status'),stage_gate=gate,
                                 friendly_message=friendly,
                                 overall_pct=1.0 if done_state=='DONE' else state.get('overall_pct',0.0),updated_epoch=time.time())
            except Exception as e:
                from v192_checkpoint import RunCancelled
                message=type(e).__name__+': '+str(e)
                friendly=''
                low=message.lower()
                if 'broad_universe_catalog_unavailable' in low:
                    friendly='股票母池取得失敗；已嘗試 FinMind 與證交所／櫃買中心官方公開名冊。'
                elif 'cache_pool_below_requested_target' in low:
                    friendly='快取股票數不足，請先完成 A｜下載／補齊本階段資料。'
                elif 'incomplete_universe' in low:
                    friendly='本階段尚有股票未下載完成；可再次執行 A 續跑。'
                state.update(state='PAUSED' if isinstance(e,RunCancelled) else 'FAILED',
                             message=message,friendly_message=friendly,failed_stage=state.get('stage'),updated_epoch=time.time())
            finally:
                atomic_json(p['state'],state)
                lockpath.unlink(missing_ok=True)
        t=threading.Thread(target=worker,daemon=True,name='AlphaRadarV19Research')
        _JOBS[key]=t;t.start()
    return {'started':True,'state':'RUNNING','run_id':runid}


def weights_for(report,horizon,asof):
    block=(report.get('weights') or {}).get(str(horizon)) or {}
    fit=block.get('fit') or {}
    if block.get('weights') and str(fit.get('cutoff','9999'))>str(pd.Timestamp(asof).date()):
        return prior(horizon,TECH),'STARTING_PRIOR_NO_FIT'
    if report and report.get('version')!=VERSION:
        return prior(horizon,TECH),'OLD_REPORT_NOT_APPLIED'
    if block.get('weights') and str(fit.get('cutoff','9999'))<=str(pd.Timestamp(asof).date()):
        return block['weights'],fit.get('status','RESEARCH_FIT')
    return prior(horizon,TECH),'STARTING_PRIOR_NO_FIT'


def analog_summary(panel,row,horizon,weights):
    """Past mature, spaced analogous dates. Historical frequencies, not forecasts."""
    asof=pd.Timestamp(row['date']);col=f'net_{horizon}'
    if col not in panel:return {'state':'NO_OUTCOMES','count':0}
    subset=panel[(panel.date<asof)&(panel[f'exit_date_{horizon}']<asof)&panel.eligible&panel[col].notna()].copy()
    keys=[k for k in weights if k in FACTORS and weights[k]>0]
    missing=[k for k in keys if not np.isfinite(pd.to_numeric(row.get(k),errors='coerce'))]
    if missing:return {'state':'MISSING_SELECTED_INPUTS','count':0,'missing':missing}
    if not keys or subset.empty:return {'state':'INSUFFICIENT','count':0}
    values=subset[keys].to_numpy(dtype=float);query=np.array([row[k] for k in keys]);w=np.array([weights[k] for k in keys])
    w=w/w.sum();mask=np.isfinite(values);coverage=mask@w
    distance=np.nansum((values-query)**2*w,axis=1)/np.maximum(coverage,.01)
    distance[coverage<1.-1e-9]=np.inf
    subset['_distance']=distance
    subset=subset[np.isfinite(subset._distance)].sort_values('_distance').drop_duplicates('date')
    cal=pd.DatetimeIndex(panel.date.unique()).sort_values();chosen=[];locs=[]
    for _,item in subset.iterrows():
        loc=cal.get_loc(item.date)
        if all(abs(loc-q)>=horizon for q in locs):chosen.append(item);locs.append(loc)
        if len(chosen)>=40:break
    minimum=8 if horizon>=60 else 15
    if len(chosen)<minimum:return {'state':'INSUFFICIENT_SPACED_SAMPLES','count':len(chosen),'minimum':minimum}
    samples=pd.DataFrame(chosen);net=samples[col].to_numpy(dtype=float)
    return {'state':'HISTORICAL_ANALOG_NOT_CALIBRATED_FORECAST','count':len(samples),
            'mean_net':float(net.mean()),'median_net':float(np.median(net)),'positive_fraction':float((net>0).mean()),
            'q25_net':float(np.quantile(net,.25)),'worst_mae':float(samples[f'mae_{horizon}'].min()),
            'first':str(samples.date.min().date()),'last':str(samples.date.max().date()),'horizon':horizon}


def field_health(panel,report=None):
    if panel is None or panel.empty:return [{'field':'price history','present':0,'total':0,'state':'MISSING'}]
    current=panel[panel.date==panel.date.max()];out=[]
    for col in ('ticker','name','date','close','source','rsi','k','d','macd_hist','bias20','neckline')+FACTORS:
        if col not in current:
            present=0
        elif col in FACTORS or col in ('close','rsi','k','d','macd_hist','bias20','neckline'):
            present=int(np.isfinite(pd.to_numeric(current[col],errors='coerce')).sum())
        else:
            present=int((current[col].notna() & current[col].astype(str).str.strip().ne('')).sum())
        out.append({'field':col,'present':present,'total':len(current),'coverage':present/len(current),
                    'state':'AVAILABLE' if present==len(current) else 'PARTIAL' if present else 'MISSING_NOT_ZERO'})
    kind=(report or {}).get('data_kind','NOT_RUN')
    out.append({'field':'real_market_validation','present':int(bool(report and report.get('cutoffs') and kind=='PROVIDER_HISTORY')),'total':1,
                'state':kind if kind in ('SYNTHETIC_TEST_ONLY','IMPORTED_UNVERIFIED') else (report or {}).get('status','NOT_RUN')})
    return out


def position_size(capital,entry,stop,risk_fraction=.005,max_weight=.2,cost_buffer=.007):
    if not all(np.isfinite(x) for x in (capital,entry,stop,risk_fraction,max_weight,cost_buffer)):
        return {'shares':0,'state':'INVALID_INPUT'}
    if capital<=0 or not 0<stop<entry or not 0<risk_fraction<=.05 or not 0<max_weight<=1:
        return {'shares':0,'state':'INVALID_INPUT'}
    per_share=entry-stop+entry*cost_buffer
    shares=int(min(capital*risk_fraction/per_share,capital*max_weight/(entry*(1+cost_buffer))))
    return {'shares':shares,'position_value':shares*entry,'planned_max_loss':shares*per_share,
            'risk_budget':capital*risk_fraction,'state':'ILLUSTRATION_GAP_RISK_NOT_CAPPED'}


def request_cancel(root):
    """Ask the app's own worker to stop at the next safe checkpoint."""
    p=paths(root);state=job_status(root)
    if state.get('state')!='RUNNING':return False
    atomic_json(p['root']/'v19_cancel.json',{'run_id':state.get('run_id')})
    return True



def _auto_path(root):
    return paths(root)['root']/'v20_final_campaign.json'


def _settings_from_dict(raw):
    raw=dict(raw or {})
    allowed=set(Settings.__dataclass_fields__)
    clean={k:v for k,v in raw.items() if k in allowed}
    for k in ('horizons','replay_cutoffs','excluded_cutoffs'):
        if k in clean and clean[k] is not None:
            clean[k]=tuple(clean[k])
    return Settings(**clean)


def auto_campaign_status(root):
    """Persistent one-click V20 validation campaign status."""
    p=_auto_path(root);obj=read_json(p);key=str(paths(root)['root'].resolve())
    if not obj:
        return {}
    with _AUTO_LOCK:
        alive=bool(_AUTO_THREADS.get(key) and _AUTO_THREADS[key].is_alive())
    if obj.get('state')=='RUNNING' and not alive:
        # A Streamlit process restart kills daemon threads, but all job caches
        # and completed wave reports remain. Mark resumable instead of failed.
        obj=dict(obj,state='INTERRUPTED',message='自動驗證執行緒中斷；可由頁面自動續跑。')
        atomic_json(p,obj)
    obj['worker_alive']=alive
    return obj


def _auto_write(root,obj,**updates):
    with _AUTO_LOCK:
        if read_json(_auto_path(root)).get('stop_requested'):
            obj['stop_requested']=True
        obj.update(updates,updated_epoch=time.time())
        atomic_json(_auto_path(root),obj)


def _auto_report_from_job(root,job):
    directory=job.get('report_directory')
    if not directory:
        return {}
    try:
        report_path=Path(directory).resolve()/'v19_results.json'
        runroot=paths(root)['runroot'].resolve()
        if not report_path.is_relative_to(runroot) or not report_path.is_file():
            return {}
        return read_json(report_path)
    except (OSError,RuntimeError,ValueError):
        return {}


def _all_exposed_cutoffs(root, max_reports=None):
    """Collect exact historical cutoffs already exposed by any saved run.

    V20.1 A1-A3 only carried the immediately previous campaign exclusions, so
    a new campaign could accidentally reuse S6/S7/S8 development dates.  V20.3-final
    scans saved reports and excludes every exact cutoff it can prove was already
    seen.  Missing/corrupt reports are skipped; no date is invented.
    """
    runroot=paths(root)['runroot'].resolve(); seen=[]
    try:
        report_paths=sorted(runroot.glob('*/v19_results.json'),
                            key=lambda x:x.stat().st_mtime,reverse=True)
        if max_reports is not None:
            report_paths=report_paths[:max(0,int(max_reports))]
    except OSError:
        report_paths=[]
    for rp in report_paths:
        try: report=read_json(rp)
        except (OSError,ValueError): continue
        settings=report.get('settings') or {}
        for value in list(settings.get('excluded_cutoffs') or [])+list(report.get('cutoffs') or []):
            value=str(value or '').strip()
            if value and value not in seen: seen.append(value)
    return seen


def start_auto_campaign(root,cfg=Settings(),resume=True):
    """Start or resume the V20.3-final clean-universe automatic validation campaign.

    One user click launches two bounded 150x48 Cloud-safe waves. Each wave uses
    the official-current roster, proportional sampling, new stock/date seeds,
    and excludes already-exposed exact cutoffs.  The 60d core is fixed; 5/20d
    are gates rather than standalone alpha engines. No same-wave retuning.
    """
    root=Path(root);key=str(root.resolve());p=_auto_path(root)
    with _AUTO_LOCK:
        if _AUTO_THREADS.get(key) and _AUTO_THREADS[key].is_alive():
            return {'started':False,'state':'RUNNING'}
        existing=read_json(p)
        from v20_final import PROTOCOL_VERSION, protocol_hash, protocol_manifest, PROTOCOL
        if existing.get('version')==PROTOCOL_VERSION and existing.get('state')=='DONE':
            return {'started':False,'state':'FINAL_ALREADY_FINISHED'}
        if job_status(root).get('state')=='RUNNING':
            return {'started':False,'state':'ANOTHER_JOB_RUNNING'}
        if (resume and str(existing.get('version'))=='20.3-final' and
                existing.get('state') in ('RUNNING','INTERRUPTED','PAUSED','FAILED') and existing.get('base_settings')):
            state=dict(existing)
            base=_settings_from_dict(state['base_settings'])
        else:
            base=replace(cfg,years=3,as_of=cfg.end(),prefer_adjusted=True,optional_data=False,financial_history=False,
                         factor_design='balanced_v198',refresh_history=False,universe_mode='proportional',
                         top_k=PROTOCOL['top_k'],horizons=tuple(PROTOCOL['horizons']))
            (root/'final_roster_snapshot.json').unlink(missing_ok=True)
            prior=read_last_report(root) or {}
            # Exclude *all* saved exposed cutoffs, not just the latest A-wave
            # chain.  This prevents C1/C2 from recycling S4-S8 dates that were
            # already used to design the model.
            prior_cutoffs=_all_exposed_cutoffs(root)
            if not prior_cutoffs:
                prior_settings=prior.get('settings') or {}
                prior_cutoffs=list(prior_settings.get('excluded_cutoffs') or [])+list(prior.get('cutoffs') or [])
                prior_cutoffs=list(dict.fromkeys(str(x) for x in prior_cutoffs if str(x)))
            state={
                'schema':2,'version':'20.3-final','state':'RUNNING','started_epoch':time.time(),
                'updated_epoch':time.time(),'wave_index':0,'current_wave':None,
                'phase':'PREPARE','message':'準備V20.3-final清理母池＋Core-first自動驗證',
                'base_settings':asdict(base),'used_cutoffs':prior_cutoffs, 'waves':[],
                'wave_plan':[{'key':w['key'],'stocks':w['stocks'],'dates':w['dates'],
                              'seed':w.get('seed'),'universe_seed':w.get('universe_seed')}
                             for w in AUTO_WAVES],
                'automatic_weight_adoption':False,'automatic_orders_authorized':False,
                'final_manifest':protocol_manifest(base),
            }
        if (state.get('final_manifest') or {}).get('protocol_hash')!=protocol_hash():
            return {'started':False,'state':'PROTOCOL_CHANGED_DO_NOT_RESUME'}
        from v192_checkpoint import code_digest
        if (state.get('final_manifest') or {}).get('code_hash')!=code_digest():
            return {'started':False,'state':'CODE_CHANGED_DO_NOT_RESUME'}
        state['state']='RUNNING';state['stop_requested']=False
        atomic_json(p,state)

        def worker():
            reports=[]
            # Recover already-completed wave reports from state if present.
            for w in state.get('waves') or []:
                rp=w.get('report_path')
                if rp:
                    try:
                        r=read_json(Path(rp))
                        if r:
                            r['final_artifact_directory']=str(Path(rp).resolve().parent)
                            reports.append(r)
                    except (OSError,ValueError):
                        pass
            try:
                completed_keys={str(x.get('key')) for x in (state.get('waves') or [])
                                if x.get('execution_status')=='STAGE_COMPLETE'}
                pending=[i for i,w in enumerate(AUTO_WAVES) if w['key'] not in completed_keys]
                start_idx=(pending[0] if pending else len(AUTO_WAVES))
                state['wave_index']=start_idx
                for idx in range(start_idx,len(AUTO_WAVES)):
                    if AUTO_WAVES[idx]['key'] in completed_keys:
                        continue
                    if read_json(p).get('stop_requested'):
                        _auto_write(root,state,state='PAUSED',phase='PAUSED',message='已暫停自動驗證；快取與已完成波次均保留。')
                        return
                    wave=AUTO_WAVES[idx]
                    used=tuple(dict.fromkeys(state.get('used_cutoffs') or []))
                    wave_cfg=apply_stage(base,wave['key'],optional_data=False,financial_history=False)
                    wave_cfg=replace(wave_cfg,excluded_cutoffs=used,refresh_history=False)
                    _auto_write(root,state,wave_index=idx,current_wave=wave['key'],phase='RUN',
                                message=f"{wave['label']}：自動下載＋驗證")

                    success=False;last_job={}
                    for attempt in range(1,4):
                        if read_json(p).get('stop_requested'):
                            request_cancel(root)
                            _auto_write(root,state,state='PAUSED',phase='PAUSED',message='已要求暫停；安全checkpoint會保留。')
                            return
                        launched=start_job(root,wave_cfg,'download_validate',resume=True)
                        if not launched.get('started'):
                            raise SourceError('FINAL_JOB_NOT_LAUNCHED: '+str(launched.get('state')))
                        # Only this exact run belongs to the campaign.
                        # otherwise the newly launched wave is polled below.
                        while True:
                            js=job_status(root);last_job=js
                            if js.get('run_id')!=launched.get('run_id'):
                                raise SourceError('FINAL_JOB_ID_MISMATCH')
                            _auto_write(root,state,phase='RUN',current_wave=wave['key'],
                                        current_attempt=attempt,
                                        job_state=js.get('state'),job_stage=js.get('stage'),
                                        job_overall_pct=js.get('overall_pct',0),
                                        message=f"{wave['label']}｜{js.get('message','執行中')}")
                            if js.get('state')!='RUNNING':
                                break
                            if read_json(p).get('stop_requested'):
                                request_cancel(root)
                            time.sleep(1.0)
                        if (last_job.get('state')=='DONE' and
                                (last_job.get('stage_gate') or {}).get('execution_status')=='STAGE_COMPLETE'):
                            success=True;break
                        msg=str(last_job.get('message','')).lower()
                        retryable=(last_job.get('state') in ('INTERRUPTED','NEEDS_MORE_DATA') or
                                   'incomplete_universe' in msg or 'cache_pool_below_requested_target' in msg)
                        if not retryable or attempt>=3:
                            break
                        time.sleep(1.5)
                    if not success:
                        _auto_write(root,state,state='FAILED',phase='FAILED',
                                    message=f"{wave['label']}未完成；已保留快取。原因：{last_job.get('message','UNKNOWN')}")
                        return

                    report=_auto_report_from_job(root,last_job)
                    if not report:
                        _auto_write(root,state,state='FAILED',phase='FAILED',message=f"{wave['label']}完成但找不到報告檔。")
                        return
                    if (report.get('settings') or {}).get('research_stage')!=wave['key'] or report.get('version')!=PROTOCOL_VERSION:
                        raise SourceError('FINAL_WAVE_REPORT_MISMATCH')
                    if report.get('final_protocol_hash')!=protocol_hash():
                        raise SourceError('FINAL_PROTOCOL_REPORT_MISMATCH')
                    cutoffs=[str(x) for x in (report.get('cutoffs') or [])]
                    state['used_cutoffs']=list(dict.fromkeys((state.get('used_cutoffs') or [])+cutoffs))
                    gate=report.get('stage_gate') or evaluate_stage_gate(report)
                    audit=report.get('v20_audit') or {}
                    audit202=report.get('v202_audit') or {}
                    report_path=str((Path(last_job['report_directory'])/'v19_results.json').resolve())
                    wave_record={
                        'key':wave['key'],'label':wave['label'],'stocks':wave['stocks'],'dates':wave['dates'],
                        'seed':wave.get('seed'),'universe_seed':wave.get('universe_seed'),
                        'execution_status':gate.get('execution_status'),'research_status':gate.get('research_status'),
                        'download_coverage':gate.get('download_coverage'),'cutoffs':cutoffs,
                        'v20_audit':audit,'v202_audit':audit202,'report_path':report_path,
                    }
                    state['waves']=[x for x in (state.get('waves') or []) if x.get('key')!=wave['key']]
                    state['waves'].append(wave_record)
                    completed_keys.add(wave['key'])
                    report['final_artifact_directory']=str(Path(last_job['report_directory']).resolve())
                    reports.append(report)
                    _auto_write(root,state,wave_index=idx+1,phase='ADVANCE',
                                message=f"{wave['label']}完成；自動進入下一波。")

                from v20_model import summarize_v202_campaign
                summary=summarize_v202_campaign(reports)
                from v20_final import write_final_bundle
                bundle_path=write_final_bundle(root,reports,summary,state['final_manifest'])
                _auto_write(root,state,state='DONE',phase='DONE',current_wave=None,
                            job_overall_pct=1.0,summary=summary,final_bundle=bundle_path,
                            message='V20.3-final自動清理＋核心驗證完成：2波均已執行，不需再手動按下一階段。')
            except Exception as e:
                _auto_write(root,state,state='FAILED',phase='FAILED',
                            message=type(e).__name__+': '+str(e))

        t=threading.Thread(target=worker,daemon=True,name='AlphaRadarV20AutoCampaign')
        _AUTO_THREADS[key]=t;t.start()
    return {'started':True,'state':'RUNNING'}


def ensure_auto_campaign(root):
    """Resume a persisted active campaign after a Streamlit process restart."""
    status=auto_campaign_status(root)
    if status.get('state')=='INTERRUPTED' and status.get('base_settings'):
        try:
            return start_auto_campaign(root,_settings_from_dict(status['base_settings']),resume=True)
        except Exception:
            return {'started':False,'state':'FAILED_TO_RESUME'}
    return {'started':False,'state':status.get('state')}


def pause_auto_campaign(root):
    with _AUTO_LOCK:
        state=read_json(_auto_path(root))
        if not state:return False
        state['stop_requested']=True
        atomic_json(_auto_path(root),state)
        request_cancel(root)
        return True
