"""Alpha Radar V20.3-final mobile-first research dashboard. Every empty field has an explicit state."""
from __future__ import annotations
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from pathlib import Path
import html
import json
import os
import time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from v19_config import Settings, FACTORS, TECH, TZ, VERSION
from v1983_stages import (RELEASE, STAGES, AUTO_WAVES, get_stage, apply_stage, stage_from_settings, stage_index,
                          next_stage_key, evaluate_stage_gate)
from v19_data import read_json
from v19_features import current_candidates
from v191_ui import validation_overview, allocation_banner
from v192_ui import factor_section, database_download
from v19_service import (start_job,job_status,material_for_display,read_last_report,read_latest_attempt_report,
                         weights_for,analog_summary,field_health,position_size,request_cancel,
                         start_auto_campaign,auto_campaign_status,ensure_auto_campaign,pause_auto_campaign)

ROOT=Path(__file__).resolve().parent
BASE=Path(os.getenv('ALPHA_RADAR_DATA_DIR',str(ROOT/'data')))
DATA=BASE/'v19'
LABELS={
 'trend':'趨勢／均線','relative_strength':'相對大盤強度','breakout':'平台突破',
 'reversal':'KD／MACD／RSI修復','pattern':'W底／頸線','volume':'價量搭配',
 'revenue':'營收成長','quality':'獲利品質','foreign':'外資持續買超','trust':'投信持續買超',
 'joint':'外投同步買超','dealer':'自營商自行買賣','margin':'融資整理','holders':'大戶持股變化',
 'ticker':'股票代碼','name':'名稱','date':'資料日期','close':'日線收盤','source':'行情來源',
 'rsi':'RSI(14)','k':'KD：K值','d':'KD：D值','macd_hist':'MACD柱體','bias20':'20日乖離％',
 'neckline':'W底頸線','real_market_validation':'隨機日期歷史研究'}
from v193_ui import LABELS as BROADER_LABELS, broader_results
LABELS.update(BROADER_LABELS)
from v194_factors import LABELS as SPARSE_LABELS
from v194_ui import STATES as SPARSE_STATES, choose_model, report_supports, import_evidence_control
LABELS.update(SPARSE_LABELS)
from v196_factors import LABELS as SCORECARD_LABELS
LABELS.update(SCORECARD_LABELS)
from v197_ten_pillars import NAMES as TEN_LABELS
LABELS.update(TEN_LABELS)
LABELS.update({'p202_rel5':'5日相對0050強度','p202_rel20':'20日相對0050強度','p202_rel60':'60日相對0050強度','p202_volume_impulse':'量能脈衝','p202_entry_quality':'非追高進場品質'})
SETUP={'REVERSAL':'低檔修復觀察','BREAKOUT':'突破加速觀察','GROWTH_PULLBACK':'業績＋回檔觀察','WATCH':'趨勢追蹤'}
FIT={'OLD_REPORT_NOT_APPLIED':'舊版報告未套用，請重跑V20驗證',
     'BASELINE_INSUFFICIENT_INDEPENDENT_BLOCKS':'不重疊區塊不足，保留基準',
     'BASELINE_TRAIN_COHORT_INCOMPLETE':'同口徑訓練資料不足',
     'BASELINE_VALIDATION_COHORT_INCOMPLETE':'同日內部驗證資料不足',
     'BASELINE_STABILITY_NOT_PROVEN':'調權穩定性未通過，保留基準',
     'ROBUST_INNER_VALIDATION_ACCEPTED':'通過過去區塊的調權檢查（研究）',
     'STARTING_PRIOR_NO_FIT':'起始權重，尚未訓練','BASELINE_INSUFFICIENT_TRAINING':'訓練樣本不足，沿用基準',
     'BASELINE_TECH_GAP':'技術資料不足，沿用基準','BASELINE_VALIDATION_NOT_BETTER':'內部驗證未明顯勝出，保留基準',
     'RESEARCH_FIT':'已依當時以前資料調整（研究用途）'}
FIT.update(SPARSE_STATES)
CSS="""
<style>
.block-container{max-width:1120px;padding-top:1.1rem;padding-bottom:3rem}
h1{font-size:1.85rem!important;letter-spacing:-.025em}h2{font-size:1.3rem!important}
.v19-note{border-left:4px solid #537cb6;background:#f1f5fb;padding:12px 16px;border-radius:6px;
color:#304663;margin:12px 0;line-height:1.7}
.v19-card{border:1px solid #dbe3ef;border-radius:16px;padding:18px 20px;margin:13px 0;background:#fff;
box-shadow:0 3px 12px rgba(38,60,90,.04);color:#20334c}
.v19-title{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:1.13rem;font-weight:750}
.v19-tag{display:inline-block;background:#ecf3fc;color:#395f90;padding:4px 9px;border-radius:7px;
font-size:.83rem;font-weight:600;margin:9px 6px 5px 0}
.v19-small{font-size:.88rem;color:#647287;line-height:1.65;overflow-wrap:anywhere}
.v19-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}
.v19-metrics span{display:block;font-size:.78rem;color:#647287}.v19-metrics b{font-size:1.22rem}
.v19-up{color:#bc4740}.v19-down{color:#17795c}
.v19-muted{color:#68788c}
[data-testid="stRadio"] [role="radiogroup"]{flex-wrap:wrap;gap:5px}
[data-testid="stDataFrame"]{max-width:100%}
@media(max-width:640px){.block-container{padding-left:1rem;padding-right:1rem}
.v19-card{padding:15px 13px}.v19-title{font-size:1.05rem}.v19-metrics{gap:8px}
.v19-metrics b{font-size:1.07rem}.v19-metrics span{font-size:.75rem}}
</style>
"""

def esc(x):return html.escape(str(x if x is not None else ''),quote=True)

def number(value,digits=2):
    try:
        v=float(value)
        return f'{v:,.{digits}f}' if np.isfinite(v) else '—'
    except (TypeError,ValueError):return '—'

def percent(value,scale=100):
    try:
        v=float(value)*scale
        return f'{v:+.2f}%' if np.isfinite(v) else '—'
    except (TypeError,ValueError):return '—'

def _bootstrap():
    if not os.getenv('FINMIND_TOKEN'):
        try:
            token=st.secrets.get('FINMIND_TOKEN')
            if token:os.environ['FINMIND_TOKEN']=str(token)
        except Exception:pass

@st.cache_data(ttl=600,show_spinner=False)
def _display_data(root,price_mtime,evidence_mtime,legacy_mtime,cfg):
    ui_bars = 340 if cfg.stocks <= 600 else 270
    return material_for_display(root,cfg,recent_bars=ui_bars)

def _mtime(path):
    try:return Path(path).stat().st_mtime
    except OSError:return 0.

