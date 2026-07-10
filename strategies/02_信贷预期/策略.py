# -*- coding: utf-8 -*-
"""
02 信贷预期 —— 信号构造
=======================
中长期贷款余额(日度) -> 同比(剔季) -> 长短均线差 -> 双态信号（正:1, 负:-1）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_long_term_loan
from src.signal_utils import ma_diff, sign_signal
from src.config import PARAMS

NAME = "信贷预期"
REPORT_KEY = "信贷预期"
LONG_BELOW = False   # 做多条件：均线差 > 阈值（信用扩张方向为正）


def indicator(params=None):
    """原始择时指标：信用扩张方向 = 中长期贷款同比 的长短均线差（短 - 长）。"""
    p = params or PARAMS[NAME]
    balance = load_long_term_loan().set_index("date")["value"]
    yoy = balance / balance.shift(p["yoy_window"]) - 1          # 同比（剔除季节效应）
    return ma_diff(yoy, p["short_ma"], p["long_ma"], kind=p.get("ma_kind", "SMA"))


def build_signal(params=None):
    p = params or PARAMS[NAME]
    # 均线差 > threshold（信用扩张更明确为正）-> 做多；< threshold -> 空仓。默认0=原口径。
    direction = indicator(params) - p.get("threshold", 0.0)
    signal = sign_signal(direction, positive_is_long=True)
    signal.name = "signal"
    return signal
