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


def build_signal():
    p = PARAMS[NAME]
    s = load_us_cn_spread().set_index("date")["spread"]
    direction = ma_diff(s, p["short_ma"], p["long_ma"])        # 利差长短均线差
    # 均线差>0 表示利差上行/人民币资产吸引力提升 -> 做多
    signal = sign_signal(direction, positive_is_long=True)
    signal.name = "signal"
    return signal