@st.fragment(run_every=2)
def progress_box():
    status=job_status(DATA)
    if not status:return
    state=status.get('state')
    stages={'prepare':'準備快取','universe':'取得股票母池','download':'下載歷史日線','optional':'補充營收／籌碼',
            'features':'計算因子','validate':'歷史驗證','database':'儲存階段資料','latest_fit':'計算最近權重','factor_report':'匯整因子報告'}
    stage=stages.get(status.get('stage'),status.get('stage',''))
    overall=max(0.,min(1.,float(status.get('overall_pct',0.) or 0.)))
    total=max(1,int(status.get('total',1) or 1));done=max(0,int(status.get('done',0) or 0))
    step=int(status.get('step_index',0) or 0);steps=int(status.get('steps_total',0) or 0)
    prefix=f'步驟 {step}/{steps}｜' if step and steps else ''
    settings=status.get('settings') or {}
    scope=''
    if settings.get('research_stage'):
        scope=f"{settings.get('research_stage')}｜{settings.get('stocks')}檔 × {settings.get('dates')}日期｜"
    st.progress(overall,text=f"整體 {overall*100:.0f}%｜{scope}{prefix}{stage}")
    st.caption(f"目前：{stage} {done}/{total}｜{status.get('message','')}")
    elapsed=max(0,time.time()-float(status.get('started_epoch',time.time())))
    lag=max(0,time.time()-float(status.get('updated_epoch',time.time())))
    if state=='RUNNING':
        st.caption(f'已執行 {elapsed/60:.1f} 分鐘｜最近更新 {lag:.0f} 秒前。每2秒更新；手機重連不會重開同一任務。')
        if st.button('暫停（保留已完成結果）',key='v192_pause'):
            request_cancel(DATA)
            st.info('已請求暫停；當前連線或計算結束後儲存進度。')
    elif state=='DONE':
        st.success('本次流程完成：'+str(status.get('message','')))
        if status.get('execution_status')=='STAGE_COMPLETE' and status.get('research_status')=='RESEARCH_PARTIAL':
            st.warning('執行階段已完成並可晉級；RESEARCH_PARTIAL 只代表部分歷史結果不完整，缺口會保留在報告中，不會補成0。')
        key='v19_seen_'+str(status.get('run_id',''))
        if not st.session_state.get(key):
            st.session_state[key]=True
            _display_data.clear()
            st.rerun()
    elif state in ('FAILED','INTERRUPTED','PAUSED','NEEDS_MORE_DATA'):
        friendly=status.get('friendly_message') or '本次更新未完成；先前成功結果與已下載快取仍保留。'
        if state=='FAILED':st.error(friendly)
        else:st.warning(friendly)
        st.caption('停止位置：'+stage+'｜'+str(status.get('message','')))
    auto=auto_campaign_status(DATA)
    if auto:
        waves=auto.get('wave_plan') or []
        total=max(1,len(waves))
        idx=min(total,int(auto.get('wave_index') or 0))
        job_pct=float(auto.get('job_overall_pct',0) or 0)
        overall=min(1.0,(idx + (job_pct if auto.get('state')=='RUNNING' else 0.0))/total)
        if auto.get('state')=='DONE':overall=1.0
        st.markdown('#### V20.3-final 自動清理／核心驗證')
        st.progress(overall,text=f"自動驗證 {overall*100:.0f}%｜{auto.get('message','')}")
        st.caption(f"已完成波次 {idx}/{total}｜目前 {auto.get('current_wave') or '—'}｜下載、驗證、下一波皆自動銜接。")
        if auto.get('state')=='RUNNING':
            if st.button('暫停自動驗證（保留快取）',key='v20_auto_pause'):
                pause_auto_campaign(DATA);st.info('已要求在安全checkpoint暫停。')
        elif auto.get('state') in ('FAILED','PAUSED'):
            st.warning(str(auto.get('message','自動驗證已停止；快取仍保留。')))
        elif auto.get('state')=='DONE':
            st.success('V20.3-final兩波自動清理＋核心驗證已完成。')
            summary=auto.get('summary') or {}
            rows=[]
            for x in summary.get('horizons') or []:
                sel=x.get('selection_vs_same_pool') or {};pol=x.get('policy_vs_0050') or {}
                rows.append({'週期':f"{x.get('horizon')}日",'選股案例':sel.get('cases'),
                             '選股vs同池等權':percent(sel.get('mean')),
                             'IID 95%下緣':percent(sel.get('bootstrap_95_low')),
                             '季度群聚95%下緣':percent(sel.get('quarter_cluster_95_low')),
                             '不重疊案例':sel.get('disjoint_cases'),
                             '不重疊平均':percent(sel.get('disjoint_mean')),
                             '跨波判定':x.get('selection_validity'),
                             '\u914d\u7f6e\u9a57\u6536':(x.get('acceptance',{}).get('policy_vs_0050') or {}).get('status'),
                             '配置vs0050':percent(pol.get('mean')),
                             '配置群聚95%下緣':percent(pol.get('quarter_cluster_95_low'))})
            if rows:st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    with st.expander('執行紀錄／技術細節',expanded=False):
        st.json(status)

def candidate_card(row,analog,horizon,weights,index):
    valid=analog.get('state')=='HISTORICAL_ANALOG_NOT_CALIBRATED_FORECAST'
    median=analog.get('median_net') if valid else None
    mean=analog.get('mean_net') if valid else None
    count=analog.get('count',0)
    tone='v19-up' if median is not None and median>0 else 'v19-down' if median is not None else 'v19-muted'
    factors=sorted(((k,float(row.get(k,np.nan))*v) for k,v in weights.items()
                   if v>0 and pd.notna(row.get(k))),key=lambda x:x[1],reverse=True)[:3]
    reasons='／'.join(LABELS.get(k,k) for k,_ in factors) or '因子資料不足'
    risk=number(row.get('stop_distance_pct'))
    missing=[LABELS[k] for k in FACTORS if pd.isna(row.get(k))]
    evidence='可比較的歷史樣本不足' if not valid else f"樣本 {count} 組｜歷史正報酬比例 {percent(analog.get('positive_fraction'))}"
    st.markdown(f"""<div class="v19-card">
      <div class="v19-title"><div>#{index:02d}　{esc(row.get('name'))} <span class="v19-small">{esc(row['ticker'])}</span></div>
        <div>日線 {number(row.get('close'))}</div></div>
      <span class="v19-tag">{esc(SETUP.get(row.get('setup'),'研究觀察'))}</span>
      <span class="v19-tag">研究分 {number(row.get('score'),1)}</span>
      <span class="v19-tag">Core核心 {number(row.get('v202_core'),1)}</span>
      <span class="v19-tag">{esc({'READY_FOR_MANUAL_REVIEW':'可人工覆核','WAIT_PULLBACK_OVERHEAT':'過熱等回檔','WAIT_TIMING':'等待短線時機','WATCH_NEEDS_CONFIRMATION':'等待中線確認','WATCH_CORE_NOT_STRONG':'核心不足','CASH_OR_NO_NEW_POSITION':'風控現金','INSUFFICIENT_V20_PRICE_EVIDENCE':'證據不足'}.get(row.get('v202_entry_state') or row.get('v20_entry_state'),'研究觀察'))}</span>
      <span class="v19-tag">因子覆蓋 {number(float(row.get('factor_coverage',0))*100,0)}%</span>
      <div class="v19-metrics">
        <div><span>{horizon}日歷史平均淨報酬</span><b>{percent(mean)}</b></div>
        <div><span>歷史中位數（非保證）</span><b class="{tone}">{percent(median)}</b></div>
        <div><span>參考停損距離</span><b>{risk}%</b></div>
      </div>
      <div class="v19-small">{esc(reasons)}<br>{esc(evidence)}<br>
      觀察區 {number(row.get('reference_low'))}–{number(row.get('reference_high'))}｜
      防守參考 {number(row.get('stop_reference'))}｜不追價參考 {number(row.get('chase_ceiling'))}<br>
      資料日 {esc(str(row.get('date'))[:10])}｜來源 {esc(row.get('source'))}<br>
      這是日線研究候選，不是即時買進指令；價區以本次日線與ATR估算。</div></div>""",unsafe_allow_html=True)
    with st.expander(f"{row['ticker']}：因子數值與缺資料說明",expanded=False):
        table=[{'因子':LABELS.get(k,k),'分數':number(row.get(k),1),
                '本次權重':f"{weights.get(k,0)*100:.1f}%",
                '狀態':'缺資料，不填0' if pd.isna(row.get(k)) else '可用'} for k in FACTORS]
        st.dataframe(pd.DataFrame(table),hide_index=True,use_container_width=True)

