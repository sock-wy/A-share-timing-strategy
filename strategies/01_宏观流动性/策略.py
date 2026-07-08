# -*- coding: utf-8 -*-
"""
01 宏观流动性 —— 信号构造
=========================
净投放(月度) -> 平滑 -> 滚动Zscore -> 阈值 p 三态信号（>p:1, <-p:-1, 中间延续）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_macro_liquidity
from src.signal_utils import rolling_zscore, threshold_signal
from src.config import PARAMS

NAME = "宏观流动性"
REPORT_KEY = "宏观流动性"


def build_signal(params=None):
    p = params or PARAMS[NAME]
    df = load_macro_liquidity().set_index("date")
    net = df["net_injection"]                                   # 4工具净投放加总（月度）
    smoothed = net.rolling(p["smooth_window"], min_periods=1).mean()   # 平滑
    strength = rolling_zscore(smoothed, p["zscore_window"])            # 流动性供给强度
    signal = threshold_signal(strength, p["p"])                       # 三态阈值信号
    signal.name = "signal"
    return signal
