# -*- coding: utf-8 -*-
"""
绩效指标模块
============
复现研报绩效表（表1-表10）中的全部指标：
    年化收益率、年化波动率、年化IR、最大回撤、Calmar比率、
    周胜率、周赔率、信号次胜率、信号次赔率、次均天数、信号次数

口径说明（对照研报数字反推）：
  · 年化IR   = 年化收益率 / 年化波动率           （宏观流动性 11.4%/15.6%=0.73 ✓）
  · Calmar   = 年化收益率 / 最大回撤             （11.4%/21.37%=0.53 ✓）
  · 周胜率   = 策略周收益>0 的周数占比
  · 周赔率   = 平均盈利周收益 / |平均亏损周收益|
  · 信号次数 = 做多信号触发次数（连续做多区间的个数）
  · 次胜率   = 做多区间内基准录得正收益的比例
  · 次赔率   = 平均盈利做多区间收益 / |平均亏损做多区间收益|
  · 次均天数 = 平均每个做多区间的持仓自然日
"""
import numpy as np
import pandas as pd


def annualized_return(nav: pd.Series, periods_per_year: int) -> float:
    """按周期数几何年化。"""
    n = len(nav) - 1
    if n <= 0:
        return np.nan
    total = nav.iloc[-1] / nav.iloc[0]
    return total ** (periods_per_year / n) - 1


def max_drawdown(nav: pd.Series) -> float:
    """最大回撤（正数表示回撤幅度）。"""
    roll_max = nav.cummax()
    dd = nav / roll_max - 1
    return -dd.min()


def compute_metrics(weekly_ret: pd.Series, nav: pd.Series, trades: pd.DataFrame,
                    weeks_per_year: int = 52) -> dict:
    """综合计算研报全部指标。

    weekly_ret : 策略周收益序列
    nav        : 策略净值序列
    trades     : extract_trades() 返回的逐笔做多交易表
    """
    ann_ret = annualized_return(nav, weeks_per_year)
    ann_vol = weekly_ret.std() * np.sqrt(weeks_per_year)
    mdd = max_drawdown(nav)

    # 周度盈亏（仅统计有持仓的周，空仓周收益为0不计入胜率分母更贴近研报，
    # 但研报口径未明确；这里统计所有非零周收益）
    nz = weekly_ret[weekly_ret != 0]
    win = nz[nz > 0]
    loss = nz[nz < 0]
    weekly_win = len(win) / len(nz) if len(nz) else np.nan
    weekly_odds = (win.mean() / abs(loss.mean())) if len(loss) and len(win) else np.nan

    # 逐笔（做多区间）盈亏
    if len(trades):
        tw = trades[trades["trade_return"] > 0]["trade_return"]
        tl = trades[trades["trade_return"] < 0]["trade_return"]
        sig_win = len(tw) / len(trades)
        sig_odds = (tw.mean() / abs(tl.mean())) if len(tl) and len(tw) else np.nan
        avg_days = trades["holding_days"].mean()
        n_signals = len(trades)
    else:
        sig_win = sig_odds = avg_days = np.nan
        n_signals = 0

    return {
        "年化收益率": ann_ret,
        "年化波动率": ann_vol,
        "年化IR": ann_ret / ann_vol if ann_vol else np.nan,
        "最大回撤": mdd,
        "Calmar比率": ann_ret / mdd if mdd else np.nan,
        "周胜率": weekly_win,
        "周赔率": weekly_odds,
        "信号次胜率": sig_win,
        "信号次赔率": sig_odds,
        "次均天数": avg_days,
        "信号次数": n_signals,
    }


def yearly_returns(weekly_ret: pd.Series, bench_weekly_ret: pd.Series) -> pd.DataFrame:
    """分年度表现（对应研报表14/表16）：择时策略 / 基准 / 超额。"""
    df = pd.DataFrame({"strat": weekly_ret, "bench": bench_weekly_ret})
    rows = []
    for yr, g in df.groupby(df.index.year):
        s = (1 + g["strat"]).prod() - 1
        b = (1 + g["bench"]).prod() - 1
        rows.append({"年份": yr, "择时策略": s, "中证800": b, "策略超额": s - b})
    return pd.DataFrame(rows).set_index("年份")
