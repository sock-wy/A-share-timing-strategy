# -*- coding: utf-8 -*-
"""
一键全自动校准
==============
对每个子策略，在 SCAN_GRID（均线差类同时搜 SMA/EMA + threshold）上用多指标距离
（年化收益率、最大回撤 权重×2；信号次数/次均天数/次胜率/次赔率 各×1）搜索“最贴研报”
的参数，自动写入该策略「组1」（供全策略汇总直接展示），并打印拟合度排行。

拟合度 = 综合距离（越小越贴合研报，也即越贴合研报曲线，因为这几个指标共同约束曲线）。
同时给出样本内(2015-2021)/样本外(2022-2025)的年化，用于识别过拟合/样本外失效。

运行：  python -m src.autofit
"""
import json

from .data_loader import load_index
from .backtest import run_backtest
from .config import BACKTEST, ROOT
from .runner import load_strategy
from .scan import FOLDERS
from .similarity import find_most_similar, DISTANCE_NOTE

IN_SAMPLE = ("2015-01-05", "2021-12-31")
OUT_SAMPLE = ("2022-01-01", "2025-11-28")


def _ann(mod, params, start=None, end=None):
    m = run_backtest(load_index(BACKTEST["benchmark"]), mod.build_signal(params),
                     name=mod.NAME, start=start, end=end)["metrics"]
    return m["年化收益率"], m["最大回撤"], m["信号次数"]


def _write_group1(folder, params):
    gf = ROOT / "strategies" / folder / "我的参数组.json"
    data = json.load(open(gf, encoding="utf-8")) if gf.exists() else {}
    g = dict(params)
    g["confirm_weeks"] = 1
    data["组1"] = g
    json.dump(data, open(gf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def autofit():
    print(f"全自动校准中（多指标距离，年化&回撤×2）……\n{DISTANCE_NOTE}\n")
    rows = []
    for name, folder in FOLDERS.items():
        mod = load_strategy(folder)
        res = find_most_similar(mod)                 # 全区间最贴研报
        best, dist = res["参数"], res["综合距离"]
        af, _, _ = _ann(mod, best)
        ai, _, _ = _ann(mod, best, *IN_SAMPLE)
        ao, _, _ = _ann(mod, best, *OUT_SAMPLE)
        _write_group1(folder, best)
        rows.append((dist, name, af, ai, ao, best))

    rows.sort(key=lambda r: r[0])                    # 按拟合度（距离）升序
    print(f"{'排名':<4}{'子策略':<10}{'拟合距离':>8}{'全区间年化':>10}"
          f"{'样本内15-21':>11}{'样本外22-25':>11}   最优参数")
    print("-" * 100)
    for i, (dist, name, af, ai, ao, best) in enumerate(rows, 1):
        flag = "  ⚠样本外失效" if (ai > 0.05 and ao < 0) else ""
        gap = "  ⚠参数已到顶(疑数据/口径问题)" if dist > 0.4 else ""
        print(f"{i:<4}{name:<10}{dist:>8.3f}{af*100:>9.1f}%{ai*100:>10.1f}%{ao*100:>10.1f}%"
              f"   {best}{flag}{gap}")
    print("\n各策略最优参数已写入「组1」，全策略汇总页即显示最贴合结果。")


if __name__ == "__main__":
    autofit()