def page_decisions(panel,report,cfg):
    st.subheader('先看機會，再看進場，最後控制投入金額')
    st.markdown('<div class="v19-note">排序、買點與資料可信度分開。研究分高不代表一定漲停；歷史平均與中位數不是未來報酬保證。沒有營收／獲利證據的股票，不會冒稱「業績優良」。</div>',unsafe_allow_html=True)
    if panel.empty:
        st.info('尚未載入行情。按上方「下載近年資料＋執行驗證」即可；已有V18資料庫時會先讀取，無須清除原資料。')
        return
    h=st.radio('持有期（交易日）',list(cfg.horizons),horizontal=True,format_func=lambda x:f'{x}日',key='v19_h')
    asof=panel.date.max();weights,state=weights_for(report,h,asof)
    st.caption(f"日線截至 {str(asof.date())}｜{FIT.get(state,state)}。來源標示與日期分開，不把來源待核一律叫舊日線。")
    allocation_banner(report,h,cfg,asof)
    scoring_cfg=cfg
    if cfg.factor_design in ('sparse_v194','sparse_v195','tournament_v196','ten_angle_v197','balanced_v198'):
        weights,scoring_cfg=choose_model(report,h,cfg,asof,LABELS)
    if cfg.factor_design not in ('sparse_v194','sparse_v195','tournament_v196','ten_angle_v197','balanced_v198'):
        design=st.selectbox('\u6392\u540d\u6a21\u5f0f',['\u6b77\u53f2\u63a1\u7528\u6aa2\u67e5','\u65b0\u56e0\u5b50\u8a66\u9a57\u6392\u540d'],key='v193_design')
        if design=='\u65b0\u56e0\u5b50\u8a66\u9a57\u6392\u540d':
            from v193_factors import expanded_prior, EXTENDED
            today=panel[(panel.date==asof)&panel.eligible]
            keys=[k for k in FACTORS if k in today and today[k].notna().mean()>=.85 and (cfg.optional_data or k in TECH+EXTENDED)]
            if keys:weights=expanded_prior(h,keys)
            st.warning('\u6b64\u7d44\u662f\u65b0\u56e0\u5b50\u8a66\u9a57\u6b0a\u91cd\uff0c\u672a\u5fc5\u901a\u904e\u63a1\u7528\u9580\u6abb\uff1b\u4e0d\u662f\u66f4\u9ad8\u52dd\u7387\u7684\u4fdd\u8b49\u3002')
    pool_counts=panel[panel.date==asof]
    st.caption(f"本日有資料 {pool_counts.ticker.nunique()-int((pool_counts.ticker==cfg.benchmark).any())} 檔個股；通過歷史長度／流動性／價格異常檢查 {int(pool_counts.eligible.sum())} 檔。這是已載入股票池，不冒稱全市場。")
    gate='UNKNOWN'
    if cfg.factor_design in ('ten_angle_v197','balanced_v198'):
        valid=pool_counts.loc[pool_counts.eligible,'p197_market_breadth'].dropna()
        regimes=pool_counts.loc[pool_counts.eligible,'p197_market_gate']
        gate=regimes.mode().iat[0] if not regimes.empty else 'UNKNOWN'
        st.caption('市場背景（與選股分開）：'+str(gate)+'｜已載入股票池站上60日線占比 '+(f'{valid.iloc[0]:.0%}' if len(valid) else '資料不足')+'。市場廣度不是全市場資料；不等於盤中已確認買點。')
    mode=st.selectbox('機會類型',['全部研究候選','業績＋回檔','低檔修復','突破加速'],key='v19_setup')
    codes={'業績＋回檔':'GROWTH_PULLBACK','低檔修復':'REVERSAL','突破加速':'BREAKOUT'}
    rows=current_candidates(panel,scoring_cfg,weights,h,setup=codes.get(mode))
    if cfg.factor_design=='balanced_v198' and scoring_cfg.factor_design=='balanced_v198':
        from v20_model import live_v202_candidates, v20_layer_name, v20_anchor
        weights=v20_anchor(h)
        rows,state202=live_v202_candidates(panel,h,scoring_cfg,limit=20)
        if mode!='全部研究候選' and 'setup' in rows:
            rows=rows[rows.setup.eq(codes.get(mode))]
        st.caption('V20.3-final採 Core-first：60日核心負責排序；20日只做確認 Gate；5日只做進場 Gate，不再讓不穩定的短線因子覆蓋核心排名。')
        if h==60:
            st.caption('Core目前固定為成交金額容量80%＋近一年高點20%（研究代理）；不再依每一批驗證結果追著微調。')
        if state202=='INDEX_LEAD':
            st.warning('V20.3-final判定為 INDEX_LEAD：0050趨勢強、股票池廣度不足，本期研究配置優先以0050作比較／替代，不硬選5檔個股。')
        elif state202=='CASH':
            st.warning('V20.3-final風控為 CAUTION：本期研究配置採現金／不新增部位。')
    if rows.empty:
        st.info('這個類型目前沒有通過條件的候選。可能是條件未成立、風控暫停或基本面證據不足，不等於市場沒有機會。')
    for i,(_,row) in enumerate(rows.head(5).iterrows(),1):
        candidate_card(row,analog_summary(panel,row,h,weights),h,weights,i)
    with st.expander('本次因子權重與使用方式',expanded=False):
        st.dataframe(pd.DataFrame([{'因子':LABELS.get(k,k),'權重％':round(v*100,2)} for k,v in weights.items()]),hide_index=True,use_container_width=True)
        st.write('一、研究分是相對排序，不是上漲機率。二、確認型態、量價與當日資料後才評估進場。三、用預定損失設定部位；停損不保證跳空時能成交。四、每次研究使用相同成本與股票池，與固定權重及0050比較。')
    with st.expander('資金配置試算（不是自動下單）',expanded=False):
        capital=st.number_input('可投入資金（元）',min_value=1000.,value=100000.,step=10000.,key='v19_capital')
        risk=st.slider('每筆規劃損失／資金（％）',.1,2.,.5,.1,key='v19_risk')
        entry=st.number_input('預計買進價',min_value=.01,value=100.,key='v19_entry')
        stop=st.number_input('預定防守價',min_value=.01,value=95.,key='v19_stop')
        sized=position_size(capital,entry,stop,risk/100)
        if sized['shares']:
            st.write(f"參考上限：{sized['shares']:,} 股；部位約 {number(sized['position_value'],0)} 元；含成本緩衝的規劃損失約 {number(sized['planned_max_loss'],0)} 元。")
        else:st.info('請確認防守價低於買進價，且輸入值合理。')
        st.caption('單股上限20％，可含零股；未處理實際最低手續費。跳空、流動性及滑價可能使損失超過規劃。')

