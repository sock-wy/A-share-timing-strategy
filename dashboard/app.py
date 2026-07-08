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
from src.config import REPORT_PERF, PARAM_SPACE, PARAMS

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
def compute(folder, params_items):
    """跑一次回测。params_items=None 用默认参数；否则用传入参数（元组化以便缓存）。"""
    mod = get_module(folder)
    params = dict(params_items) if params_items else None
    res = run_backtest(load_index("中证800"), mod.build_signal(params), name=mod.NAME)
    return res["metrics"], res["weekly"], res["trades"], mod.NAME, mod.REPORT_KEY


st.set_page_config(page_title="A股择时多策略面板", layout="wide")
st.title("A股权益择时 · 多策略回测面板")

page = st.sidebar.radio("页面", ["全策略汇总", "单策略详情"])

# ============================================================ 全策略汇总
if page == "全策略汇总":
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
    st.caption("默认参数下的复现；调参请进「单策略详情 → 参数复原对比」。")

# ============================================================ 单策略详情
else:
    disp = st.sidebar.selectbox("选择子策略", list(STRATS.keys()))
    folder = STRATS[disp]
    mod = get_module(folder)
    name, rkey = mod.NAME, mod.REPORT_KEY
    rep = REPORT_PERF.get(rkey, {})

    tab1, tab2 = st.tabs(["基准表现", "参数复原对比"])

    # ---------------- 标签1：基准表现（默认参数）----------------
    with tab1:
        m, wk, trades, name, _ = compute(folder, None)
        st.plotly_chart(nav_figure({"weekly": wk, "name": name}), use_container_width=True)
        st.markdown("**绩效指标（复现 vs 研报）**")
        tbl = pd.DataFrame({
            "指标": METRIC_ORDER,
            "复现": [fmt(k, m.get(k)) for k in METRIC_ORDER],
            "研报": [fmt(k, rep.get(k)) for k in METRIC_ORDER],
        })
        st.dataframe(tbl, use_container_width=True, hide_index=True)
        st.markdown("**逐笔交易明细**")
        st.dataframe(trades, use_container_width=True, hide_index=True)

    # ---------------- 标签2：参数复原对比（旋钮实时）----------------
    with tab2:
        space = PARAM_SPACE.get(name, {})
        defaults = PARAMS.get(name, {})
        recovered_file = ROOT / "strategies" / folder / "复原参数.json"

        st.markdown("**参数旋钮**（拖动实时重算）")
        col_btn, _ = st.columns([1, 3])
        if recovered_file.exists() and col_btn.button("载入复原参数"):
            best = json.load(open(recovered_file, encoding="utf-8"))
            for pn, v in best.items():
                st.session_state[f"{folder}_{pn}"] = v
            st.rerun()

        cols = st.columns(max(1, len(space)))
        params = {}
        for (pn, (lo, hi, step)), c in zip(space.items(), cols):
            key = f"{folder}_{pn}"
            is_int = float(step).is_integer() and float(lo).is_integer()
            if key not in st.session_state:
                st.session_state[key] = defaults.get(pn, lo)
            if is_int:
                params[pn] = c.slider(pn, int(lo), int(hi), step=int(step), key=key)
            else:
                params[pn] = c.slider(pn, float(lo), float(hi), step=float(step), key=key)

        m2, wk2, trades2, _, _ = compute(folder, tuple(sorted(params.items())))
        st.plotly_chart(nav_figure({"weekly": wk2, "name": f"{name}（当前参数）"}),
                        use_container_width=True)

        st.markdown("**特征指标：当前参数 vs 研报**")
        feat = ["年化收益率", "年化IR", "最大回撤", "信号次数"]
        c1, c2, c3, c4 = st.columns(4)
        for k, c in zip(feat, [c1, c2, c3, c4]):
            c.metric(k, fmt(k, m2.get(k)), f"研报 {fmt(k, rep.get(k))}", delta_color="off")
        st.caption(f"当前参数：{params}")
