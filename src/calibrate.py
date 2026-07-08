# -*- coding: utf-8 -*-
"""
参数复原引擎
============
思路：研报只给信号方向、不给参数。我们从默认参数出发，**按给定顺序分步扫描**：
每一步锁定其它参数、只扫一个参数的候选值，选出让【该步对齐目标指标】最接近研报的取值，
采纳后进入下一步。全过程记录成日志表，最后输出“复原参数”与验收对照。

用法（见各子策略目录下 参数复原.py）：
    from src.calibrate import run_calibration
    STEPS = [("p", [0.3,0.4,0.5,0.6,0.7,0.8], "信号次数"),
             ("zscore_window", [24,30,36,42,48], "次均天数"),
             ("smooth_window", [1,2,3,4,6], "年化收益率")]
    run_calibration(策略, STEPS)
"""
import json

import numpy as np
import pandas as pd

from .data_loader import load_index
from .backtest import run_backtest
from .config import PARAMS, REPORT_PERF, BACKTEST, ROOT

_KEYS = ["年化收益率", "年化IR", "最大回撤", "信号次数", "次均天数"]


def evaluate(mod, params):
    """给定参数，跑一次中证800周度回测，返回 (指标dict, 完整结果)。"""
    bench = load_index(BACKTEST["benchmark"])
    res = run_backtest(bench, mod.build_signal(params), name=mod.NAME)
    return res["metrics"], res


def run_calibration(mod, steps, save=True, verbose=True):
    """按 steps 顺序分步扫描调参。

    steps : [(参数名, [候选值...], 对齐目标指标名), ...]
    返回  : (复原参数dict, 调整日志DataFrame, 最终指标dict, 最终结果)
    """
    target = REPORT_PERF[mod.REPORT_KEY]
    best = dict(PARAMS[mod.NAME])                       # 从默认参数出发
    log = []

    for i, (pname, candidates, objective) in enumerate(steps, 1):
        tgt = target.get(objective, np.nan)
        trials = []
        for v in candidates:
            trial = dict(best)
            trial[pname] = v
            m, _ = evaluate(mod, trial)
            diff = abs(m[objective] - tgt) if tgt == tgt else np.nan
            trials.append((v, m, diff))
            log.append({
                "步骤": i, "调整参数": pname, "取值": v, "对齐目标": objective,
                **{k: m[k] for k in _KEYS},
                "距研报": diff, "采纳": False,
            })
        best_v = min(trials, key=lambda t: (np.inf if t[2] != t[2] else t[2]))[0]
        best[pname] = best_v
        for row in log:                                # 标记本步采纳项
            if row["步骤"] == i and row["取值"] == best_v:
                row["采纳"] = True

    log_df = pd.DataFrame(log)
    m_final, res_final = evaluate(mod, best)

    if verbose:
        _print_report(mod, best, log_df, m_final, target)
    if save:
        out = ROOT / "strategies"
        # 由 REPORT_KEY 反查目录（前缀编号+名称）
        folder = next(p for p in (out).iterdir() if p.is_dir() and mod.NAME in p.name)
        with open(folder / "复原参数.json", "w", encoding="utf-8") as f:
            json.dump(best, f, ensure_ascii=False, indent=2)
        log_df.to_csv(folder / "调整日志.csv", index=False, encoding="utf-8-sig")
    return best, log_df, m_final, res_final


def _fmt(k, v):
    if v != v:
        return "-"
    if k in {"年化收益率", "最大回撤"}:
        return f"{v*100:.2f}%"
    if k in {"信号次数", "次均天数"}:
        return f"{v:.0f}"
    return f"{v:.2f}"


def _print_report(mod, best, log_df, m_final, target):
    print(f"\n{'='*60}\n【{mod.NAME}】参数复原调整日志\n{'='*60}")
    show = log_df.copy()
    for k in _KEYS:
        show[k] = [_fmt(k, x) for x in show[k]]
    show["距研报"] = [f"{x:.3f}" if x == x else "-" for x in show["距研报"]]
    show["采纳"] = show["采纳"].map({True: "✔", False: ""})
    print(show.to_string(index=False))

    print(f"\n{'-'*60}\n复原参数：{best}\n{'-'*60}")
    print(f"{'指标':<10}{'复原值':>12}{'研报值':>12}")
    for k in _KEYS:
        rv = target.get(k, np.nan)
        print(f"{k:<10}{_fmt(k, m_final[k]):>12}{_fmt(k, rv):>12}")