def page_validation(panel,report,cfg):
    st.subheader(f'{cfg.dates}個基準日：先封存選股，再看後續表現')
    st.write(f'設定：{cfg.sampling_method}不放回抽樣，日期種子{cfg.seed}。權重僅使用基準日以前已完成的績效；訓練與內部驗證依時間分離。')
    st.caption('持有期為交易日：基準日T計算 → T+1開盤假設進場 → T+5／20／60收盤評價。同步匯出相對T日收盤的價格變動。未成交名額留現金，不以其他成功股票替補。')
    if not report:
        st.info('尚無已完成研究。可按「下載近年資料＋執行驗證」，或用已有快取執行。缺籌碼不會阻止價量因子的驗證。')
        return
    st.write(f"研究狀態：**{report.get('status')}**｜資料 {report.get('data_start')}～{report.get('data_end')}｜股票／基準合計 {report.get('symbols')} 檔")
    st.caption('目前資料池未完整驗證歷史下市成分；仍有存活者偏差。若來源為未還原價格，結果是扣成本的價格報酬，不等同含息總報酬。')
    universe_stats=report.get('universe_diagnostics') or {}
    if universe_stats:
        quality=universe_stats.get('universe_quality') or {}
        st.write('母池覆蓋：實際驗證股票 '+str(universe_stats.get('tested_tickers'))+' 檔｜當日可選 '+str(universe_stats.get('today_eligible'))+' 檔；上市／上櫃 '+str(universe_stats.get('tested_market')))
        if quality:
            st.caption('目前目錄 '+str(quality.get('catalog_size'))+' 檔、選取 '+str(quality.get('selected_size'))+' 檔、完成下載 '+str(quality.get('downloaded_size'))+' 檔（'+format(quality.get('download_coverage',0),'.1%')+'）。這是當前成分股的覆蓋，不是已核實的歷史存活者完整母體。')
            if 'warmup_eligible_symbols' in quality:
                st.caption('其中歷史K線至少'+str(cfg.warmup)+'筆：'+str(quality.get('warmup_eligible_symbols'))+'檔（'+format(quality.get('warmup_eligible_fraction',0),'.1%')+'）；至少252筆：'+str(quality.get('has_252_bar_history_symbols'))+'檔。下載成功不等於有足夠完整的歷史可測。')
            with st.expander('產業／市場覆蓋明細（下載母體稽核）'):
                st.dataframe(pd.DataFrame(quality.get('sector_comparison') or []),use_container_width=True,hide_index=True)
    kind=report.get('data_kind','UNCLASSIFIED')
    st.caption('資料分類：'+kind+'；RESEARCH_COMPLETE只表示本次資料的計算流程完成，不代表最佳策略已獲證實。')
    if kind=='SYNTHETIC_TEST_ONLY':
        st.warning('此為合成測試資料，不能當作真實市場績效。')
    if report.get('v202_audit'):
        st.markdown('### V20.3-final主要驗證結果（先看這裡）')
        st.caption('選股能力用「同一股票池等權」比較；資產配置再與0050比較。下方舊的 Fixed/Adaptive 是V19歷史控制組，不再代表V20.3-final主模型。')
        rr=[]
        for x in (report.get('v202_audit') or {}).get('horizons',[]):
            a=x.get('selection_vs_same_pool') or {};b=x.get('selection_vs_0050') or {};c=x.get('policy_vs_0050') or {}
            rr.append({'週期':f"{x.get('horizon')}日",'核心選股平均':percent(x.get('model_mean_net')),
                       '完整選股日／基準日':f"{x.get('cascade_complete_dates')}/{x.get('benchmark_complete_dates')}",
                       '選股vs同池等權':percent(a.get('mean')),'IID 95%下緣':percent(a.get('bootstrap_90_low')),
                       '季度群聚95%下緣':percent(a.get('quarter_cluster_90_low')),
                       '不重疊案例':a.get('disjoint_cases'),'不重疊平均':percent(a.get('disjoint_mean')),
                       '單純選股vs0050':percent(b.get('mean')),'配置策略vs0050':percent(c.get('mean')),
                       '配置群聚95%下緣':percent(c.get('quarter_cluster_90_low'))})
        if rr:st.dataframe(pd.DataFrame(rr),hide_index=True,use_container_width=True)
    else:
        st.warning('這份報告仍是V20.1／更早版本；下方 Fixed/Adaptive 只是舊控制組。更新V20.3-final後請跑一次自動清理驗證，才會產生Core-first雙基準結果。')
    validation_overview(report)
    broader_results(report)
    report_supports(report,LABELS)
    factor_section(report,LABELS)
    counts=report.get('fit_status_counts') or {}
    if counts:
        with st.expander('各次權重調整結果',expanded=False):
            st.json(counts)
    from v196_factors import simple_summary,profile_label
    simple=simple_summary(report)
    if simple:
        with st.expander('\u7c21\u55ae\u5c0d\u7167\u7d44\u6709\u6c92\u6709\u52dd\u904e\u8907\u96dc\u6a21\u578b\uff1f',expanded=False):
            st.caption('\u9019\u4e9b\u662f\u56fa\u5b9a\u6b0a\u91cd\u5c0d\u7167\uff0c\u4e0d\u662f\u4e8b\u5f8c\u6311\u9078\u7684\u6b63\u5f0f\u63a8\u85a6\u3002\u6bcf\u5217\u53ea\u6bd4\u8f03\u540c\u65e5\u3001\u540c\u50f9\u683c\u57fa\u790e\u7684\u6709\u6548\u7d50\u679c\uff0c\u975e\u7d2f\u7a4d\u5831\u916c\u3002')
            st.dataframe(pd.DataFrame([{'\u6301\u6709\u65e5':x['horizon'],'\u56fa\u5b9a\u5c0d\u7167':profile_label(x['profile']),'\u914d\u5c0d\u6578':x['paired_cases'],'\u5e73\u5747\u6de8\u5831\u916c':percent(x['net']),'0050\u540c\u65e5':percent(x['benchmark_net']),'\u5dee\u7570':percent(x['excess'])} for x in simple]),hide_index=True,use_container_width=True)
    if cfg.factor_design in ('ten_angle_v197','balanced_v198'):
        from v197_selection import ten_summary
        from v197_ten_pillars import LENSES
        with st.expander('十面向研究：哪些訊號有效？',expanded=True):
            st.caption('市場狀態與可成交性是風控，不當成各股票加分；產業成分未歷史核實者僅研究。缺財報或公告時點時不補假數據。')
            coverage=report.get('ten_pillar_coverage',[])
            if coverage:st.dataframe(pd.DataFrame([{'因子':x['name'],'資料覆蓋率':f"{x['coverage']:.0%}",'證據註記':x['reason']} for x in coverage]),hide_index=True,use_container_width=True)
            d=report.get('ten_pillar_shadow_summary') or ten_summary(report)
            if d:
                compare=pd.DataFrame([{'週期':x['horizon'],'固定假說':x['profile'],'同期有效組數':x['paired_cases'],'淨報酬':percent(x['mean_net']),'舊模型':percent(x['legacy_mean']),'0050':percent(x['benchmark_mean']),'相對0050':percent(x['vs_0050'])} for x in d])
                st.dataframe(compare,hide_index=True,use_container_width=True)
            st.caption('固定假說只是研究對照。這批基準日已被反覆分析，不是新的盲測；不同週期的可比較組數不同。')
        if cfg.factor_design=='balanced_v198':
            from v20_model import evidence_summary
            v20=report.get('v20_audit') or {}
            with st.expander('V20.3-final：Core-first／雙基準證據',expanded=True):
                st.caption('V20.3-final不再把5/20/60各自當alpha引擎：60日核心排序，20日確認、5日進場只作Gate；選股先比同池等權，配置才比0050。')
                if v20.get('horizons'):
                    rows20=[]
                    for x in v20.get('horizons',[]):
                        rows20.append({'層級':{5:'Tactical',20:'Next Compounder',60:'Core'}.get(x.get('horizon')),
                            '持有日':x.get('horizon'),'模型':x.get('profile'),'配對數':x.get('paired_cases'),
                            '平均淨報酬':percent(x.get('mean_net')),'0050':percent(x.get('benchmark_mean')),
                            '平均超額':percent(x.get('mean_excess')),'Bootstrap 90%下緣':percent(x.get('bootstrap_90_low')),
                            '季度群聚95%下緣':percent(x.get('quarter_cluster_90_low')),
                            '前半／後半':percent(x.get('first_half_mean_excess'))+' / '+percent(x.get('second_half_mean_excess'))})
                    st.dataframe(pd.DataFrame(rows20),hide_index=True,use_container_width=True)
                    st.json({'status':v20.get('status'),'source':v20.get('source'),
                             'automatic_orders_authorized':v20.get('automatic_orders_authorized')})
                else:
                    ev=evidence_summary()
                    st.info('目前載入的是V20發布前的S8報告；下列是綜合S4/S6/S7/S8後凍結的V20架構。自動驗證完成後會在此與進度區直接顯示跨波結果。')
                    st.json({'核心60日雙袖套':ev['core_sleeves'],'即時排名代理':ev['anchors'],
                             '階層權重':ev['hierarchy_weights'],'開發期證據':ev['development_evidence']})
            from v198_selection import optimized_audit
            oldaudit=report.get('v1987_robustness_audit') or report.get('v1986_optimized_audit') or optimized_audit(report)
            with st.expander('V19.8歷史反證紀錄（V20重構依據）',expanded=False):
                ar=[]
                for x in oldaudit.get('horizons',[]):
                    ar.append({'持有日':x.get('horizon'),'舊凍結設定':x.get('profile'),
                               '同口徑組數':x.get('paired_cases'),'平均淨報酬':percent(x.get('mean_net')),
                               '0050同日':percent(x.get('benchmark_mean')),'平均超額':percent(x.get('mean_excess')),
                               'Bootstrap 90%下緣':percent(x.get('bootstrap_90_low')),
                               '季度群聚95%下緣':percent(x.get('quarter_cluster_bootstrap_90_low')),
                               '前半／後半':percent(x.get('first_half_mean_excess'))+' / '+percent(x.get('second_half_mean_excess')),
                               '狀態':x.get('status')})
                if ar:st.dataframe(pd.DataFrame(ar),hide_index=True,use_container_width=True)
                st.caption('這些已曝光歷史結果只用來解釋為何V20放棄「5/20/60三套獨立alpha」的舊架構，不是V20的新盲測績效。')
    records=pd.DataFrame(report.get('results',[]))
    if not records.empty:
        table=records.pivot_table(index=['date','horizon'],columns='strategy',values='mean_net',aggfunc='first',dropna=False).reset_index()
        table=table.rename(columns={'date':'基準日','horizon':'持有交易日','baseline':'固定權重','adaptive':'逐步調整權重',
                                    'benchmark_0050':'0050同口徑','equal_weight_universe':'股票池等權','guarded':'證據門檻／現金',
                                    'training_challenger_research':'事前訓練候選（未必採用）',
                                    'expanded_fixed_research':'舊擴充固定試驗組' })
        for c in ('固定權重','逐步調整權重','0050同口徑','股票池等權','證據門檻／現金','事前訓練候選（未必採用）','舊擴充固定試驗組'):
            if c in table:table[c]=table[c].map(percent)
        for c in list(table.columns):
            if str(c).startswith('simple_control_'):
                table[c]=table[c].map(percent)
                table=table.rename(columns={c:profile_label(c)})
        for c in list(table.columns):
            if str(c).startswith('ten_shadow_'):
                table[c]=table[c].map(percent)
                table=table.rename(columns={c:'十面向研究：'+c.removeprefix('ten_shadow_')})
        st.dataframe(table,hide_index=True,use_container_width=True)
        st.caption('「—」代表該組不完整，不是報酬0。60日結果可能跨除權息、分割或停牌；異常未還原價格區間不拿來證明策略勝出。')
    with st.expander('每次訓練、排除因子與完整來源紀錄',expanded=False):
        st.json({'overlap':report.get('overlapping_horizons'), 'sampling_plan':report.get('sampling_plan'),
                 'resumed_cases':report.get('resumed_cases'), 'adjusted_bar_fraction':report.get('adjusted_bar_fraction')})
        st.caption('完整逐輪權重與來源請下載JSON或診斷包，避免手機一次載入數千筆訓練紀錄。')
    pointer=read_json(DATA/'last_success.json')
    directory=Path(pointer['directory']) if pointer.get('directory') else None
    if directory and directory.resolve().is_relative_to((DATA/'runs').resolve()):
        for fn,label,mime in [('v198_diagnostic_bundle.zip','下載V19.8分層母池完整驗證包（股價／因子／權重）','application/zip'),
                              ('v197_diagnostic_bundle.zip','下載V19.7相容格式資料包','application/zip'),
                              ('sparse_factor_selection.csv','下載每次因子去留與權重','text/csv'),
                              ('sparse_latest_weights.csv','下載各週期最新候選權重','text/csv'),
                              ('factor_validation_summary.csv','下載因子效果總表','text/csv'),
                              ('factor_validation_cases.csv','下載每日每因子驗證','text/csv'),
                              ('sampling_plan.json','下載抽樣日期與種子','application/json'),
                              ('v191_diagnostic_bundle.zip','下載相容格式診斷包','application/zip'),
                              ('comparison.csv','下載全部基準日比較表','text/csv'),
                              ('selected_trades.csv','下載每檔選股／買賣基準／結果','text/csv'),
                              ('v19_results.json','下載完整結果與每輪權重','application/json'),
                              ('v19_validation.md','下載研究報告','text/markdown')]:
            path=directory/fn
            if path.exists():st.download_button(label,path.read_bytes(),file_name=fn,mime=mime,key='dl_'+fn)
    with st.expander('逐欄位檢查（全部已載入股票）',expanded=False):
        health=pd.DataFrame(field_health(panel,report))
        if 'field' in health:health['field']=health.field.map(lambda x:LABELS.get(x,x))
        st.dataframe(health.rename(columns={'field':'欄位','present':'有值筆數','total':'母數','coverage':'有值比例','state':'狀態'}),hide_index=True,use_container_width=True)
        st.caption('有值比例不等於資料正確率；頸線空值也可能表示沒有W底。營收、法人、大戶等缺值不會補成0或捏造連買日數。')

