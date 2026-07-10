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
LONG_BELOW = True   # 做多条件：均线差 < 阈值（PCR 下行/乐观）


def indicator(params=None):
    """原始择时指标：PCR 的长短均线差（短 - 长）。"""
    p = params or PARAMS[NAME]
    s = load_pcr().set_index("date")["pcr"]
    return ma_diff(s, p["short_ma"], p["long_ma"], kind=p.get("ma_kind", "SMA"))


def build_signal(params=None):
    p = params or PARAMS[NAME]
    # 均线差 < threshold（PCR 更明确下行/乐观）-> 做多；> threshold -> 空仓。默认0=原口径。
    direction = indicator(params) - p.get("threshold", 0.0)
    signal = sign_signal(direction, positive_is_long=False)
    signal.name = "signal"
    return signal
