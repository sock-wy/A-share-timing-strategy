# -*- coding: utf-8 -*-
"""
A股权益择时 · 多策略回测面板（全中文）
======================================
运行：  streamlit run dashboard/app.py

· 标的（导航栏顶部切换）：中证800（研报基准）/ 沪深300 / 中证1000（同结构复刻）
    - 全市场信号（宏观/跨境/衍生品/资金流）：信号相同，只是换标的持有；
    - 技术信号（筹码结构/长端动量）：由各标的自身 OHLC 重算。
    - 每个标的独立参数存档文件：我的参数组.json（中证800）/ 我的参数组_沪深300.json 等，互不影响。
· 全策略汇总页：各子策略「组1」复现 vs 研报 + 可编辑「备注」（09/10 可切进阶版汇总）
· 单策略页：研报原文 + 参数数字框(±步进) + 3 组参数存档 + 净值/指标/逐笔交易
· 09/10 另有【进阶版】：一键跳转，独立参数存档，可「用这套参数做汇总」
"""
import sys
import re
import json
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loader import load_index
from src.backtest import run_backtest
from src.plotting import nav_figure
from src.runner import load_strategy, build_signal_for
from src.config import (REPORT_PERF, PARAM_SPACE, PARAMS, CATEGORIES,
                        REPORT_RESULT_TEXT, REPORT_METHOD_TEXT, MA_KIND_STRATEGIES,
                        MATH_EXPLAIN, ADVANCED, BENCH, TARGETS,
                        DATA_MODE_STRATEGIES, DATA_MODE_OPTIONS, PARAM_HELP,
                        STRAT_LOGIC, COMPOSITE_MEMBERS, COMPOSITE_RESERVED)
from src.composite import run_composites

STRATS = {
    "01 宏观流动性": "01_宏观流动性", "02 信贷预期": "02_信贷预期",
    "03 中美汇率": "03_中美汇率", "04 中美利差": "04_中美利差",
    "05 期货基差": "05_期货基差", "06 期权PCR": "06_期权PCR",
    "07 融资融券": "07_融资融券", "08 大小单资金": "08_大小单资金",
    "09 筹码结构": "09_筹码结构", "10 长端动量": "10_长端动量",
}
NODATA_FOLDERS = {"08_大小单资金": "大小单资金"}   # 缺数据、汇总里只占位显示研报值
METRIC_ORDER = ["年化收益率", "年化波动率", "年化IR", "最大回撤", "Calmar比率",
                "周胜率", "周赔率", "信号次胜率", "信号次赔率", "次均天数", "信号次数"]
PCT = {"年化收益率", "年化波动率", "最大回撤", "周胜率", "信号次胜率"}
_DM_LABEL = {v: k for k, v in DATA_MODE_OPTIONS.items()}   # 内部值->友好标签