@st.fragment(run_every=20)
def live_tile(ticker):
    from v19_live import observation
    quote=observation(ticker)
    if quote.get('pending') and quote.get('price') is None:
        st.info('正在查詢當日行情；日線分析仍可使用，不需要等待整頁重新計算。')
    if quote.get('price') is not None:
        st.metric('當日觀察價',number(quote['price']),delta=percent(quote.get('change_pct'),1))
        st.caption(f"來源 {quote.get('source','—')}｜成交／分鐘時間 {quote.get('timestamp','—')}｜{quote.get('age_label','—')}")
        if quote.get('observed_black_to_red'):st.info('本次追蹤已觀察到由昨收下方轉至上方；這是已發生的現象，不是事前預測命中。')
    else:
        st.warning('當日成交價尚未取得：'+str(quote.get('reason') or '來源仍查詢中'))
    st.caption('盤中與日線日期分開。第三方分鐘價、過期官方價不冒充可成交買點；V19新權重尚不自動發布下單指令。')
    with st.expander('盤中來源診斷',expanded=False):
        st.json(quote)

def page_doctor(panel,report,cfg):
    st.subheader('個股診斷：日線結構與當日行情分開')
    if panel.empty:
        st.info('請先下載歷史日線，或使用原有V18資料庫。')
        return
    names=panel.sort_values('date').drop_duplicates('ticker',keep='last').set_index('ticker')['name'].to_dict()
    tickers=sorted(names)
    default=tickers.index('2330.TW') if '2330.TW' in tickers else 0
    ticker=st.selectbox('已載入股票',tickers,index=default,format_func=lambda t:f"{names[t]} {t}",key='v19_doctor_ticker')
    h=st.radio('評估週期',list(cfg.horizons),horizontal=True,format_func=lambda x:f'{x}交易日',key='v19_doctor_h')
    stock=panel[panel.ticker==ticker].sort_values('date');row=stock.iloc[-1]
    weights,state=weights_for(report,h,row.date)
    scoring_cfg=cfg
    if cfg.factor_design in ('sparse_v194','sparse_v195','tournament_v196','ten_angle_v197','balanced_v198'):weights,scoring_cfg=choose_model(report,h,cfg,row.date,LABELS,key='v194_doctor_mode')
    # Display does not require a stock to pass the candidate filter.
    from v19_features import score_rows
    scored=stock.tail(1).copy();scored['score'],scored['factor_coverage']=score_rows(scored,weights,min_coverage=1.-1e-9 if scoring_cfg.factor_design in ('sparse_v194','sparse_v195','tournament_v196','ten_angle_v197','balanced_v198') else .75)
    observed=scored.iloc[-1].to_dict()
    observed['setup']='WATCH';observed['stop_reference']=max(float(row.support10),float(row.close-1.8*row.atr)) if pd.notna(row.atr) and pd.notna(row.support10) else np.nan
    observed['stop_reference']=min(observed['stop_reference'],float(row.close)*.99)
    observed['stop_distance_pct']=(row.close-observed['stop_reference'])/row.close*100
    observed['reference_low']=row.close-.5*row.atr;observed['reference_high']=row.close+.25*row.atr
    observed['chase_ceiling']=row.close+min(row.atr,row.close*.03)
    candidate_card(observed,analog_summary(panel,row,h,weights),h,weights,1)
    st.caption(f"股票最新日線 {str(row.date.date())}；整體模型最新資料 {str(panel.date.max().date())}。")
    if st.checkbox('顯示當日盤中觀察（每20秒檢查）',value=False,key='v19_live_enable'):
        live_tile(ticker)
    data=stock.tail(120)
    fig=go.Figure(go.Candlestick(x=data.date,open=data.open,high=data.high,low=data.low,close=data.close,name='日K'))
    fig.add_trace(go.Scatter(x=data.date,y=data.ma20,name='20日均線'))
    fig.add_trace(go.Scatter(x=data.date,y=data.ma60,name='60日均線'))
    fig.update_layout(height=390,margin=dict(l=8,r=8,t=20,b=10),xaxis_rangeslider_visible=False,legend=dict(orientation='h'))
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(pd.DataFrame([{'指標':LABELS.get(k,k),'數值':number(row.get(k))} for k in ('rsi','k','d','macd_hist','bias20','neckline')]),hide_index=True,use_container_width=True)
    if not bool(row.eligible):st.warning('本檔未通過目前候選池條件；可查看資料，不會自動當成推薦股。')

