# -*- coding: utf-8 -*-
"""
A股权益择时 · 多策略回测面板（全中文）
======================================
运行：  streamlit run dashboard/app.py

功能：
  · 全策略汇总页：所有子策略 × 研报指标 vs 当前复现 的大表
  · 单策略页 —— 两个标签：
      标签1「基准表现」：默认参数下完整回测（净值曲线 + 研报全部指标 + 逐笔交易）
      标签2「参数复原对比」：参数旋钮实时调参 → 复现曲线 vs 中证800 + 特征指标对研报
"""
import sys
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
from src.runner import load_strategy
from src.config import (REPORT_PERF, PARAM_SPACE, PARAMS, CATEGORIES,
                        REPORT_RESULT_TEXT, REPORT_METHOD_TEXT, MA_KIND_STRATEGIES)

# 已实现子策略：显示名 -> 目录（08 大小单缺数据未登记）
STRATS = {
    "01 宏观流动性": "01_宏观流动性", "02 信贷预期": "02_信贷预期",
    "03 中美汇率": "03_中美汇率", "04 中美利差": "04_中美利差",
    "05 期货基差": "05_期货基差", "06 期权PCR": "06_期权PCR",
    "07 融资融券": "07_融资融券", "09 筹码结构": "09_筹码结构",
    "10 长端动量": "10_长端动量",
}
METRIC_ORDER = ["年化收益率", "年化波动率", "年化IR", "最大回撤", "Calmar比率",
                "周胜率", "周赔率", "信号次胜率", "信号次赔率", "次均天数", "信号次数"]
PCT = {"年化收益率", "年化波动率", "最大回撤", "周胜率", "信号次胜率"}


