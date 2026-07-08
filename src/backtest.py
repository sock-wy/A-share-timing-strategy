# -*- coding: utf-8 -*-
"""
周度回测引擎
============
研报统一口径：周度调仓（每周最后一个交易日收盘价），信号>0满仓做多基准、<=0空仓。

关键防未来函数处理：
  · 指标/信号在各自原始频率（月/日）算好，索引为 date；
  · 对齐到“每周实际最后一个交易日”时用 ffill（只用截至周五收盘可获得的信息）；
  · 本周五确定的信号，用于持有【下一周】——position 相对 signal 平移一周。
"""
import numpy as np
import pandas as pd
from . import metrics as M
from .config import BACKTEST


def _to_weekly(index_df: pd.DataFrame, rule: str):
    """把基准日线重采样成周度：每周最后一个交易日的收盘价与真实交易日期。"""
    idx = index_df.set_index("date").sort_index()
    close = idx["close"].resample(rule).last().dropna()
    trade_date = idx.index.to_series().resample(rule).last().reindex(close.index)
    wk = pd.DataFrame({"close": close, "trade_date": trade_date})
    wk["ret"] = wk["close"].pct_change()
    return wk


def extract_trades(wk: pd.DataFrame) -> pd.DataFrame:
    """抽取逐笔做多交易：position==1 的连续周区间，每段一笔。

    进场 = 建仓那一周（信号确定的上一周五）；出场 = 本段最后一个持仓周五。
    因此持有整整一周的交易 = 7 天（不会出现“0 天”的标注假象）。
    trade_return = 出场收盘 / 进场收盘 − 1。
    """
    pos = wk["position"].values
    trades, i, n = [], 0, len(wk)
    while i < n:
        if pos[i] == 1:
            j = i
            while j + 1 < n and pos[j + 1] == 1:
                j += 1
            seg = wk.iloc[i:j + 1]
            entry = wk.iloc[max(i - 1, 0)]              # 建仓周（上一周五）
            exit_ = wk.iloc[j]                          # 平仓周（本段末周五）
            entry_d = pd.Timestamp(entry["trade_date"])
            exit_d = pd.Timestamp(exit_["trade_date"])
            trade_ret = (1 + seg["ret"]).prod() - 1     # 持有期基准累计收益
            trades.append({
                "序号": len(trades) + 1,
                "进场日期": entry_d.date(),
                "出场日期": exit_d.date(),
                "持仓周数": len(seg),
                "holding_days": (exit_d - entry_d).days,
                "进场价": round(entry["close"], 2),
                "出场价": round(exit_["close"], 2),
                "trade_return": trade_ret,
                "盈亏": "盈" if trade_ret > 0 else "亏",
            })
            i = j + 1
        else:
            i += 1
    return pd.DataFrame(trades)


def run_backtest(index_df: pd.DataFrame, signal: pd.Series, name: str = "策略") -> dict:
    """执行一个子策略的周度回测。

    index_df : 基准指数日线（需含 date, close）
    signal   : 索引为 date 的信号序列（原始频率即可），>0 视为做多
    返回 dict：weekly(周度明细), trades(逐笔), metrics(研报指标), name
    """
    rule = BACKTEST["rebalance"]
    wk = _to_weekly(index_df, rule)

    # —— 信号对齐到每周实际最后交易日（ffill，防未来函数）——
    sig = signal.dropna().sort_index()
    aligned = sig.reindex(pd.to_datetime(wk["trade_date"].values), method="ffill")
    aligned.index = wk.index
    wk["signal"] = aligned.values

    # —— 仓位：信号>0满仓(1)、<=0空仓(0)；本周信号持有下周 ——
    wk["position"] = (wk["signal"] > 0).astype(float).shift(1).fillna(0)

    # —— 区间裁剪 ——
    wk = wk.loc[BACKTEST["start"]: BACKTEST["end"]].copy()

    # —— 净值 ——
    wk["strat_ret"] = wk["position"] * wk["ret"]
    wk["excess_ret"] = wk["strat_ret"] - wk["ret"]        # 相对基准超额
    wk["strat_nav"] = (1 + wk["strat_ret"].fillna(0)).cumprod()
    wk["bench_nav"] = (1 + wk["ret"].fillna(0)).cumprod()
    wk["excess_nav"] = (1 + wk["excess_ret"].fillna(0)).cumprod()

    trades = extract_trades(wk)
    m = M.compute_metrics(wk["strat_ret"].fillna(0), wk["strat_nav"], trades,
                          weeks_per_year=BACKTEST["weeks_per_year"])
    return {"name": name, "weekly": wk, "trades": trades, "metrics": m}
