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


def _apply_debounce(long_raw, confirm):
    """信号去抖（双向状态机）：原始信号连续 confirm 周同向，才切换仓位。

    · 空仓时，做多信号连续 ≥confirm 周 -> 建仓；
    · 满仓时，空仓信号连续 ≥confirm 周 -> 平仓；
    · 否则保持当前仓位。
    过滤掉单周信号毛刺（双向），confirm<=1 时原样返回（不去抖）。因果、无未来函数。

    long_raw : 0/1 数组（1=当周信号做多）；返回去抖后的 0/1 仓位意向数组。
    """
    long_raw = np.asarray(long_raw, dtype=int)
    n = len(long_raw)
    if confirm <= 1 or n == 0:
        return long_raw.astype(float)
    out = np.zeros(n)
    state, run, prev = 0, 0, None
    for t in range(n):
        v = long_raw[t]
        run = run + 1 if v == prev else 1          # 当前值已连续 run 周
        prev = v
        if v == 1 and state == 0 and run >= confirm:
            state = 1                              # 做多确认 -> 建仓
        elif v == 0 and state == 1 and run >= confirm:
            state = 0                              # 空仓确认 -> 平仓
        out[t] = state
    return out


def run_backtest(index_df: pd.DataFrame, signal: pd.Series, name: str = "策略",
                 confirm_weeks: int = 1, start: str = None, end: str = None) -> dict:
    """执行一个子策略的周度回测。

    index_df      : 基准指数日线（需含 date, close）
    signal        : 索引为 date 的信号序列（原始频率即可），>0 视为做多
    confirm_weeks : 信号确认周数（去抖）；1=不去抖；>1 时信号需连续该周数同向才切换仓位
    start, end    : 回测区间（默认全区间；用于样本内/外测试）
    返回 dict：weekly(周度明细), trades(逐笔), metrics(研报指标), name
    """
    rule = BACKTEST["rebalance"]
    wk = _to_weekly(index_df, rule)

    # —— 信号对齐到每周实际最后交易日（ffill，防未来函数）——
    sig = signal.dropna().sort_index()
    aligned = sig.reindex(pd.to_datetime(wk["trade_date"].values), method="ffill")
    aligned.index = wk.index
    wk["signal"] = aligned.values

    # —— 仓位：信号>0做多；先对周信号去抖，再平移一周持有 ——
    long_raw = (wk["signal"] > 0).astype(int).values
    debounced = _apply_debounce(long_raw, int(confirm_weeks))
    wk["position"] = pd.Series(debounced, index=wk.index).shift(1).fillna(0)

    # —— 区间裁剪（可自定义样本内/外区间）——
    wk = wk.loc[start or BACKTEST["start"]: end or BACKTEST["end"]].copy()

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