def fmt(k, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    if k in PCT:
        return f"{v*100:.2f}%"
    if k in {"次均天数", "信号次数"}:
        return f"{v:.0f}"
    return f"{v:.2f}"


@st.cache_resource
def get_module(folder):
    return load_strategy(folder)


@st.cache_data(show_spinner=False)
def compute(folder, params_items, confirm=1, start=None, end=None):
    """跑一次回测。params_items=None 用默认参数；否则用传入参数（元组化以便缓存）。"""
    mod = get_module(folder)
    params = dict(params_items) if params_items else None
    res = run_backtest(load_index("中证800"), mod.build_signal(params),
                       name=mod.NAME, confirm_weeks=confirm, start=start, end=end)
    return res["metrics"], res["weekly"], res["trades"], mod.NAME, mod.REPORT_KEY


st.set_page_config(page_title="A股择时多策略面板", layout="wide")
st.title("A股权益择时 · 多策略回测面板")

# ---------------- 侧边栏导航：六大维度手风琴，点开选子策略 ----------------
if "view" not in st.session_state:
    st.session_state.view = ("strategy", "宏观流动性", "01_宏观流动性")

st.sidebar.title("导航")
if st.sidebar.button("📊 全策略汇总", use_container_width=True,
                     type="primary" if st.session_state.view[0] == "summary" else "secondary"):
    st.session_state.view = ("summary",)
    st.rerun()

st.sidebar.markdown("**研报六大维度**（点开选子策略）")
_cur = st.session_state.view[2] if st.session_state.view[0] == "strategy" else None
for _cat, _subs in CATEGORIES.items():
    with st.sidebar.expander(_cat, expanded=any(f == _cur for _, f in _subs)):
        for _sname, _folder in _subs:
            if st.button(_sname, key=f"nav_{_folder}", use_container_width=True,
                         type="primary" if _folder == _cur else "secondary"):
                st.session_state.view = ("strategy", _sname, _folder)
                st.rerun()

VIEW = st.session_state.view

# ============================================================ 全策略汇总
if VIEW[0] == "summary":
    st.subheader("全策略汇总：当前复现 vs 研报")
    rows = []
    for disp, folder in STRATS.items():
        m, *_ , rkey = compute(folder, None)
        rep = REPORT_PERF.get(rkey, {})
        rows.append({
            "子策略": disp,
            "复现年化": fmt("年化收益率", m["年化收益率"]),
            "研报年化": fmt("年化收益率", rep.get("年化收益率")),
            "复现IR": fmt("年化IR", m["年化IR"]),
            "研报IR": fmt("年化IR", rep.get("年化IR")),
            "复现回撤": fmt("最大回撤", m["最大回撤"]),
            "研报回撤": fmt("最大回撤", rep.get("最大回撤")),
            "复现次数": fmt("信号次数", m["信号次数"]),
            "研报次数": fmt("信号次数", rep.get("信号次数")),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("默认参数下的复现；调参请点左侧某个子策略进入单策略详情。")

# ============================================================ 单策略详情
else:
    folder = VIEW[2]                              # 侧边栏手风琴选中的子策略目录
    # 08 大小单资金缺数据、未实现 —— 友好提示后停止
    if folder == "08_大小单资金":
        st.warning("「大小单资金」子策略缺“超大单主动净流入”数据，暂未实现（占位）。")
        st.stop()

    mod = get_module(folder)
    name, rkey = mod.NAME, mod.REPORT_KEY
    rep = REPORT_PERF.get(rkey, {})
    space = PARAM_SPACE.get(name, {})
    defaults = PARAMS.get(name, {})
    recovered_file = ROOT / "strategies" / folder / "复原参数.json"
    scan_file = ROOT / "strategies" / folder / "扫描摘要.json"
    scan_data = json.load(open(scan_file, encoding="utf-8")) if scan_file.exists() else {}

    st.subheader(name)
    # ---------------- 研报原文·策略定义与建仓/平仓逻辑（开头摘抄）----------------
    st.markdown("**📄 研报原文·策略定义与建仓/平仓逻辑**")
    st.info(REPORT_METHOD_TEXT.get(name, "（研报未单列该子策略方法）"))

    # 已保存的个人设置（若有则作为参数初值；下次打开自动载入）
    saved_file = ROOT / "strategies" / folder / "我的设置.json"
    saved = json.load(open(saved_file, encoding="utf-8")) if saved_file.exists() else {}

    # ---------------- 参数（数字框 + 加减号）+ 载入按钮 ----------------
    st.markdown("**参数**（数字框旁 −/＋ 按步长增减，也可直接输入；实时重算净值 / 指标 / 逐笔交易）")
    b1, b2, _ = st.columns([1, 1, 2])
    if recovered_file.exists() and b1.button("载入复原参数"):
        for pn, v in json.load(open(recovered_file, encoding="utf-8")).items():
            st.session_state[f"{folder}_{pn}"] = v
        st.rerun()
    if "综合最相似" in scan_data and b2.button("载入最相似参数"):
        for pn, v in scan_data["综合最相似"]["参数"].items():
            st.session_state[f"{folder}_{pn}"] = v
        st.rerun()

    cols = st.columns(max(1, len(space)))
    params = {}
    for (pn, (lo, hi, step)), c in zip(space.items(), cols):
        key = f"{folder}_{pn}"
        is_int = float(step).is_integer() and float(lo).is_integer()
        if key not in st.session_state:
            dflt = saved.get(pn, defaults.get(pn, lo))
            st.session_state[key] = int(dflt) if is_int else float(dflt)
        if is_int:
            params[pn] = c.number_input(pn, min_value=int(lo), max_value=int(hi),
                                        step=int(step), key=key)
        else:
            dec = len(str(step).split(".")[1]) if "." in str(step) else 2   # 按步长定小数位
            params[pn] = c.number_input(pn, min_value=float(lo), max_value=float(hi),
                                        step=float(step), key=key, format=f"%.{dec}f")

    # 均线类型 SMA/EMA（仅对支持的策略；信号定义不变，仅均线类型可选）
    if name in MA_KIND_STRATEGIES:
        mk = f"{folder}_ma_kind"
        if mk not in st.session_state:
            st.session_state[mk] = saved.get("ma_kind", "SMA")
        params["ma_kind"] = st.radio(
            "均线类型（信号定义不变：仍是长短均线差→方向；EMA 滞后更小、更灵敏）",
            ["SMA", "EMA"], horizontal=True, key=mk)
    st.caption(f"当前参数：{params}")

    c_hold, c_date = st.columns([1, 2])
    cf = f"{folder}_confirm"
    if cf not in st.session_state:
        st.session_state[cf] = int(saved.get("confirm_weeks", 1))
    confirm = c_hold.number_input(
        "信号确认周数（去抖，1=不去抖；调大→信号连续N周同向才切换仓位，过滤单周毛刺）",
        min_value=1, max_value=12, step=1, key=cf)
    dmin, dmax = datetime.date(2015, 1, 5), datetime.date(2025, 11, 28)
    dr = c_date.slider("回测时间段（拖动做样本内/外测试）", min_value=dmin, max_value=dmax,
                       value=(dmin, dmax), format="YYYY-MM-DD")
    start, end = str(dr[0]), str(dr[1])

    # 保存当前参数设置 -> 我的设置.json（下次打开该策略自动载入）
    if st.button("💾 保存当前设置（下次打开自动载入）"):
        to_save = dict(params)
        to_save["confirm_weeks"] = int(confirm)
        json.dump(to_save, open(saved_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        st.success(f"已保存：{to_save}")

    # —— 指标(均线差)在当前区间的统计：帮助选阈值、看谁多谁少 ——
    if hasattr(mod, "indicator"):
        ind = mod.indicator(params).loc[start:end].dropna()
        if len(ind):
            thr = params.get("threshold", 0.0)
            who = "高于" if ind.mean() > 0 else "低于"
            st.caption(
                f"📐 当前区间「均线差(短−长)」均值 {ind.mean():+.4f}，标准差 {ind.std():.4f}，"
                f"区间 [{ind.min():+.3f}, {ind.max():+.3f}]；短均线平均**{who}**长均线（差>0 占比 {(ind>0).mean()*100:.0f}%）。"
                f"当前阈值 {thr:+.3f} → 做多占比（差<阈值）{(ind < thr).mean()*100:.0f}%。")

    # —— 当前参数回测（净值 / 指标 / 逐笔交易 都用这一次结果）——
    m, wk, trades, _, _ = compute(folder, tuple(sorted(params.items())), int(confirm), start, end)
    st.plotly_chart(nav_figure({"weekly": wk, "name": f"{name}（当前参数）"}),
                    use_container_width=True)

    # ---------------- 绩效指标（当前参数复现 vs 研报）+ 综合最相似 ----------------
    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.markdown("**绩效指标（当前参数复现 vs 研报）**")
        tbl = pd.DataFrame({
            "指标": METRIC_ORDER,
            "复现": [fmt(k, m.get(k)) for k in METRIC_ORDER],
            "研报": [fmt(k, rep.get(k)) for k in METRIC_ORDER],
        })
        st.dataframe(tbl, use_container_width=True, hide_index=True)
        st.caption("研报列为全区间数值；拖动上方时间段只改变「复现」列，用于样本内/外对比。")
    with col_r:
        if "综合最相似" in scan_data:
            sim = scan_data["综合最相似"]
            st.markdown(f"**🎯 综合最相似参数**：`{sim['参数']}` ｜ 综合距离 **{sim['综合距离']:.3f}**")
            bd = pd.DataFrame(sim["逐指标"])
            bd["复现"] = [fmt(k, v) for k, v in zip(bd["指标"], bd["复现"])]
            bd["研报"] = [fmt(k, v) for k, v in zip(bd["指标"], bd["研报"])]
            bd["相对偏差"] = [f"{x*100:.1f}%" if x is not None else "-" for x in bd["相对偏差"]]
            st.dataframe(bd[["指标", "复现", "研报", "相对偏差", "权重"]],
                         use_container_width=True, hide_index=True)
            st.caption(sim["说明"])   # 一行小字：距离怎么算、哪些×2

    # ---------------- 逐笔交易明细（随参数更新）----------------
    st.markdown("**逐笔交易明细（当前参数，每改一次参数即刷新）**")
    st.dataframe(trades, use_container_width=True, hide_index=True)

    # ---------------- 底部：研报原文 + 参数扫描要点 ----------------
    st.markdown("---")
    st.markdown("**📄 研报原文·结果描述**")
    st.info(REPORT_RESULT_TEXT.get(name, "（研报未单列该子策略结果）"))
    if scan_data:
        a, d, ir = scan_data["年化最高"], scan_data["回撤最小"], scan_data["IR最高"]
        st.markdown(f"**🔍 参数扫描要点**（在预设网格 {scan_data['网格组合数']} 组组合上遍历）")
        st.markdown(
            f"- **年化最高 {a['年化收益率']*100:.2f}%** ← 参数 `{a['参数']}`"
            f"（此时 回撤 {a['最大回撤']*100:.2f}%、IR {a['年化IR']:.2f}、信号 {a['信号次数']} 次）\n"
            f"- **最大回撤最小 {d['最大回撤']*100:.2f}%**（限年化>0）← 参数 `{d['参数']}`"
            f"（此时 年化 {d['年化收益率']*100:.2f}%）\n"
            f"- **年化IR最高 {ir['年化IR']:.2f}** ← 参数 `{ir['参数']}`"
            f"（年化 {ir['年化收益率']*100:.2f}%、回撤 {ir['最大回撤']*100:.2f}%）"
        )
        st.caption("扫描网格见 src/config.py 的 SCAN_GRID，可扩大后重跑 `python -m src.scan`。")
