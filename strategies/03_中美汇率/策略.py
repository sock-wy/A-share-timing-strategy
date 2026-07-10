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


def build_signal(params=None):
    p = params or PARAMS[NAME]
    s = load_usdcnh().set_index("date")["close"]
    # 信号定义不变：仍是长短均线差 -> 方向；仅均线类型可选 SMA/EMA（默认 SMA）
    direction = ma_diff(s, p["short_ma"], p["long_ma"], kind=p.get("ma_kind", "SMA"))
    # 均线差<0 表示汇率下行/人民币升值 -> 做多，故 positive_is_long=False
    signal = sign_signal(direction, positive_is_long=False)
    signal.name = "signal"
    return signal