def news_block():
    with st.expander('可能影響台股：最近72小時新聞與國際摘要',expanded=False):
        from briefing_jobs import load_brief,ensure_brief
        from market_briefing import _only_recent_news
        if st.button('更新新聞／國際摘要',key='v19_news_refresh'):
            ensure_brief(BASE,force=True)
            st.info('已啟動新聞更新；稍後重新開啟此區即可查看。')
        brief=load_brief(BASE);news=_only_recent_news(brief.get('news') or {},now=datetime.now(TZ),max_age_hours=72)
        if not news.get('items'):st.caption('目前沒有可核對發布時間的72小時內新聞；不以舊新聞補滿。')
        for row in (news.get('items') or [])[:10]:
            st.markdown('**'+str(row.get('title',''))+'**')
            st.caption(str(row.get('published_iso',''))+'｜'+str(row.get('source','')))
            if row.get('summary'):st.write(row['summary'])
            if row.get('impact'):st.write(row['impact'])
            if str(row.get('link','')).startswith(('https://','http://')):st.link_button('來源文章',row['link'])

def _render_stage_gate(gate, *, title='階段檢核'):
    if not gate or not gate.get('stage'):
        return
    execution=gate.get('execution_status')
    research=gate.get('research_status')
    complete=int(gate.get('complete_adaptive_cases',0) or 0)
    expected=int(gate.get('expected_cases',0) or 0)
    coverage=float(gate.get('download_coverage',0) or 0)
    dates=int(gate.get('cutoff_dates',0) or 0)
    requested=int(gate.get('requested_dates',0) or 0)
    attempted=int(gate.get('attempted_cases',0) or 0)
    if execution=='STAGE_COMPLETE':
        st.success(f"{title}：STAGE_COMPLETE｜研究品質 {research}")
    else:
        st.warning(f"{title}：{execution}｜研究品質 {research}")
    st.caption(f"資料完整度 {coverage*100:.1f}%｜基準日 {dates}/{requested}｜日期×週期運算 {attempted}/{expected}｜結果完整 {complete}/{expected}")
    if research=='RESEARCH_PARTIAL' and execution=='STAGE_COMPLETE':
        st.caption('注意：結果完整度屬研究品質指標，不再等同晉級鎖；缺漏案例仍會在診斷報告逐案標示。')
    rows=[]
    for item in gate.get('checks') or []:
        actual=item.get('actual')
        required=item.get('required')
        if item.get('key')=='history_coverage':
            actual=f"{float(actual or 0)*100:.1f}%";required=f">= {float(required or 0)*100:.0f}%"
        rows.append({'檢核':item.get('label') or item.get('key'),'結果':'✅' if item.get('ok') else '❌',
                     '目前':actual,'門檻':required})
    if rows:
        with st.expander('查看階段檢核明細',expanded=False):
            st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            if gate.get('blocking_reasons'):
                st.caption('阻擋原因：'+'、'.join(map(str,gate.get('blocking_reasons') or [])))
            if gate.get('warnings'):
                st.caption('研究警示：'+'、'.join(map(str,gate.get('warnings') or [])))


def _select_research_stage(label):
    st.session_state['v1984_stage']=label
    st.session_state.pop('ar_cloud_allow_panel',None)


