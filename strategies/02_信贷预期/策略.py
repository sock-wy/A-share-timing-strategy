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
from src.signal_utils import sign_signal
from src.config import PARAMS

NAME = "信贷预期"
REPORT_KEY = "信贷预期"
LONG_BELOW = False   # 做多条件：均线差 > 阈值（信用扩张方向为正）


def _ma_diff_full(s, short, long, kind="SMA"):
    """严格满窗长短均线差（短 - 长）：窗口未满不出值（min_periods=窗口），
    杜绝“只有几个点也当整窗均线算”的不满窗虚信号。

    仅信贷预期使用本地严格版；共享的 signal_utils.ma_diff 保持不变，
    故中美汇率/中美利差/期权PCR 等其它策略完全不受影响。
    """
    if kind == "EMA":
        return (s.ewm(span=short, adjust=False, min_periods=short).mean()
                - s.ewm(span=long, adjust=False, min_periods=long).mean())
    return (s.rolling(short, min_periods=short).mean()
            - s.rolling(long, min_periods=long).mean())


def indicator(params=None):
    """原始择时指标：信用扩张方向 = 中长期贷款同比 的长短均线差（短 - 长）。

    均线严格满窗（不满窗不出值），data_mode='插值'（Wind 日度插值）/
    '月度'（时点 PIT 阶梯，不插值、无未来函数）。
    """
    p = params or PARAMS[NAME]
    balance = load_long_term_loan(mode=p.get("data_mode", "插值")).set_index("date")["value"]
    yoy = balance / balance.shift(p["yoy_window"]) - 1          # 同比（剔除季节效应）
    return _ma_diff_full(yoy, p["short_ma"], p["long_ma"], kind=p.get("ma_kind", "SMA"))


def build_signal(params=None):
    p = params or PARAMS[NAME]
    # 均线差 > threshold（信用扩张更明确为正）-> 做多；< threshold -> 空仓。默认0=原口径。
    direction = indicator(params) - p.get("threshold", 0.0)
    signal = sign_signal(direction, positive_is_long=True)
    signal.name = "signal"
    return signal
