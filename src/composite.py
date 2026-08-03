# -*- coding: utf-8 -*-
"""
组合策略（合成模型）
====================
把多个子策略信号合成为一个综合择时信号，以中证800 为标的回测。研报第 7 节两种：

  1) 等权合成：各子策略信号等权平均 → 综合信号 > 0 满仓、≤0 空仓。
  2) 动态赋权：滚动 window 日约束优化，最小化 ‖|R_t| − Σ w_i·S_i·R_t‖²，
     s.t. lo ≤ w_i ≤ hi、Σ w_i = 1（研报 N=10 用 5%~15%，此处按 0.5/N ~ 1.5/N 泛化）。

成员在 config.COMPOSITE_MEMBERS；每个成员用其「组1」参数（无则默认参数）在中证800 上出信号。
预留成员(config.COMPOSITE_RESERVED)接口保留，后期把 folder 挪进 MEMBERS 即可接入。
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .config import ROOT, BACKTEST, COMPOSITE_MEMBERS
from .data_loader import load_index
from .runner import load_strategy, build_signal_for
from .backtest import run_backtest


def _group1_params(folder):
    """取该子策略「组1」参数（去掉 confirm_weeks）；无则 None（用默认参数）。"""
    f = ROOT / "strategies" / folder / "我的参数组.json"
    if f.exists():
        g = json.load(open(f, encoding="utf-8")).get("组1")
        if g:
            return {k: v for k, v in g.items() if k != "confirm_weeks"}
    return None


def member_signals(members=None, target=BACKTEST["benchmark"]):
    """各成员子策略的日频信号（对齐到标的交易日、ffill、缺失填0），返回 DataFrame。"""
    members = members or COMPOSITE_MEMBERS
    idx = load_index(target).set_index("date").sort_index().index
    cols = {}
    for name, folder in members:
        mod = load_strategy(folder)
        sig = build_signal_for(mod, _group1_params(folder), target)
        cols[name] = sig.dropna().sort_index().reindex(idx, method="ffill").fillna(0)
    return pd.DataFrame(cols, index=idx)


def member_strengths(members=None, target=BACKTEST["benchmark"]):
    """各成员的【连续强度】∈[-1,1]（+做多方向）：标准化各自指标 -> 自动定向 -> tanh 压缩。
    用于图19（近8周赋权信号）的连续曲线；不改变回测（回测仍用离散仓位）。
    无 indicator 或异常时回退为离散信号的 EWMA 平滑。"""
    members = members or COMPOSITE_MEMBERS
    idx = load_index(target).set_index("date").sort_index().index
    cols = {}
    for name, folder in members:
        mod = load_strategy(folder)
        params = _group1_params(folder)
        disc = build_signal_for(mod, params, target).reindex(idx, method="ffill").fillna(0)
        strength = None
        if hasattr(mod, "indicator"):
            try:
                cont = (mod.indicator(params, index_name=target)
                        if getattr(mod, "INDEX_DEPENDENT", False) else mod.indicator(params))
                cont = cont.astype(float)
                mu = cont.expanding(min_periods=12).mean()
                sd = cont.expanding(min_periods=12).std()
                z = ((cont - mu) / sd).reindex(idx, method="ffill")
                al = pd.concat([z, disc], axis=1).dropna()
                sgn = -1.0 if (len(al) > 30 and al.iloc[:, 0].corr(al.iloc[:, 1]) < 0) else 1.0
                strength = np.tanh(sgn * z * 0.9)
            except Exception:
                strength = None
        if strength is None:
            strength = disc.ewm(span=21, adjust=False).mean()
        cols[name] = strength.reindex(idx).fillna(0.0).clip(-1, 1)
    return pd.DataFrame(cols, index=idx)


def equal_signal(sigs):
    """等权综合信号 = 各子策略信号的等权平均。"""
    return sigs.mean(axis=1)


def dynamic_weights(sigs, bench_ret, window=120, reest_every=5, lo=None, hi=None):
    """滚动约束优化动态权重，返回 (综合信号, 权重历史 DataFrame)。"""
    names = list(sigs.columns)
    N = len(names)
    lo = 0.5 / N if lo is None else lo
    hi = 1.5 / N if hi is None else hi
    dates = sigs.index
    SR = sigs.mul(bench_ret, axis=0).values          # S_i * R_t
    y_all = bench_ret.abs().values                    # 最优解 |R_t|
    S = sigs.values

    w = np.full(N, 1.0 / N)
    cons = ({"type": "eq", "fun": lambda w: w.sum() - 1.0},)
    bnds = [(lo, hi)] * N
    W = np.empty((len(dates), N))
    for t in range(len(dates)):
        if t >= window and (t - window) % reest_every == 0:
            X = SR[t - window:t]                       # (window, N)
            y = y_all[t - window:t]
            res = minimize(lambda w: float(np.sum((X @ w - y) ** 2)), w,
                           method="SLSQP", bounds=bnds, constraints=cons,
                           options={"maxiter": 200, "ftol": 1e-9})
            if res.success:
                w = res.x
        W[t] = w
    comp = pd.Series((S * W).sum(axis=1), index=dates, name="signal")
    return comp, pd.DataFrame(W, index=dates, columns=names)


def composite_signals(members=None, target=BACKTEST["benchmark"], window=120):
    """只算两个组合的日频综合信号（不回测），返回 ({标签:信号}, 成员信号, 动态权重)。
    供面板配合时间轴滑块按区间重算（信号计算较重、缓存一次即可）。"""
    sigs = member_signals(members, target)
    bench = load_index(target)
    ret = bench.set_index("date")["close"].pct_change().reindex(sigs.index).fillna(0)
    eq = equal_signal(sigs).rename("signal")
    dyn, W = dynamic_weights(sigs, ret, window=window)
    return {"等权合成": eq, "动态赋权": dyn}, sigs, W


def run_composites(members=None, target=BACKTEST["benchmark"], window=120,
                   start=None, end=None, exec_mode="close"):
    """跑等权 + 动态赋权两个组合，返回 (结果dict, 成员信号, 动态权重)。
    exec_mode: 'close'(周五收盘成交) / 'next_open'(次周开盘成交,版本2默认)。"""
    comp, sigs, W = composite_signals(members, target, window)
    bench = load_index(target)
    results = {}
    for tag, sig in comp.items():
        results[tag] = run_backtest(bench, sig, name=tag, start=start, end=end, exec_mode=exec_mode)
    return results, sigs, W


if __name__ == "__main__":
    res, sigs, W = run_composites()
    print(f"组合成员（{len(sigs.columns)}）：{list(sigs.columns)}")
    for tag, r in res.items():
        m = r["metrics"]
        print(f"[{tag}] 年化{m['年化收益率']*100:5.2f}%  回撤{m['最大回撤']*100:4.1f}%  "
              f"IR{m['年化IR']:.2f}  次数{m['信号次数']}  次均{m['次均天数']:.0f}  次胜率{m['信号次胜率']*100:.0f}%")