def main(configure_page=True):
    # app.py sets page config before calling this in Cloud; standalone callers
    # can still ask this function to configure its own page exactly once.
    if configure_page:
        st.set_page_config(page_title='Alpha Radar V20.3-final',page_icon='📈',layout='wide',initial_sidebar_state='collapsed')
    _bootstrap();st.markdown(CSS,unsafe_allow_html=True)
    st.title('Alpha Radar V20.3-final')
    st.caption('近年日線驗證 × 可追溯權重 × 投資規劃｜V20.3-final：清理母池 × Core-first 60日排序 × 20日確認Gate × 5日進場Gate｜雙基準驗證')

    # V20 reads the last EXECUTION-COMPLETE stage, not only a
    # RESEARCH_COMPLETE outcome report.  read_last_report() also recovers an
    # already-finished V19.8.4 partial stage from runs/ without rerunning it.
    last_report=read_last_report(DATA)
    last_gate=evaluate_stage_gate(last_report) if last_report else {}
    completed_stage=(last_gate.get('stage') if last_gate.get('execution_status')=='STAGE_COMPLETE' else None)
    manual_keys=[x['key'] for x in STAGES]
    # Automatic A1/A2/A3 reports rank after S8 internally, but the user-facing
    # staged selector intentionally stops at S8 in V20.1.
    manual_completed=('S8' if completed_stage in ({x['key'] for x in AUTO_WAVES}|{'A1','A2','A3'}) else completed_stage)
    if manual_completed not in manual_keys:manual_completed=None
    recommended_key=next_stage_key(manual_completed) or manual_completed or 'S1'
    stage_labels=[x['label'] for x in STAGES]
    recommended_label=get_stage(recommended_key)['label']
    auto_state=auto_campaign_status(DATA)
    if auto_state and str(auto_state.get('version'))!='20.3-final':
        auto_state=dict(auto_state,state='LEGACY_DONE')
    if auto_state.get('state')=='INTERRUPTED':
        ensure_auto_campaign(DATA)
        auto_state=auto_campaign_status(DATA)
    if st.session_state.get('v1984_stage') not in stage_labels:
        st.session_state['v1984_stage']=recommended_label

    with st.sidebar:
        with st.expander('\u820a\u7248\u7814\u7a76\u53c3\u6578\uff08\u975e\u6700\u7d42\u9a57\u6536\u6d41\u7a0b\uff09',expanded=False):
            st.subheader('分階段研究設定')
            stage_label=st.selectbox('本輪規模',stage_labels,key='v1984_stage')
            stage=next(x for x in STAGES if x['label']==stage_label)
            stage_key=stage['key']
            st.caption(f"{stage['stocks']}檔 × {stage['dates']}個基準日 × 5/20/60日；每批下載 {stage['batch_size']} 檔。前一階段成功後才解鎖。")
            years=st.selectbox('歷史區間（年）',[1,2,3],index=2,key='v19_years')
            universe_mode=st.selectbox('股票母池選取方式',['balanced','proportional','legacy_random'],index=0,
                format_func=lambda x:{'balanced':'上市／上櫃×產業分層（建議）','proportional':'按當前產業家數比例','legacy_random':'舊版純隨機比較'}[x],key='v198_pool_mode')
            st.caption('V20.3-final手動安全階梯仍只到S8；後續一鍵跑2波150檔×48日期。新波次先用證交所／櫃買中心現行官方名冊清掉舊代碼，再按當前產業家數比例抽樣，不再用A3的污染母池。')
            end=st.date_input('資料截止日',value=datetime.now(TZ).date()-timedelta(days=1),
                              max_value=datetime.now(TZ).date()-timedelta(days=1),key='v19_end')
            optional_allowed=bool(stage['optional_allowed'])
            extra=st.checkbox('補抓營收／法人／融資',value=False,disabled=not optional_allowed,key='v19_optional')
            if stage_key in ('S5','S6','S7','S8'):
                st.caption('S5～S8刻意只跑價量與既有可追溯因子；S7改時間點、S8再改股票樣本。S8之後由V20自動驗證接手，缺乏公告時點證據的基本面／籌碼仍不硬塞進歷史權重。')
            elif not optional_allowed:
                st.caption('前3階段只跑價量，先確認穩定性；第4階段（100檔）可選配額外資料。')
            st.markdown('#### 因子研究')
            design=st.selectbox('研究引擎',['balanced_v198','ten_angle_v197','tournament_v196','sparse_v195'],
                format_func=lambda x:'V20 階層式核心／確認／進場模型（建議）' if x=='balanced_v198' else 'V19.7 十面向研究' if x=='ten_angle_v197' else 'V19.6.1 決策檢查' if x=='tournament_v196' else 'V19.5 稀疏因子搜尋',key='v196_engine')
            max_factors=st.selectbox('稀疏模型最多因子數',[2,3,4,5,6],index=4,key='v194_max_factors')
            finance_allowed=bool(stage['finance_allowed'] and extra)
            finance=st.checkbox('並下載季報與本益比',value=False,disabled=not finance_allowed,key='v194_finance')
            financial_timing=st.selectbox('季報或營收缺公告時點',['disclosure_required','lagged_research'],
                format_func=lambda x:'嚴格：無公告時點不納入' if x=='disclosure_required' else '研究延後假設（非實盤證據）',key='v194_timing')
            seed=st.number_input('日期隨機種子',min_value=0,max_value=2**31-1,value=1920,step=1,key='v192_seed')
            sampling=st.selectbox('基準日抽樣方式',['uniform','stratified'],index=0,
                                  format_func=lambda x:'全期隨機（沿用前階段口徑）' if x=='uniform' else '分段隨機（日期較分散）',key='v192_sampling')
            refresh=st.checkbox('強制重新下載（一般續跑不勾）',value=False,key='v192_refresh')
            adjusted=st.checkbox('優先使用還原價（失敗時保留原價並標示）',value=True,key='v191_adjusted')
            legacy=st.checkbox('開啟V18.21原工作台（保留舊模型）',value=False,key='v19_legacy')
    if legacy:
        st.info('以下是保留的V18.21原工作台，不是V19新研究排名。')
        import legacy_app
        legacy_app.main(configure_page=False)
        return

    base_cfg=Settings(years=years,stocks=int(stage['stocks']),dates=int(stage['dates']),
                 seed=int(seed),sampling_method=sampling,as_of=end.isoformat(),optional_data=extra,
                 prefer_adjusted=adjusted,refresh_history=refresh,request_budget=int(stage['request_budget']),
                 universe_mode=universe_mode,sparse_max_inputs=int(max_factors),
                 sparse_budget=int(stage['search_budget']),financial_history=finance,
                 financial_timing=financial_timing,factor_design=design)
    cfg=apply_stage(base_cfg,stage_key,optional_data=extra,financial_history=finance)
    st.markdown('### '+ '\u6700\u7d42\u6b77\u53f2\u9a57\u6536\uff08\u56fa\u5b9a\u5169\u6ce2\uff0c\u4e0d\u518d\u9010\u968e\u6309\u9215\uff09')
    from v20_final import PROTOCOL_VERSION
    fs=auto_campaign_status(DATA)
    if fs.get('state') not in ('RUNNING','DONE'):
        if st.button('\u25b6 \u4e00\u9375\u57f7\u884c\uff0f\u7e8c\u8dd1\u6700\u7d42\u9a57\u6536',key='final_acceptance_start',type='primary'):
            result=start_auto_campaign(DATA,base_cfg,resume=True)
            if result.get('started'):st.rerun()
            else:st.warning(str(result.get('state')))
    if fs.get('state')=='DONE':
        st.write({'\u6838\u5fc3\u9a57\u6536':(fs.get('summary') or {}).get('core_verdict'),
                  '\u539f\u59cb\u5168\u90e8\u76ee\u6a19':(fs.get('summary') or {}).get('full_original_goal')})
    bundle=DATA/'V20_FINAL_RESULTS.zip'
    if bundle.is_file():
        st.download_button('\u4e0b\u8f09\u5169\u6ce2\u5b8c\u6574\u9a57\u6536\u5305',bundle.read_bytes(),'V20_FINAL_RESULTS.zip',mime='application/zip',key='final_bundle_download')
    st.caption('\u7a0b\u5f0f\u5b8c\u6210\u4e0d\u7b49\u65bc\u7b56\u7565\u901a\u904e\uff1b\u4e0d\u901a\u904e\u6216\u8b49\u64da\u4e0d\u8db3\u90fd\u6703\u505c\u6b62\uff0c\u4e0d\u81ea\u52d5\u8ffd\u52a0\u6e2c\u8a66\u3002')
    with st.expander('\u820a\u7248 S \u968e\u6bb5\u8a3a\u65b7\uff08\u6700\u7d42\u9a57\u6536\u4e0d\u9700\u8981\u4f7f\u7528\uff09',expanded=False):
        completed_idx=stage_index(manual_completed) if manual_completed else -1
        current_idx=stage_index(stage_key)
        can_run=current_idx <= completed_idx+1 and bool(stage['cloud_enabled']) and auto_state.get('state')!='RUNNING'
        latest_attempt=read_latest_attempt_report(DATA)
        latest_attempt_gate=evaluate_stage_gate(latest_attempt) if latest_attempt else {}
    
        # Make the actual execution scope unmissable on mobile.  This prevents a
        # user from thinking S2/S5 is running while the worker still has S1 config.
        st.info(f"目前選擇：{stage_key}｜{stage['label']}｜{cfg.stocks}檔 × {cfg.dates}日期 × 5/20/60日")
        st.caption(f"本階段最低下載完整度 {float(stage['min_download_coverage'])*100:.0f}%｜批次 {stage['batch_size']} 檔｜Cloud風險等級 {stage['risk_tier']}。")
        if stage_key=='S7':
            st.caption(f"S7交叉確認固定設定：日期種子 {cfg.seed}｜抽樣 {cfg.sampling_method}；刻意與S6預設1920／uniform不同。")
        elif stage_key=='S8':
            st.caption(f"S8壓力測試固定設定：日期種子 {cfg.seed}｜股票母池種子 {cfg.universe_seed}｜抽樣 {cfg.sampling_method}；排除S4/S6/S7已曝光日期。")
    
        if manual_completed:
            done_stage=get_stage(manual_completed)
            st.success('手動安全階梯已完成至 '+done_stage['label'])
            if completed_stage in manual_keys:
                _render_stage_gate(last_gate,title=f'{completed_stage} 執行檢核')
            next_key=next_stage_key(manual_completed)
            if next_key and current_idx <= completed_idx:
                nxt=get_stage(next_key)
                st.button(f"▶ 進入{nxt['label']}｜{nxt['stocks']}檔 × {nxt['dates']}日期",
                          type='primary',key='v1984_next_stage',on_click=_select_research_stage,args=(nxt['label'],))
            elif next_key and stage_key==next_key:
                st.caption(f"下一步就是本頁的 {next_key}；完成後再自動推進。")
            elif manual_completed=='S8':
                st.success('S1～S8安全階梯已完成。V20.3-final不再往S9/S10；直接用單一清理母池＋Core-first自動驗證計畫。')
                st.caption('一次啟動後自動跑2波：150檔×48日期 → 150檔×48日期；兩波更換股票／日期種子、排除已曝光日期，且固定V20.3-final規則，不在同批結果上重調權重。')
                if auto_state.get('state') not in ('RUNNING','DONE'):
                    label='▶ 一鍵啟動 V20.3-final 清理母池＋核心驗證' if not auto_state else '▶ 續跑 V20.3-final 清理母池＋核心驗證'
                    if st.button(label,type='primary',key='v20_auto_start'):
                        result=start_auto_campaign(DATA,base_cfg,resume=True)
                        if result.get('started'):st.rerun()
                        else:st.info(str(result.get('state')))
                elif auto_state.get('state')=='RUNNING':
                    st.info('V20.3-final自動驗證正在背景連續執行；不需再按A、B或「下一階段」。')
                elif auto_state.get('state')=='DONE':
                    st.success('V20.3-final自動清理＋核心驗證已全部完成。')
        elif current_idx==0:
            st.info('尚未有V20可辨識的完成階段紀錄，請先由第1階段開始。')
    
        # If the newest attempted stage did not pass, show the exact failed check
        # instead of leaving the user to repeatedly press A/B without explanation.
        if (latest_attempt_gate.get('stage')==stage_key
                and latest_attempt_gate.get('execution_status')!='STAGE_COMPLETE'):
            _render_stage_gate(latest_attempt_gate,title=f'{stage_key} 最近一次執行')
    
        if current_idx > completed_idx+1:
            st.warning('此階段尚未解鎖。為避免再次一次放太大，請先完成前一階段。')
        elif stage_key=='S5':
            st.warning('S5是新的橋接階段：只從100擴到120檔，不開選配資料；若Cloud中斷，重新按A/B會沿用既有快取與安全checkpoint。')
        elif stage_key=='S6':
            st.warning('S6是Cloud邊界驗證：120成功後才跑150檔。若連續兩次因資源中斷，停止Cloud重試，改用離線 staged runner。')
        elif stage_key=='S7':
            st.warning('S7不再放大股票數：維持150檔，固定改用日期種子271828＋stratified抽樣24個基準日，且排除S4/S6已用過的精確基準日，專門檢查凍結候選是否跨不同時間點仍成立。S6快取完整時可先按B，不必重抓同一批150檔。')
        elif stage_key=='S8':
            st.warning('S7結果未確認5/20日核心候選；S8維持150檔，但更換股票母池種子與日期種子做反證。這一階段已成為V20重構的重要證據來源。')
    
        if manual_completed!='S8':
            c1,c2=st.columns(2)
            with c1:
                if st.button('A｜下載／補齊本階段資料',type='primary',key='v1984_download',disabled=not can_run):
                    result=start_job(DATA,cfg,'download_only')
                    if result.get('started'):st.rerun()
                    else:st.info(str(result.get('state')))
            with c2:
                if st.button('B｜用快取執行本階段驗證',key='v1984_validate',disabled=not can_run):
                    result=start_job(DATA,cfg,'cache_validate')
                    if result.get('started'):st.rerun()
                    else:st.info(str(result.get('state')))
            with st.expander('進階：同一步驟下載後直接驗證',expanded=False):
                st.caption('前置安全階梯仍可手動拆成下載與驗證；S8完成後改由V20自動驗證接手。')
                if st.button('下載＋驗證',key='v1984_combined',disabled=not can_run):
                    result=start_job(DATA,cfg,'download_validate')
                    if result.get('started'):st.rerun()
                    else:st.info(str(result.get('state')))
        else:
            st.caption('S8之後手動A/B已收起；請使用上方V20.3-final自動驗證，一次啟動後自動連續完成。')
    progress_box()
    database_download(DATA)
    import_evidence_control(DATA)
    # The original app eagerly built the ENTIRE historical factor panel before
    # the user selected a page. Only load a recent display panel on demand.
    if st.button('載入最新選股與個股分析（節省記憶體）', key='ar_cloud_load_panel'):
        st.session_state['ar_cloud_allow_panel'] = True
    if cfg.stocks > 1000 and st.session_state.get('ar_cloud_allow_panel', False):
        st.error('目前設定超過1000檔。Cloud前端不直接建構超大型面板；完整歷史研究請用資料庫／離線工具。')
        return
    if not st.session_state.get('ar_cloud_allow_panel', False):
        last = read_last_report(DATA)
        st.info('資料與設定控制已就緒。需要查看即時候選或個股圖表時，請按「載入最新選股與個股分析」。完整歷史驗證由上方任務執行，無須首頁先載入全部K線。')
        if last:
            st.caption('已有完整歷史研究報告；可選擇上方任務繼續下一階段，或載入分析畫面。')
        return
    if fs.get('base_settings'):
        from v19_service import _settings_from_dict
        cfg=apply_stage(_settings_from_dict(fs['base_settings']),'C2' if fs.get('state')=='DONE' else 'C1')
    try:
        panel,_=_display_data(str(DATA),_mtime(DATA/'history_prices.csv.gz'),
                             max(_mtime(DATA/'historical_evidence.csv.gz'),_mtime(DATA/'optional_evidence.csv')),_mtime(BASE/'daily_prices.sqlite'),cfg)
        report=read_last_report(DATA)
    except Exception as exc:
        panel=pd.DataFrame();report=read_last_report(DATA)
        st.error('資料檢查未通過，未填入假數字：'+type(exc).__name__+': '+str(exc))
    view=st.radio('功能',['選股與規劃','歷史驗證','個股診斷'],horizontal=True,label_visibility='collapsed',key='v19_view')
    if view=='選股與規劃':page_decisions(panel,report,cfg);news_block()
    elif view=='歷史驗證':page_validation(panel,report,cfg)
    else:page_doctor(panel,report,cfg)
    st.caption('公開日線可以先驗證技術策略；歷史營收、籌碼與大戶資料只有在發布時間可用時才加入。各階段基準日仍是開發診斷；只有跨階段結果穩定，才值得再擴大研究，仍不代表未來獲利保證。')

