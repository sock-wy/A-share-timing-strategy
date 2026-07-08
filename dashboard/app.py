# -*- coding: utf-8 -*-
"""
Streamlit 面板（骨架，可运行）
==============================
下拉选择已实现的子策略，查看净值图 + 逐笔交易 + 指标对照。
运行：  streamlit run dashboard/app.py

随着更多子策略实现，只需在 IMPLEMENTED 里登记 (显示名, 模块路径) 即可自动出现在面板。
"""
import sys
import importlib.util
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loader import load_index          # noqa: E402
from src.backtest import run_backtest            # noqa: E402
from src.plotting import build_report            # noqa: E402
from src.config import REPORT_PERF               # noqa: E402

# 已实现子策略登记：显示名 -> strategy.py 路径（08 大小单缺数据，未登记）
IMPLEMENTED = {
    "01 宏观流动性": ROOT / "strategies" / "01_宏观流动性" / "strategy.py",
    "02 信贷预期": ROOT / "strategies" / "02_信贷预期" / "strategy.py",
    "03 中美汇率": ROOT / "strategies" / "03_中美汇率" / "strategy.py",
    "04 中美利差": ROOT / "strategies" / "04_中美利差" / "strategy.py",
    "05 期货基差": ROOT / "strategies" / "05_期货基差" / "strategy.py",
    "06 期权PCR": ROOT / "strategies" / "06_期权PCR" / "strategy.py",
    "07 融资融券": ROOT / "strategies" / "07_融资融券" / "strategy.py",
    "09 筹码结构": ROOT / "strategies" / "09_筹码结构" / "strategy.py",
    "10 长端动量": ROOT / "strategies" / "10_长端动量" / "strategy.py",
}


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.parent.name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


st.set_page_config(page_title="A股择时多策略面板", layout="wide")
st.title("A股权益择时 · 多策略回测面板")

choice = st.sidebar.selectbox("选择子策略", list(IMPLEMENTED.keys()))
mod = _load_module(IMPLEMENTED[choice])
result = run_backtest(load_index("中证800"), mod.build_signal(), name=mod.NAME)

m = result["metrics"]
rep = REPORT_PERF.get(mod.REPORT_KEY, {})
c1, c2, c3, c4 = st.columns(4)
c1.metric("年化收益率", f"{m['年化收益率']*100:.2f}%", f"研报 {rep.get('年化收益率',0)*100:.2f}%")
c2.metric("最大回撤", f"{m['最大回撤']*100:.2f}%", f"研报 {rep.get('最大回撤',0)*100:.2f}%")
c3.metric("年化IR", f"{m['年化IR']:.2f}", f"研报 {rep.get('年化IR',0):.2f}")
c4.metric("信号次数", f"{m['信号次数']}", f"研报 {rep.get('信号次数','-')}")

wk = result["weekly"]
st.line_chart(wk[["strat_nav", "bench_nav", "excess_nav"]])
st.subheader("逐笔交易明细")
st.dataframe(result["trades"], use_container_width=True)
