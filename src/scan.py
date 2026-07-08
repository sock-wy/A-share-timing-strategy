# -*- coding: utf-8 -*-
"""
参数网格扫描
============
在 config.SCAN_GRID 定义的网格上遍历每个子策略，找出：
  · 年化最高 在何参数（附带此参数下的回撤/IR/信号次数）
  · 最大回撤最小 在何参数（限定“年化>0”，避免退化成永远空仓的 0 回撤）
  · 年化IR 最高 在何参数
结果保存为各子策略目录下 扫描摘要.json，供 dashboard 底部展示。

运行：  python -m src.scan          # 扫描全部并保存
"""
import json
import itertools

import numpy as np
import pandas as pd

from .data_loader import load_index
from .backtest import run_backtest
from .config import SCAN_GRID, BACKTEST, ROOT
from .runner import load_strategy

FOLDERS = {  # 子策略名 -> 目录
    "宏观流动性": "01_宏观流动性", "信贷预期": "02_信贷预期", "中美汇率": "03_中美汇率",
    "中美利差": "04_中美利差", "期货基差": "05_期货基差", "期权PCR": "06_期权PCR",
    "融资融券": "07_融资融券", "筹码结构": "09_筹码结构", "长端动量": "10_长端动量",
}


def grid_scan(mod, grid):
    """遍历网格，返回所有组合的指标 DataFrame。"""
    bench = load_index(BACKTEST["benchmark"])
    keys = list(grid.keys())
    rows = []
    for combo in itertools.product(*[grid[k] for k in keys]):
        params = dict(zip(keys, combo))
        m = run_backtest(bench, mod.build_signal(params), name=mod.NAME)["metrics"]
        rows.append({**params, "年化收益率": m["年化收益率"], "年化IR": m["年化IR"],
                     "最大回撤": m["最大回撤"], "信号次数": m["信号次数"]})
    return pd.DataFrame(rows), keys


def summarize(df, keys):
    """从扫描结果里提炼要点。"""
    def pack(row):
        return {"参数": {k: (int(row[k]) if float(row[k]).is_integer() else float(row[k])) for k in keys},
                "年化收益率": float(row["年化收益率"]), "年化IR": float(row["年化IR"]),
                "最大回撤": float(row["最大回撤"]), "信号次数": int(row["信号次数"])}

    best_ret = df.loc[df["年化收益率"].idxmax()]
    best_ir = df.loc[df["年化IR"].idxmax()]
    pos = df[df["年化收益率"] > 0]                       # 回撤最小限定年化为正，避免空仓退化
    best_dd = (pos if len(pos) else df).loc[(pos if len(pos) else df)["最大回撤"].idxmin()]
    return {"年化最高": pack(best_ret), "回撤最小": pack(best_dd),
            "IR最高": pack(best_ir), "网格组合数": int(len(df))}


def scan_all():
    for name, folder in FOLDERS.items():
        if name not in SCAN_GRID:
            continue
        mod = load_strategy(folder)
        df, keys = grid_scan(mod, SCAN_GRID[name])
        summary = summarize(df, keys)
        with open(ROOT / "strategies" / folder / "扫描摘要.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        a, d = summary["年化最高"], summary["回撤最小"]
        print(f"[{name}] 组合{summary['网格组合数']:>3}  "
              f"年化最高 {a['年化收益率']*100:5.2f}% @ {a['参数']}  |  "
              f"回撤最小 {d['最大回撤']*100:5.2f}% @ {d['参数']}")


if __name__ == "__main__":
    scan_all()
