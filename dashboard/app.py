# -*- coding: utf-8 -*-
"""
A股权益择时 · 多策略回测面板（全中文）
======================================
运行：  streamlit run dashboard/app.py

· 全策略汇总页：各子策略用「组1」参数复现 vs 研报 + 可编辑「备注」笔记
  （09/10 若开启「用进阶汇总」，汇总改用其进阶版「进阶组1」参数）
· 单策略页：研报原文 + 参数数字框(±步进) + 3 组参数存档 + 净值/指标/逐笔交易
· 09/10 另有【进阶版】：一键跳转，顶部写清进阶版建仓/平仓逻辑，独立 3 组参数存档，
  可一键「用这套参数做汇总」（否则汇总仍用原版组1）。
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
                        REPORT_RESULT_TEXT, REPORT_METHOD_TEXT, MA_KIND_STRATEGIES,
                        MATH_EXPLAIN, ADVANCED)

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


# ---------------- 参数组存档：strategies/<folder>/我的参数组.json ----------------
def group_file(folder):
    return ROOT / "strategies" / folder / "我的参数组.json"


def load_groups(folder):
    f = group_file(folder)
    return json.load(open(f, encoding="utf-8")) if f.exists() else {}


def write_groups(folder, data):
    json.dump(data, open(group_file(folder), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


@st.cache_resource
def get_module(folder, filename="策略.py"):
    return load_strategy(folder, filename)


@st.cache_data(show_spinner=False)
def compute(folder, params_items, confirm=1, start=None, end=None, filename="策略.py"):
    """跑一次回测。params_items=None 用默认参数；否则用传入参数（元组化以便缓存）。"""
    mod = get_module(folder, filename)
    params = dict(params_items) if params_items else None
    res = run_backtest(load_index("中证800"), mod.build_signal(params),
                       name=mod.NAME, confirm_weeks=confirm, start=start, end=end)
    return res["metrics"], res["weekly"], res["trades"], mod.NAME, mod.REPORT_KEY


def compute_group1(folder):
    """全策略汇总用的复现：
    · 09/10 且开启「用进阶汇总」 -> 用其进阶版「进阶组1」参数；
    · 否则 -> 用原版「组1」（无则默认参数）。
    """
    data = load_groups(folder)
    adv = ADVANCED.get(folder)
    if adv and data.get("用进阶汇总"):
        g = data.get("进阶组1", {}) or {}
        confirm = int(g.get("confirm_weeks", 1))
        params = {k: v for k, v in g.items() if k != "confirm_weeks"}
        items = tuple(sorted(params.items())) if params else None
        return compute(folder, items, confirm, filename=adv["file"])
    g = data.get("组1")
    if g:
        confirm = int(g.get("confirm_weeks", 1))
        params = {k: v for k, v in g.items() if k != "confirm_weeks"}
        return compute(folder, tuple(sorted(params.items())), confirm)
    return compute(folder, None)


st.set_page_config(page_title="A股择时多策略面板", layout="wide")
st.title("A股权益择时 · 多策略回测面板")

# ---------------- 侧边栏导航：六大维度手风琴 ----------------
if "view" not in st.session_state:
    st.session_state.view = ("strategy", "宏观流动性", "01_宏观流动性")

st.sidebar.title("导航")
if st.sidebar.button("📊 全策略汇总", use_container_width=True,
                     type="primary" if st.session_state.view[0] == "summary" else "secondary"):
    st.session_state.view = ("summary",)
    st.rerun()

st.sidebar.markdown("**研报六大维度**（点开选子策略）")
_cur = st.session_state.view[2] if st.session_state.view[0] in ("strategy", "advanced") else None
for _cat, _subs in CATEGORIES.items():
    with st.sidebar.expander(_cat, expanded=any(f == _cur for _, f in _subs)):
        for _sname, _folder in _subs:
            if st.button(_sname, key=f"nav_{_folder}", use_container_width=True,
                         type="primary" if _folder == _cur else "secondary"):
                st.session_state.view = ("strategy", _sname, _folder)
                st.rerun()
            if _folder in ADVANCED:  # 09/10 侧边栏直达进阶版
                if st.button(f"   └ 🚀 {ADVANCED[_folder]['name']}", key=f"navadv_{_folder}",
                             use_container_width=True):
                    st.session_state.view = ("advanced", ADVANCED[_folder]["name"], _folder)
                    st.rerun()

VIEW = st.session_state.view


# ============================================================ 单策略渲染（原版/进阶版共用）
def render_strategy(folder, filename, is_advanced):
    mod = get_module(folder, filename)
    name, rkey = mod.NAME, mod.REPORT_KEY
    rep = REPORT_PERF.get(rkey, {})
    space = PARAM_SPACE.get(name, {})
    defaults = PARAMS.get(name, {})
    kpre = f"{folder}@adv" if is_advanced else folder      # session_state 键前缀（原版/进阶不冲突）
    gpre = "进阶" if is_advanced else ""                    # 参数组名前缀：组1 / 进阶组1
    scan_file = ROOT / "strategies" / folder / ("扫描摘要_进阶.json" if is_advanced else "扫描摘要.json")
    scan_data = json.load(open(scan_file, encoding="utf-8")) if scan_file.exists() else {}
    recovered_file = None if is_advanced else ROOT / "strategies" / folder / "复原参数.json"
    groups = load_groups(folder)
    g1 = groups.get(f"{gpre}组1", {})

    st.subheader(name + ("　🚀进阶版" if is_advanced else ""))
    st.markdown("**📄 " + ("本进阶版·建仓/平仓逻辑" if is_advanced else "研报原文·策略定义与建仓/平仓逻辑") + "**")
    st.info(REPORT_METHOD_TEXT.get(name, "（研报未单列该子策略方法）"))
    if name in MATH_EXPLAIN:
        with st.expander("📐 数学逻辑解释（点开）"):
            st.markdown(MATH_EXPLAIN[name])

    # ---------------- 载入按钮 ----------------
    slot_label = "进阶组" if is_advanced else "组"
    st.markdown(f"**参数存档**：3 组可保存/载入你调好的参数"
                + ("（**进阶组1** 供“用于汇总”使用）" if is_advanced else "（**组1** 会用于全策略汇总）"))
    lc = st.columns(5)
    for i in range(3):
        slot = f"{gpre}组{i+1}"
        if lc[i].button(f"📂 载入{slot_label}{i+1}", key=f"load{i}_{kpre}", disabled=slot not in groups,
                        use_container_width=True):
            for pn, v in groups[slot].items():
                sk = f"{kpre}_confirm" if pn == "confirm_weeks" else f"{kpre}_{pn}"
                st.session_state[sk] = int(v) if pn == "confirm_weeks" else v
            st.rerun()
    if recovered_file is not None and recovered_file.exists() and \
            lc[3].button("📂 载入复原参数", key=f"loadrec_{kpre}", use_container_width=True):
        for pn, v in json.load(open(recovered_file, encoding="utf-8")).items():
            st.session_state[f"{kpre}_{pn}"] = v
        st.rerun()
    if "综合最相似" in scan_data and lc[4].button("🎯 载入最相似", key=f"loadsim_{kpre}",
                                                use_container_width=True):
        for pn, v in scan_data["综合最相似"]["参数"].items():
            st.session_state[f"{kpre}_{pn}"] = v
        st.rerun()
    if "综合最相似" in scan_data:
        st.caption("最相似 = 在参数网格上，使各指标相对偏差 |复现−研报|/|研报| 的加权平均最小的一组"
                   "（年化收益率、最大回撤 权重×2，信号次数/次均天数/次胜率/次赔率 各×1）。")

    # ---------------- 参数（数字框 + 加减号）----------------
    st.markdown("**参数**（数字框旁 −/＋ 按步长增减，也可直接输入；实时重算净值 / 指标 / 逐笔交易）")
    cols = st.columns(max(1, len(space)))
    params = {}
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

    if name in MA_KIND_STRATEGIES:
        mk = f"{kpre}_ma_kind"
        if mk not in st.session_state:
            st.session_state[mk] = g1.get("ma_kind", "SMA")
        params["ma_kind"] = st.radio(
            "均线类型（信号定义不变：仍是长短均线差→方向；EMA 滞后更小、更灵敏）",
            ["SMA", "EMA"], horizontal=True, key=mk)
    st.caption(f"当前参数：{params}")

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

    # ---------------- 保存按钮 ----------------
    sc = st.columns(3)
    for i in range(3):
        slot = f"{gpre}组{i+1}"
        if sc[i].button(f"💾 存为{slot_label}{i+1}", key=f"save{i}_{kpre}", use_container_width=True):
            g = dict(params)
            g["confirm_weeks"] = int(confirm)
            data = load_groups(folder)
            data[slot] = g
            write_groups(folder, data)
            st.success(f"已保存到 {slot}：{g}")

    # ---------------- 进阶版：用于全策略汇总的开关 ----------------
    if is_advanced:
        data = load_groups(folder)
        using = bool(data.get("用进阶汇总", False))
        st.markdown("**🔖 用于全策略汇总**（开启后，汇总页该策略改用本进阶版参数；否则用原版组1）")
        tc = st.columns([2, 2, 3])
        if tc[0].button("📌 用这套参数做汇总", key=f"useadv_{kpre}", use_container_width=True,
                        type="primary"):
            g = dict(params)
            g["confirm_weeks"] = int(confirm)
            d = load_groups(folder)
            d["进阶组1"] = g
            d["用进阶汇总"] = True
            write_groups(folder, d)
            st.success("已设为汇总用：进阶版（存入进阶组1）")
            st.rerun()
        if tc[1].button("↩️ 汇总改回原版组1", key=f"useorig_{kpre}", use_container_width=True):
            d = load_groups(folder)
            d["用进阶汇总"] = False
            write_groups(folder, d)
            st.info("汇总已改回原版组1")
            st.rerun()
        tc[2].caption(f"当前全策略汇总使用：{'✅ 进阶版（进阶组1）' if using else '原版组1'}")

    # —— 指标实际分布统计 ——
    if hasattr(mod, "indicator"):
        ind = mod.indicator(params).loc[start:end].dropna()
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
                                  start, end, filename)
    st.plotly_chart(nav_figure({"weekly": wk, "name": f"{name}（当前参数）"}),
                    use_container_width=True)

    # —— 绩效指标 ——
    st.markdown("**绩效指标（当前参数复现 vs 研报）**")
    tbl = pd.DataFrame({
        "指标": METRIC_ORDER,
        "复现": [fmt(k, m.get(k)) for k in METRIC_ORDER],
        "研报": [fmt(k, rep.get(k)) for k in METRIC_ORDER],
    })
    st.dataframe(tbl, use_container_width=True, hide_index=True)
    st.caption("研报列为全区间数值；拖动上方时间段只改变「复现」列，用于样本内/外对比。"
               + ("　进阶版仍与研报“" + rkey + "”原始绩效对照。" if is_advanced else ""))

    # —— 逐笔交易明细 ——
    st.markdown("**逐笔交易明细（当前参数，每改一次参数即刷新）**")
    st.dataframe(trades, use_container_width=True, hide_index=True)

    # —— 研报原文·结果描述 ——
    st.markdown("---")
    st.markdown("**📄 研报原文·结果描述**")
    st.info(REPORT_RESULT_TEXT.get(rkey, "（研报未单列该子策略结果）"))


# ============================================================ 全策略汇总
if VIEW[0] == "summary":
    st.subheader("全策略汇总：各策略「组1」参数复现 vs 研报")
    rows = []
    for disp, folder in STRATS.items():
        data = load_groups(folder)
        use_adv = ADVANCED.get(folder) and data.get("用进阶汇总")
        m, *_, rkey = compute_group1(folder)
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
        key="summary_editor")
    for _, r in edited.iterrows():
        folder = STRATS[r["子策略"].replace("　🚀进阶", "")]
        note = r["备注"] or ""
        data = load_groups(folder)
        if data.get("备注", "") != note:
            data["备注"] = note
            write_groups(folder, data)
    st.caption("复现列使用各子策略「组1」参数（未保存组1则用默认参数）；09/10 若开启「用进阶汇总」"
               "则用其进阶版「进阶组1」（带🚀进阶标记）。「备注」列可直接编辑，自动保存。调参请点左侧子策略。")

# ============================================================ 进阶版详情
elif VIEW[0] == "advanced":
    folder = VIEW[2]
    adv = ADVANCED[folder]
    top = st.columns([1, 4])
    if top[0].button("↩️ 返回原版", key=f"back_{folder}", use_container_width=True):
        _oname = next((s for s, f in [(s, f) for subs in CATEGORIES.values() for s, f in subs]
                       if f == folder), folder)
        st.session_state.view = ("strategy", _oname, folder)
        st.rerun()
    top[1].caption("你正在查看【进阶版】。原版保留不变；本页参数存档（进阶组1/2/3）与原版互不影响。")
    render_strategy(folder, adv["file"], is_advanced=True)

# ============================================================ 单策略详情（原版）
else:
    folder = VIEW[2]
    if folder == "08_大小单资金":
        st.warning("「大小单资金」子策略缺“超大单主动净流入”数据，暂未实现（占位）。")
        st.stop()

    if folder in ADVANCED:  # 09/10 顶部一键跳转进阶版
        adv = ADVANCED[folder]
        jc = st.columns([2, 3])
        if jc[0].button(f"🚀 打开进阶版：{adv['name']}", key=f"toadv_{folder}",
                        use_container_width=True, type="primary"):
            st.session_state.view = ("advanced", adv["name"], folder)
            st.rerun()
        jc[1].caption("进阶版 = 另一套建仓/平仓逻辑（原版保留）。09=÷成交额重构，10=风险调整动量。"
                      "进阶版可单独存参数、并选择是否用于全策略汇总。")

    render_strategy(folder, "策略.py", is_advanced=False)
