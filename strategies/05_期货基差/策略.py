# -*- coding: utf-8 -*-
"""
05 期货基差 —— 信号构造
=======================
IC基差率(日度) -> 均线偏离度(滚动Zscore，比 (x-MA)/MA 更稳健，基差常为负) ->
阈值 p 三态信号（向上偏离>p:做多, 向下偏离<-p:空仓, 中间延续）。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_ic_basis
from src.signal_utils import rolling_zscore, threshold_signal
from src.config import PARAMS

NAME = "期货基差"
REPORT_KEY = "期货基差"
INDICATOR_NAME = "基差偏离度(Zscore)"   # 面板统计用；p 作用在它上（|偏离度|>p 触发）


def indicator(params=None):
    """原始择时指标：基差率(可选平滑)的滚动 Zscore 偏离度。近似 N(0,1)。

    smooth_days>1 时先对基差率做 smooth_days 日均值平滑（抑制换月锯齿噪音），默认1=原始。
    """
    p = params or PARAMS[NAME]
    s = load_ic_basis().set_index("date")["basis_rate"]
    sd = int(p.get("smooth_days", 1))
    if sd > 1:
        s = s.rolling(sd, min_periods=1).mean()
    return rolling_zscore(s, p["ma_window"])


def build_signal(params=None):
    p = params or PARAMS[NAME]
    deviation = indicator(params)                             # 均线偏离度（标准化）
    signal = threshold_signal(deviation, p["p"])             # 向上偏离做多、向下偏离空仓
    signal.name = "signal"
    return signal
