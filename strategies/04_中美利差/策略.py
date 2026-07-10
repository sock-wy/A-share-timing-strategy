# -*- coding: utf-8 -*-
"""
04 中美利差 —— 信号构造
=======================
中美10Y国债利差(日度) -> 长短均线差 -> 利差上行做多、下行空仓。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_us_cn_spread
from src.signal_utils import ma_diff, sign_signal
from src.config import PARAMS

NAME = "中美利差"
REPORT_KEY = "中美利差"
LONG_BELOW = False   # 做多条件：均线差 > 阈值（利差上行）


def indicator(params=None):
    """原始择时指标：利差长短均线差（短均线 - 长均线）。索引为 date，供阈值/统计使用。"""
    p = params or PARAMS[NAME]
    s = load_us_cn_spread().set_index("date")["spread"]
    return ma_diff(s, p["short_ma"], p["long_ma"], kind=p.get("ma_kind", "SMA"))


def build_signal(params=None):
    p = params or PARAMS[NAME]
    # 均线差与阈值比较：ma_diff > threshold（利差更明确上行）-> 做多；< threshold -> 空仓。
    # threshold 默认 0（即原始“跟0比”口径），可正可负。
    direction = indicator(params) - p.get("threshold", 0.0)
    # direction>0 表示均线差高于阈值 -> 做多
    signal = sign_signal(direction, positive_is_long=True)
    signal.name = "signal"
    return signal
