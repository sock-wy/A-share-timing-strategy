# -*- coding: utf-8 -*-
"""
09 筹码结构 · 进阶版 —— 按“成交额”累积绝对筹码（÷成交额，非÷总分布）
====================================================================
【为什么做进阶版】
原版把每天的筹码按“占当日总分布的比例”注入并**除以总分布归一化**，尺度被抹平：
放量突破和缩量阴跌权重几乎一样，赚钱效应指标区分度差（综合距离 0.965，年化封顶 4-5%）。
研报原文写的是 **“阻力筹码 = 成本高于现价的筹码与成交额比值”**——分母是**成交额（绝对量）**，
不是总分布。进阶版据此重构：按当日**成交额**注入绝对筹码，再除以当日成交额，
把“量”的信息真正喂进信号。

【进阶版建仓 / 平仓逻辑（面板顶部展示）】
1. 逐日维护价格网格上的**绝对筹码量**分布：
       旧筹码按 (1−当日换手率) 衰减；新筹码 = **当日成交额**，注入到当日典型价(高+低+收)/3。
2. 阻力筹码强度 = (现价上方的套牢筹码量) / **当日成交额**；
   支撑筹码强度 = (现价下方的获利筹码量) / **当日成交额**。
   （÷成交额 ⇒ 放量日强度被压低、缩量滞涨/缩量抵抗被放大，含“量价背离”信息。）
3. 赚钱效应 = 现价 / 加权平均持仓成本 − 1（>0 市场盈利，<0 亏损）。
4. 对阻力/支撑强度各做滚动 Zscore，按阈值 p 出信号（带延续，降换手）：
       · 市场**盈利** 且 支撑强度Zscore > p → 建仓（做多）；
       · 市场**亏损** 且 阻力强度Zscore > p → 平仓（空仓）；
       · 未触发 → 延续前一状态。

直觉：普遍盈利且下方获利筹码放量堆积 ⇒ 低位有承接、易涨难跌；
普遍亏损且上方套牢筹码沉重 ⇒ 反弹即遇抛压。÷成交额让“放量/缩量”真正参与判断。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
from src.data_loader import load_index, load_turnover
from src.signal_utils import rolling_zscore
from src.config import PARAMS

NAME = "筹码结构进阶"
REPORT_KEY = "筹码结构"                        # 仍与研报“筹码结构”绩效对照
INDICATOR_NAME = "赚钱效应(现价/均成本−1)"     # 面板统计用：>0 市场盈利、<0 亏损


def _load_chip():
    idx = load_index("中证800")[["date", "high", "low", "close", "amount"]].set_index("date")
    tn = load_turnover("中证800").set_index("date")["turnover"]
    df = idx.join(tn, how="inner").dropna()
    res, sup, prof = _chip_distribution_abs(
        df["high"].values, df["low"].values, df["close"].values,
        (df["turnover"] / 100).values, df["amount"].values)
    return df, res, sup, prof


def indicator(params=None):
    """原始择时指标之一：赚钱效应（现价相对平均持仓成本的收益率）。"""
    df, res, sup, prof = _load_chip()
    return pd.Series(prof, index=df.index)


def _chip_distribution_abs(high, low, close, turn, amount):
    """按成交额累积【绝对筹码量】，阻力/支撑强度 = 对应筹码量 ÷ 当日成交额。"""
    typical = (high + low + close) / 3.0                       # 当日典型价=持仓成本
    n = len(close)
    pmin, pmax = typical.min() * 0.90, typical.max() * 1.10
    step = pmin * 0.005                                        # 价格网格步长≈0.5%
    grid = np.arange(pmin, pmax + step, step)
    dist = np.zeros(len(grid))                                 # 绝对筹码量（以成交额计）

    resistance = np.full(n, np.nan)
    support = np.full(n, np.nan)
    profit = np.full(n, np.nan)
    for t in range(n):
        tr = min(max(turn[t], 0.0), 1.0)                      # 当日换手率(分数)
        dist *= (1 - tr)                                       # 旧筹码换手衰减
        idx = min(int((typical[t] - pmin) / step), len(grid) - 1)
        dist[idx] += amount[t]                                # 新筹码按当日成交额注入
        s = dist.sum()
        amt = amount[t]
        if s <= 0 or amt <= 0:
            continue
        c = close[t]
        above = grid > c
        resistance[t] = dist[above].sum() / amt               # 阻力筹码 ÷ 成交额
        support[t] = dist[~above].sum() / amt                 # 支撑筹码 ÷ 成交额
        profit[t] = c / ((grid * dist).sum() / s) - 1         # 现价/加权平均成本-1
    return resistance, support, profit


def build_signal(params=None):
    p = params or PARAMS[NAME]
    df, res, sup, prof = _load_chip()

    res_z = rolling_zscore(pd.Series(res, index=df.index), p["zscore_window"])
    sup_z = rolling_zscore(pd.Series(sup, index=df.index), p["zscore_window"])
    prof = pd.Series(prof, index=df.index)

    raw = pd.Series(np.nan, index=df.index)
    raw[(prof > 0) & (sup_z > p["p"])] = 1                     # 盈利&支撑强 -> 做多
    raw[(prof < 0) & (res_z > p["p"])] = -1                    # 亏损&阻力强 -> 空仓
    signal = raw.ffill().fillna(0)
    signal.name = "signal"
    return signal
