# -*- coding: utf-8 -*-
"""
03 中美汇率 —— 信号构造
=======================
USDCNH(日度) -> 长短均线差 -> 汇率下行(升值)做多、上行(贬值)空仓。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_usdcnh
from src.signal_utils import ma_diff, sign_signal
from src.config import PARAMS

NAME = "中美汇率"
REPORT_KEY = "中美汇率"


def indicator(params=None):
    """原始择时指标：长短均线差（短均线 - 长均线）。索引为 date，供阈值/统计使用。"""
    p = params or PARAMS[NAME]
    s = load_usdcnh().set_index("date")["close"]
    return ma_diff(s, p["short_ma"], p["long_ma"], kind=p.get("ma_kind", "SMA"))


def build_signal(params=None):
    p = params or PARAMS[NAME]
    # 均线差与阈值比较：ma_diff < threshold（汇率更明确下行/升值）-> 做多；> threshold -> 空仓。
    # threshold 默认 0（即原始“跟0比”的口径），可正可负。
    direction = indicator(params) - p.get("threshold", 0.0)
    # direction<0 表示均线差低于阈值 -> 做多，故 positive_is_long=False
    signal = sign_signal(direction, positive_is_long=False)
    signal.name = "signal"
    return signal
