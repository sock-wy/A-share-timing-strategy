# -*- coding: utf-8 -*-
"""
综合最相似参数搜索
==================
在参数网格上找“多指标总体最像研报”的一组参数。

综合距离（越小越像）：
    距离 = Σ 权重ᵢ · |复现ᵢ − 研报ᵢ| / |研报ᵢ|  ÷  Σ 权重ᵢ
其中对每个指标取【相对偏差】（除以研报值）抹平量纲，再加权平均。

纳入指标与权重（核心6指标，收益/风险加倍）：
    年化收益率 ×2、最大回撤 ×2、信号次数 ×1、次均天数 ×1、信号次胜率 ×1、信号次赔率 ×1

搜索：先在 config.SCAN_GRID 上网格遍历取最优，再在最优点相邻网格之间撒更密的
局部网格微调（提高精度）。

运行：  python -m src.similarity      # 全部子策略，结果并入各自 扫描摘要.json
"""
import json
import itertools

import numpy as np

from .data_loader import load_index
from .backtest import run_backtest
from .config import SCAN_GRID, REPORT_PERF, BACKTEST, ROOT
from .runner import load_strategy
from .scan import FOLDERS

# 指标权重（收益/风险 ×2，其余 ×1）
METRIC_WEIGHTS = {"年化收益率": 2, "最大回撤": 2, "信号次数": 1,
                  "次均天数": 1, "信号次胜率": 1, "信号次赔率": 1}
# 一行小字说明（面板与报告复用）
DISTANCE_NOTE = ("综合距离 = 各指标相对偏差 |复现−研报|/|研报| 的加权平均；"
                 "权重：年化收益率 ×2、最大回撤 ×2，信号次数/次均天数/次胜率/次赔率 各 ×1。距离越小越像。")


def distance(m, rep):
    """加权平均相对偏差。"""
    num = den = 0.0
    for k, w in METRIC_WEIGHTS.items():
        r, v = rep.get(k), m.get(k)
        if r in (None, 0) or v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        num += w * abs(v - r) / abs(r)
        den += w
    return num / den if den else np.inf


def _num(x):
    if isinstance(x, str):        # 字符串参数(如 ma_kind)原样返回
        return x
    return int(x) if float(x).is_integer() else round(float(x), 4)


def _local_candidates(best_val, grid_vals):
    """在最优值相邻网格点之间撒 5 个更密的候选。"""
    g = sorted(grid_vals)
    i = g.index(best_val)
    lo = g[i - 1] if i > 0 else best_val
    hi = g[i + 1] if i < len(g) - 1 else best_val
    is_int = all(float(v).is_integer() for v in g)
    pts = np.linspace(lo, hi, 5)
    pts = {int(round(x)) for x in pts} if is_int else {round(float(x), 3) for x in pts}
    return sorted(pts)


def find_most_similar(mod, grid=None, refine=True):
    """返回 {参数, 综合距离, 逐指标[...]}。"""
    grid = grid or SCAN_GRID[mod.NAME]
    rep = REPORT_PERF[mod.REPORT_KEY]
    bench = load_index(BACKTEST["benchmark"])
    keys = list(grid.keys())

    def ev(params):
        m = run_backtest(bench, mod.build_signal(params), name=mod.NAME)["metrics"]
        return m, distance(m, rep)

    best = None
    for combo in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        m, d = ev(params)
        if best is None or d < best[1]:
            best = (params, d, m)

    if refine:
        # 仅对数值参数做局部细化；字符串参数(如 ma_kind)固定为最优值
        local = {}
        for k in keys:
            if all(isinstance(v, (int, float)) for v in grid[k]):
                local[k] = _local_candidates(best[0][k], grid[k])
            else:
                local[k] = [best[0][k]]
        for combo in itertools.product(*[local[k] for k in keys]):
            params = dict(zip(keys, combo))
            m, d = ev(params)
            if d < best[1]:
                best = (params, d, m)

    params, d, m = best
    breakdown = [{"指标": k, "复现": float(m[k]), "研报": float(rep[k]),
                  "相对偏差": abs(m[k] - rep[k]) / abs(rep[k]) if rep.get(k) else None,
                  "权重": METRIC_WEIGHTS[k]} for k in METRIC_WEIGHTS]
    return {"参数": {k: _num(v) for k, v in params.items()},
            "综合距离": float(d), "逐指标": breakdown, "说明": DISTANCE_NOTE}


def similarity_all():
    for name, folder in FOLDERS.items():
        if name not in SCAN_GRID:
            continue
        mod = load_strategy(folder)
        res = find_most_similar(mod)
        # 并入既有 扫描摘要.json
        path = ROOT / "strategies" / folder / "扫描摘要.json"
        data = json.load(open(path, encoding="utf-8")) if path.exists() else {}
        data["综合最相似"] = res
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[{name}] 综合最相似 距离={res['综合距离']:.3f} @ {res['参数']}")


if __name__ == "__main__":
    similarity_all()
