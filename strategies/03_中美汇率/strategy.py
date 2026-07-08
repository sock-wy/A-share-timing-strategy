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


def build_signal():
    p = PARAMS[NAME]
    s = load_usdcnh().set_index("date")["close"]
    direction = ma_diff(s, p["short_ma"], p["long_ma"])        # 汇率长短均线差
    # 均线差<0 表示汇率下行/人民币升值 -> 做多，故 positive_is_long=False
    signal = sign_signal(direction, positive_is_long=False)
    signal.name = "signal"
    return signal
