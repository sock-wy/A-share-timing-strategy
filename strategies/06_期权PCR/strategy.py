# -*- coding: utf-8 -*-
"""
06 期权PCR —— 信号构造
======================
50ETF期权 PCR=认沽/认购持仓(日度) -> 长短均线差 -> PCR下行做多、上行空仓。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data_loader import load_pcr
from src.signal_utils import ma_diff, sign_signal
from src.config import PARAMS

NAME = "期权PCR"
REPORT_KEY = "期权PCR"


def build_signal():
    p = PARAMS[NAME]
    s = load_pcr().set_index("date")["pcr"]
    direction = ma_diff(s, p["short_ma"], p["long_ma"])        # PCR长短均线差
    # 均线差<0 表示 PCR 下行(乐观) -> 做多，故 positive_is_long=False
    signal = sign_signal(direction, positive_is_long=False)
    signal.name = "signal"
    return signal
