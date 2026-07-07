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


def build_signal():
    p = PARAMS[NAME]
    df = load_long_term_loan().set_index("date")
    balance = df["value"]
    yoy = balance / balance.shift(p["yoy_window"]) - 1          # 同比（剔除季节效应）
    direction = ma_diff(yoy, p["short_ma"], p["long_ma"])       # 长短均线差：信用扩张方向
    signal = sign_signal(direction, positive_is_long=True)      # 正->做多，负->空仓
    signal.name = "signal"
    return signal
