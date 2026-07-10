# -*- coding: utf-8 -*-
"""
信号构造公共函数
================
研报里反复出现的三类信号构造方式，抽成公共函数供各子策略复用：
  1) 长短均线差         ma_diff_signal   —— 汇率/利差/PCR/信贷/大小单
  2) 滚动Zscore三态阈值 zscore_threshold_signal —— 宏观流动性/期货基差
  3) 均线偏离度         ma_deviation
"""
import numpy as np
import pandas as pd


def rolling_zscore(s: pd.Series, window: int) -> pd.Series:
    """滚动 Zscore：(x - 滚动均值) / 滚动标准差。"""
    mean = s.rolling(window, min_periods=max(2, window // 3)).mean()
    std = s.rolling(window, min_periods=max(2, window // 3)).std()
    return (s - mean) / std


def ma_deviation(s: pd.Series, window: int) -> pd.Series:
    """均线偏离度：(x - MA) / MA。用于期货基差偏离度。"""
    ma = s.rolling(window, min_periods=max(2, window // 3)).mean()
    return (s - ma) / ma


def ma_diff(s: pd.Series, short: int, long: int, kind: str = "SMA") -> pd.Series:
    """长短均线差：短均线 - 长均线。>0 表示上行动能。

    kind='SMA' 简单移动平均（等权）；'EMA' 指数移动平均（近端加权，滞后更小）。
    信号定义不变——仍是“长短均线差 → 方向”，只是均线类型可选。
    """
    if kind == "EMA":
        return s.ewm(span=short, adjust=False).mean() - s.ewm(span=long, adjust=False).mean()
    return s.rolling(short, min_periods=1).mean() - s.rolling(long, min_periods=1).mean()


def sign_signal(x: pd.Series, positive_is_long=True) -> pd.Series:
    """双态信号：x>0 -> ±1。positive_is_long=False 时方向反转（如汇率、PCR 下行做多）。"""
    sig = np.sign(x)
    sig = sig.replace(0, np.nan).ffill().fillna(0)
    return sig if positive_is_long else -sig


def threshold_signal(x: pd.Series, p: float) -> pd.Series:
    """三态阈值信号：x>p -> 1；x<-p -> -1；中间延续前信号（研报“延续前信号”口径）。"""
    raw = pd.Series(np.nan, index=x.index)
    raw[x > p] = 1
    raw[x < -p] = -1
    return raw.ffill().fillna(0)