def fmt(k, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    if k in PCT:
        return f"{v*100:.2f}%"
    if k in {"次均天数", "信号次数"}:
        return f"{v:.0f}"
    return f"{v:.2f}"


def logic_html(txt):
    """把简洁交易逻辑(轻markdown)转成精致小字卡片的 HTML。"""
    txt = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", txt)
    txt = txt.replace("\n\n", "<br>").replace("\n", "<br>")
    return f'<div class="trade-logic">{txt}</div>'


# ---------------- 参数组存档：strategies/<folder>/我的参数组[_标的].json ----------------
def group_file(folder, target=BENCH):
    fn = "我的参数组.json" if target == BENCH else f"我的参数组_{target}.json"
    return ROOT / "strategies" / folder / fn


def load_groups(folder, target=BENCH):
    f = group_file(folder, target)
    return json.load(open(f, encoding="utf-8")) if f.exists() else {}


def write_groups(folder, data, target=BENCH):
    json.dump(data, open(group_file(folder, target), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def seed_group(folder, target, slot="组1"):
    """取某标的某组参数作旋钮初值；非基准标的若无存档，回退复用中证800 的同名组（调好的起点）。"""
    g = load_groups(folder, target).get(slot)
    if g:
        return g
    if target != BENCH:
        return load_groups(folder, BENCH).get(slot, {}) or {}
    return {}


@st.cache_resource
def get_module(folder, filename="策略.py"):
    return load_strategy(folder, filename)


@st.cache_data(show_spinner=False)
def compute(folder, params_items, confirm=1, start=None, end=None,
            filename="策略.py", target=BENCH):
    """跑一次回测（按标的）。params_items=None 用默认参数；否则用传入参数（元组化以便缓存）。"""
    mod = get_module(folder, filename)
    params = dict(params_items) if params_items else None
    signal = build_signal_for(mod, params, target)
    res = run_backtest(load_index(target), signal, name=mod.NAME,
                       confirm_weeks=confirm, start=start, end=end)
    return res["metrics"], res["weekly"], res["trades"], mod.NAME, mod.REPORT_KEY


def summary_variant(folder, data):
    """返回被选为「用于汇总」的进阶变体 dict；无则 None。兼容旧键 用进阶汇总=True。"""
    variants = ADVANCED.get(folder, [])
    name = data.get("汇总用变体")
    if not name and data.get("用进阶汇总") and variants:
        name = variants[0]["name"]
    return next((v for v in variants if v["name"] == name), None)


def compute_group1(folder, target=BENCH):
    """汇总用复现。参数来源：中证800 用自己的；沪深300/中证1000 一律沿用中证800 的
    组1 与进阶变体选择（信号在各自标的上重算）。选了进阶变体则用该变体「<gpre>组1」。"""
    cfg = load_groups(folder, BENCH if target != BENCH else target)   # 参数来源(非基准→中证800)
    v = summary_variant(folder, cfg)
    if v:
        g = cfg.get(f"{v['gpre']}组1")
        if g:
            confirm = int(g.get("confirm_weeks", 1))
            params = {k: val for k, val in g.items() if k != "confirm_weeks"}
            items = tuple(sorted(params.items())) if params else None
            return compute(folder, items, confirm, filename=v["file"], target=target)
    g = cfg.get("组1")
    if g:
        confirm = int(g.get("confirm_weeks", 1))
        params = {k: val for k, val in g.items() if k != "confirm_weeks"}
        return compute(folder, tuple(sorted(params.items())), confirm, target=target)
    return compute(folder, None, target=target)


@st.cache_data(show_spinner="计算组合信号（含动态赋权滚动优化）……")
def cached_composite_signals():
    from src.composite import composite_signals
    return composite_signals()                      # ({标签:综合信号}, 成员信号, 动态权重)


@st.cache_data(show_spinner="计算子策略信号……")
def cached_member_signals():
    from src.composite import member_signals
    return member_signals()


def corr_heatmap(corr):
    """相关性热力图（高档配色：petrol↔cream↔terracotta 发散）。"""
    import plotly.graph_objects as go
    z = corr.values
    scale = [[0.0, "#2a6f7f"], [0.5, "#f4f1ea"], [1.0, "#b06a3b"]]   # 负→0→正
    fig = go.Figure(go.Heatmap(
        z=z, x=list(corr.columns), y=list(corr.index), zmid=0, zmin=-1, zmax=1,
        colorscale=scale, xgap=3, ygap=3,
        text=[[f"{v*100:.0f}" for v in row] for row in z], texttemplate="%{text}",
        textfont=dict(size=13), hovertemplate="%{y} × %{x}: %{z:.2f}<extra></extra>",
        colorbar=dict(title="相关性", tickformat=".0%", outlinewidth=0)))
    fig.update_layout(
        height=520, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif", color="#1c2126"),
        yaxis=dict(autorange="reversed"))
    return fig


st.set_page_config(page_title="A股择时多策略面板", layout="wide")

# ---------------- 高档主题：字体 + 配色 + 组件细节 ----------------
st.markdown("""
<style>
  html, body, [class*="css"], .stMarkdown, p, span, div, label, input, button, table, td, th {
    font-family: "Inter","PingFang SC","Microsoft YaHei","Hiragino Sans GB",
                 -apple-system,"Segoe UI",Roboto,sans-serif;
  }
  h1, h2, h3, h4 {
    font-family: "Songti SC","STSong","Noto Serif CJK SC","Source Han Serif SC",
                 Georgia,"Times New Roman",serif !important;
    letter-spacing:.012em; color:#141a1f; font-weight:700;
  }
  h1 { font-size:2rem !important; padding-bottom:.35rem;
       border-bottom:2px solid #0e6e62; display:inline-block; margin-bottom:.4rem; }
  h3 { font-size:1.28rem !important; }
  .block-container { padding-top:2.4rem; max-width:1400px; }
  .stButton > button { border-radius:9px; transition:all .15s ease; font-weight:500; }
  .stButton > button:hover { box-shadow:0 2px 9px rgba(14,110,98,.13); transform:translateY(-1px); }
  [data-testid="stSidebar"] { border-right:1px solid #e7e3d9; }
  [data-testid="stSidebar"] .stButton > button { text-align:left; }
  [data-testid="stDataFrame"], [data-testid="stTable"] { border-radius:10px; overflow:hidden;
       border:1px solid #e7e3d9; }
  [data-testid="stAlert"] { border-radius:11px; }
  [data-testid="stMetricValue"] { font-family:"Georgia",serif; }
  [data-testid="stCaptionContainer"] { color:#7a766c; }
  hr { border-color:#e7e3d9; }
  a { color:#0e6e62; }
  .trade-logic { font-size:.82rem; line-height:1.7; color:#41464c; background:#f6f5f0;
    border-left:3px solid #0e6e62; border-radius:8px; padding:11px 15px; margin:.1rem 0 .9rem; }
  .trade-logic b { color:#141a1f; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.title("A股权益择时 · 多策略回测面板")
st.caption("开源证券《权益择时的多策略框架：从宏观驱动到微观验证》复现 · 6维度10子策略 + 组合合成")

# ---------------- 侧边栏导航：标的目录 + 六大维度手风琴 ----------------
if "view" not in st.session_state:
    st.session_state.view = ("strategy", "宏观流动性", "01_宏观流动性", BENCH)

VIEW = st.session_state.view
cur_target = VIEW[-1] if VIEW[-1] in TARGETS else BENCH

st.sidebar.title("导航")
st.sidebar.markdown("**① 选择标的**")
tgt = st.sidebar.radio("标的（回测/复刻对象）", TARGETS, index=TARGETS.index(cur_target),
                       captions=["研报基准", "大盘·复刻", "小盘·复刻"], label_visibility="collapsed")
if tgt != cur_target:                                    # 切标的 -> 跳该标的汇总页
    st.session_state.view = ("summary", tgt)
    st.rerun()

st.sidebar.markdown(f"**② {tgt} · 菜单**")
if st.sidebar.button(f"📊 {tgt} 全策略汇总", use_container_width=True,
                     type="primary" if VIEW[0] == "summary" else "secondary"):
    st.session_state.view = ("summary", tgt)
    st.rerun()
if st.sidebar.button("🧩 组合策略（中证800）", use_container_width=True,
                     type="primary" if VIEW[0] == "composite" else "secondary"):
    st.session_state.view = ("composite",)
    st.rerun()
if st.sidebar.button("🔗 子策略相关性", use_container_width=True,
                     type="primary" if VIEW[0] == "correlation" else "secondary"):
    st.session_state.view = ("correlation",)
    st.rerun()

st.sidebar.caption("研报六大维度（点开选子策略）")
_cur = VIEW[2] if VIEW[0] in ("strategy", "advanced") else None
for _cat, _subs in CATEGORIES.items():
    with st.sidebar.expander(_cat, expanded=any(f == _cur for _, f in _subs)):
        for _sname, _folder in _subs:
            if st.button(_sname, key=f"nav_{tgt}_{_folder}", use_container_width=True,
                         type="primary" if _folder == _cur else "secondary"):
                st.session_state.view = ("strategy", _sname, _folder, tgt)
                st.rerun()
            for _v in ADVANCED.get(_folder, []):
                if st.button(f"   └ 🚀 {_v['label']}", key=f"navadv_{tgt}_{_folder}_{_v['name']}",
                             use_container_width=True):
                    st.session_state.view = ("advanced", _v["name"], _folder, tgt)
                    st.rerun()


# ============================================================ 单策略渲染（原版/进阶版/多标的共用）
def render_strategy(folder, target, variant=None):
    is_advanced = variant is not None
    filename = variant["file"] if is_advanced else "策略.py"
    gpre = variant["gpre"] if is_advanced else ""
    mod = get_module(folder, filename)
    name, rkey = mod.NAME, mod.REPORT_KEY
    rep = REPORT_PERF.get(rkey, {})
    is_bench = (target == BENCH)
    space = PARAM_SPACE.get(name, {})
    defaults = PARAMS.get(name, {})
    kpre = f"{target}|{folder}" + (f"@{gpre}" if is_advanced else "")
    groups = load_groups(folder, target)
    g1 = groups.get(f"{gpre}组1") or seed_group(folder, target, f"{gpre}组1")

    tag = ("　🚀进阶版" if is_advanced else "")
    tgt_tag = "" if is_bench else f"　【{target} 复刻】"
    st.subheader(name + tag + tgt_tag)
    st.markdown("**🧭 交易逻辑**")
    st.markdown(logic_html(STRAT_LOGIC.get(name, "")), unsafe_allow_html=True)
    if name in MATH_EXPLAIN:
        with st.expander("公式细节"):
            st.markdown(MATH_EXPLAIN[name])
    if not is_bench:
        idx_dep = getattr(mod, "INDEX_DEPENDENT", False)
        st.caption(f"🔁 {target} 复刻：" + ("本策略为技术信号，信号由 " + target + " 自身 OHLC 重算。"
                   if idx_dep else "本策略为全市场信号，信号与中证800 相同，仅把持有对象换成 " + target + "。")
                   + f"　参数独立存于 我的参数组_{target}.json（无则默认复用你中证800 的组1 作起点）。")

    # ---------------- 已保存参数组（载入/覆盖你存好的组1） ----------------
    saved = groups.get(f"{gpre}组1") or seed_group(folder, target, f"{gpre}组1")
    bc = st.columns([1, 1, 2])
    if bc[0].button("📂 已保存参数组", key=f"loadsaved_{kpre}", disabled=not saved,
                    use_container_width=True):
        for pn, v in saved.items():
            sk = f"{kpre}_confirm" if pn == "confirm_weeks" else f"{kpre}_{pn}"
            if pn == "confirm_weeks" or pn in space or pn in ("ma_kind", "data_mode"):
                st.session_state[sk] = int(v) if pn == "confirm_weeks" else v
        st.rerun()
    save_clicked = bc[1].button("💾 保存当前参数", key=f"savecur_{kpre}", use_container_width=True)
    bc[2].caption("「已保存参数组」= 我的参数组.json 的组1（全策略汇总/组合用它）；保存 = 用当前参数覆盖。")

    # ---------------- 参数（数字框 + 加减号）----------------
    st.markdown("**参数**（数字框旁 −/＋ 按步长增减，也可直接输入；每个旋钮下方小字=它在本策略里的作用）")
    cols = st.columns(max(1, len(space)))
    params = {}
    help_map = PARAM_HELP.get(name, {})
    for (pn, (lo, hi, step)), c in zip(space.items(), cols):
        key = f"{kpre}_{pn}"
        is_int = float(step).is_integer() and float(lo).is_integer()
        if key not in st.session_state:
            dflt = g1.get(pn, defaults.get(pn, lo))
            st.session_state[key] = int(dflt) if is_int else float(dflt)
        if is_int:
            params[pn] = c.number_input(pn, min_value=int(lo), max_value=int(hi),
                                        step=int(step), key=key)
        else:
            dec = len(str(step).split(".")[1]) if "." in str(step) else 2
            params[pn] = c.number_input(pn, min_value=float(lo), max_value=float(hi),
                                        step=float(step), key=key, format=f"%.{dec}f")
        if pn in help_map:                                   # 旋钮下方注明作用
            c.caption(help_map[pn])

    if name in MA_KIND_STRATEGIES:
        mk = f"{kpre}_ma_kind"
        if mk not in st.session_state:
            st.session_state[mk] = g1.get("ma_kind", "SMA")
        params["ma_kind"] = st.radio(
            "均线类型（信号定义不变：仍是长短均线差→方向；EMA 滞后更小、更灵敏）",
            ["SMA", "EMA"], horizontal=True, key=mk)
    if name in DATA_MODE_STRATEGIES:
        dm = f"{kpre}_data_mode"
        if dm not in st.session_state:
            st.session_state[dm] = g1.get("data_mode", "插值")
        params["data_mode"] = st.radio(
            "信贷数据口径（插值=Wind日度含未来函数/原始；月度阶梯PIT=时点、不插值、无未来函数）",
            list(DATA_MODE_OPTIONS.values()), horizontal=True, key=dm,
            format_func=lambda v: _DM_LABEL.get(v, v))
    c_hold, c_date = st.columns([1, 2])
    cf = f"{kpre}_confirm"
    if cf not in st.session_state:
        st.session_state[cf] = int(g1.get("confirm_weeks", 1))
    confirm = c_hold.number_input(
        "信号确认周数（去抖，1=不去抖；调大→信号连续N周同向才切换仓位，过滤单周毛刺）",
        min_value=1, max_value=12, step=1, key=cf)
    dmin, dmax = datetime.date(2015, 1, 5), datetime.date(2025, 11, 28)
    dr = c_date.slider("回测时间段（拖动做样本内/外测试）", min_value=dmin, max_value=dmax,
                       value=(dmin, dmax), format="YYYY-MM-DD", key=f"date_{kpre}")
    start, end = str(dr[0]), str(dr[1])

    # ---------------- 保存当前参数 -> 已保存参数组（组1） ----------------
    if save_clicked:
        g = dict(params)
        g["confirm_weeks"] = int(confirm)
        data = load_groups(folder, target)
        data[f"{gpre}组1"] = g
        write_groups(folder, data, target)
        st.success(f"已保存为「已保存参数组」（{group_file(folder, target).name} · {gpre}组1）：{g}")

    # ---------------- 进阶版：用于全策略汇总的开关 ----------------
    if is_advanced:
        data = load_groups(folder, target)
        cur = data.get("汇总用变体")
        st.markdown("**🔖 用于全策略汇总**（开启后汇总页该策略改用本变体参数；否则用原版组1）")
        tc = st.columns([2, 2, 3])
        if tc[0].button("📌 用这套参数做汇总", key=f"useadv_{kpre}", use_container_width=True,
                        type="primary"):
            g = dict(params)
            g["confirm_weeks"] = int(confirm)
            d = load_groups(folder, target)
            d[f"{gpre}组1"] = g
            d["汇总用变体"] = name
            d.pop("用进阶汇总", None)
            write_groups(folder, d, target)
            st.success(f"已设为汇总用：{name}（存入{gpre}组1）")
            st.rerun()
        if tc[1].button("↩️ 汇总改回原版组1", key=f"useorig_{kpre}", use_container_width=True):
            d = load_groups(folder, target)
            d["汇总用变体"] = None
            d.pop("用进阶汇总", None)
            write_groups(folder, d, target)
            st.info("汇总已改回原版组1")
            st.rerun()
        tc[2].caption(f"当前全策略汇总使用：{('✅ ' + cur) if cur else '原版组1'}")

    # —— 指标实际分布统计 ——
    if hasattr(mod, "indicator"):
        ind = (mod.indicator(params, index_name=target) if getattr(mod, "INDEX_DEPENDENT", False)
               else mod.indicator(params)).loc[start:end].dropna()
        if len(ind):
            iname = getattr(mod, "INDICATOR_NAME", "均线差(短−长)")
            q15, q85 = ind.quantile([0.15, 0.85])
            txt = (f"📐「{iname}」区间统计：均值 **{ind.mean():+.4f}**，标准差 {ind.std():.4f}，"
                   f"全距 [{ind.min():+.3f}, {ind.max():+.3f}]，中央70%集中在 [{q15:+.4f}, {q85:+.4f}]，"
                   f">0 占比 {(ind>0).mean()*100:.0f}%")
            if hasattr(mod, "LONG_BELOW"):
                thr = params.get("threshold", 0.0)
                lb = mod.LONG_BELOW
                pct = (ind < thr).mean() * 100 if lb else (ind > thr).mean() * 100
                txt += f"；当前阈值 {thr:+.4f} → 做多占比（{'差<阈值' if lb else '差>阈值'}）{pct:.0f}%"
            elif "p" in params:
                pv = params["p"]
                txt += f"；当前 p={pv:.2f} → |指标|>p 触发占比 {(ind.abs() > pv).mean()*100:.0f}%"
            st.caption(txt + "。")

    # —— 回测（当前参数）——
    m, wk, trades, _, _ = compute(folder, tuple(sorted(params.items())), int(confirm),
                                  start, end, filename, target)
    st.plotly_chart(nav_figure({"weekly": wk, "name": f"{name}（{target}·当前参数）"}),
                    use_container_width=True)

    # —— 绩效指标 ——
    rep_col = "研报" if is_bench else "研报(中证800参考)"
    st.markdown(f"**绩效指标（当前参数复现 vs {rep_col}）**")
    tbl = pd.DataFrame({
        "指标": METRIC_ORDER,
        "复现": [fmt(k, m.get(k)) for k in METRIC_ORDER],
        rep_col: [fmt(k, rep.get(k)) for k in METRIC_ORDER],
    })
    st.dataframe(tbl, use_container_width=True, hide_index=True)
    st.caption(("研报列为全区间数值；拖动上方时间段只改变「复现」列。" if is_bench else
                f"⚠ 研报只做了中证800，此列仅作参考量级；{target} 的“基准”应看净值图中的 {target} 买入持有。")
               + ("　进阶版仍与研报“" + rkey + "”原始绩效对照。" if is_advanced else ""))

    # —— 逐笔交易明细 ——
    st.markdown("**逐笔交易明细（当前参数，每改一次参数即刷新）**")
    st.dataframe(trades, use_container_width=True, hide_index=True)


# ============================================================ 视图分发
if VIEW[0] == "summary":
    target = VIEW[-1] if VIEW[-1] in TARGETS else BENCH
    is_bench = (target == BENCH)
    title = "全策略汇总：各策略「组1」参数复现 vs 研报" + ("" if is_bench else f"（{target} 复刻）")
    st.subheader(title)
    if not is_bench:
        st.caption(f"⚠ 研报仅覆盖中证800。下表「研报」列为中证800 参考量级；技术类信号已按 {target} "
                   f"自身 OHLC 重算，全市场信号为同信号换 {target} 持有。{target} 一律沿用中证800 的组1/变体参数。")
    rows = []
    for disp, folder in STRATS.items():
        data = load_groups(folder, target)                  # 本标的(仅取备注)
        if folder in NODATA_FOLDERS:                         # 缺数据策略：只占位、不回测
            rep = REPORT_PERF.get(NODATA_FOLDERS[folder], {})
            rows.append({
                "子策略": disp, "复现年化": "-", "研报年化": fmt("年化收益率", rep.get("年化收益率")),
                "复现IR": "-", "研报IR": fmt("年化IR", rep.get("年化IR")),
                "复现回撤": "-", "研报回撤": fmt("最大回撤", rep.get("最大回撤")),
                "复现次数": "-", "研报次数": fmt("信号次数", rep.get("信号次数")),
                "备注": data.get("备注") or "数据缺失（缺超大单主动净流入）",
            })
            continue
        cfg = load_groups(folder, BENCH) if not is_bench else data   # 参数来源(非基准→中证800)
        use_adv = summary_variant(folder, cfg)
        m, *_, rkey = compute_group1(folder, target)
        rep = REPORT_PERF.get(rkey, {})
        rows.append({
            "子策略": disp + ("　🚀进阶" if use_adv else ""),
            "复现年化": fmt("年化收益率", m["年化收益率"]),
            "研报年化": fmt("年化收益率", rep.get("年化收益率")),
            "复现IR": fmt("年化IR", m["年化IR"]),
            "研报IR": fmt("年化IR", rep.get("年化IR")),
            "复现回撤": fmt("最大回撤", m["最大回撤"]),
            "研报回撤": fmt("最大回撤", rep.get("最大回撤")),
            "复现次数": fmt("信号次数", m["信号次数"]),
            "研报次数": fmt("信号次数", rep.get("信号次数")),
            "备注": data.get("备注", ""),
        })
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df, hide_index=True, use_container_width=True,
        disabled=[c for c in df.columns if c != "备注"],
        column_config={"备注": st.column_config.TextColumn("备注（可编辑，自动保存）", width="large")},
        key=f"summary_editor_{target}")
    for _, r in edited.iterrows():
        folder = STRATS[r["子策略"].replace("　🚀进阶", "")]
        note = r["备注"] or ""
        data = load_groups(folder, target)
        if data.get("备注", "") != note:
            data["备注"] = note
            write_groups(folder, data, target)
    st.caption("复现列使用各子策略「组1」参数（未保存则用默认/复用中证800组1）；"
               "09/10 若开启「用进阶汇总」则用其进阶版「进阶组1」（带🚀进阶标记）。备注可直接编辑，自动保存。")

elif VIEW[0] == "correlation":
    st.subheader("子策略相关性 · 中证800")
    _mem = "、".join(n for n, _ in COMPOSITE_MEMBERS)
    _rsv = "、".join(n for n, _ in COMPOSITE_RESERVED)
    st.markdown("**🧭 基础信息**")
    st.info("**看什么**：各子策略【择时信号】两两之间的皮尔逊相关性——衡量它们是否“同涨同跌”，"
            "相关性越低，组合分散化收益越好（研报表12 同口径）。\n\n"
            "**怎么算**：每个子策略用其「组1」参数在中证800 上生成日频信号（多/空/延续），"
            "对齐到交易日后计算两两相关系数，区间 2015-01 ~ 2025-11。\n\n"
            f"**范围**：当前仅这 {len(COMPOSITE_MEMBERS)} 个组合成员：{_mem}。"
            f"　预留接口（后续可加入）：{_rsv}（08 缺数据）——接入组合后此表自动纳入。")

    import numpy as np
    member_sigs = cached_member_signals()
    years = ["全区间"] + [str(y) for y in range(2015, 2026)]
    ycol, _sp = st.columns([1, 3])
    year = ycol.selectbox("🕒 时间线（选年份看当年相关性）", years, index=0, key="corr_year")
    sl = member_sigs if year == "全区间" else member_sigs.loc[year]
    corr = sl.corr().fillna(0.0)                       # 某年信号恒定→无相关，置0
    for _i in range(len(corr)):
        corr.iat[_i, _i] = 1.0

    st.plotly_chart(corr_heatmap(corr), use_container_width=True)
    off = corr.values[np.triu_indices(len(corr), 1)]
    hi = np.abs(off).max() if len(off) else 0.0
    st.caption(f"【{year}】非对角相关性：均值 {off.mean()*100:.0f}%，绝对值最大 {hi*100:.0f}%，"
               f"|相关|>30% 的组合 {int((np.abs(off)>0.3).sum())}/{len(off)} 对。"
               "相关性越低，组合分散化收益越好（与研报结论一致）。切换年份可看相关性随市况的变化。")
    with st.expander("📋 相关性矩阵（数值表）"):
        st.dataframe((corr * 100).round(0).astype(int), use_container_width=True)

elif VIEW[0] == "composite":
    st.subheader("组合策略（合成模型） · 中证800")
    _mem = "、".join(n for n, _ in COMPOSITE_MEMBERS)
    _rsv = "、".join(n for n, _ in COMPOSITE_RESERVED)
    st.caption(f"当前纳入 {len(COMPOSITE_MEMBERS)} 个子策略：{_mem}。"
               f"　预留接口（后期可接入）：{_rsv}（08 缺数据）。"
               f"　各成员用其「组1」参数在中证800 上出信号，再合成。")
    st.info("**等权合成**：各子策略信号等权平均 → 综合信号>0 满仓、≤0 空仓。\n\n"
            "**动态赋权**：滚动 120 日约束优化 —— 最小化 ‖|R_t| − Σ wᵢ·Sⁱ·R_t‖²，"
            "约束 0.5/N ≤ wᵢ ≤ 1.5/N、Σwᵢ=1（研报 N=10 用 5%~15%）。")

    comp_sigs, member_sigs, W = cached_composite_signals()
    dmin, dmax = datetime.date(2015, 1, 5), datetime.date(2025, 11, 28)
    dr = st.slider("🕒 时间轴（拖动选回测区间 / 样本内外）", min_value=dmin, max_value=dmax,
                   value=(dmin, dmax), format="YYYY-MM-DD", key="comp_date")
    cstart, cend = str(dr[0]), str(dr[1])
    bench_df = load_index(BENCH)
    for tag in ["等权合成", "动态赋权"]:
        r = run_backtest(bench_df, comp_sigs[tag], name=tag, start=cstart, end=cend)
        m = r["metrics"]
        rep = REPORT_PERF.get(tag, {})
        st.markdown(f"### {tag}")
        st.plotly_chart(nav_figure({"weekly": r["weekly"], "name": f"{tag}（中证800）"}),
                        use_container_width=True)
        tbl = pd.DataFrame({
            "指标": METRIC_ORDER,
            "复现": [fmt(k, m.get(k)) for k in METRIC_ORDER],
            "研报(全10子策略)": [fmt(k, rep.get(k)) for k in METRIC_ORDER],
        })
        st.dataframe(tbl, use_container_width=True, hide_index=True)
        if tag == "动态赋权":
            wlast = W.iloc[-1].sort_values(ascending=False)
            st.caption("最新一期动态权重：" + "　".join(f"{k} {v*100:.1f}%" for k, v in wlast.items()))
    st.caption("研报列为全区间数值；拖动上方时间轴只改变「复现」列（可做样本内/外）。"
               "⚠ 研报组合用全部 10 个子策略且子策略更强，故复现量级低于研报(16.79%/22.15%)；"
               "本组合排除 01/08/09（接口已留），把预留成员 folder 移入 config.COMPOSITE_MEMBERS 即可接入。")

elif VIEW[0] == "advanced":
    folder, target = VIEW[2], VIEW[-1]
    variants = ADVANCED[folder]
    variant = next((v for v in variants if v["name"] == VIEW[1]), variants[0])
    top = st.columns([1, 4])
    if top[0].button("↩️ 返回原版", key=f"back_{target}_{folder}", use_container_width=True):
        _oname = next((s for subs in CATEGORIES.values() for s, f in subs if f == folder), folder)
        st.session_state.view = ("strategy", _oname, folder, target)
        st.rerun()
    top[1].caption(f"你正在查看【{variant['label']}】（标的：{target}）。原版及其它变体保留不变；本页参数存档独立。")
    render_strategy(folder, target, variant)

else:  # strategy（原版）
    folder, target = VIEW[2], VIEW[-1]
    if folder == "08_大小单资金":
        st.warning("「大小单资金」子策略缺“超大单主动净流入”数据，暂未实现（占位）。")
        st.stop()

    variants = ADVANCED.get(folder, [])
    if variants:
        jc = st.columns(len(variants) + 1)
        for i, v in enumerate(variants):
            if jc[i].button(f"🚀 {v['label']}", key=f"toadv_{target}_{folder}_{v['name']}",
                            use_container_width=True, type="primary"):
                st.session_state.view = ("advanced", v["name"], folder, target)
                st.rerun()
        jc[-1].caption("进阶变体 = 另一套建仓/平仓逻辑（原版保留）。可各自独立存参数、选择是否用于汇总。")

    render_strategy(folder, target, None)
