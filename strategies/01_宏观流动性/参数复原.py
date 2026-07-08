# -*- coding: utf-8 -*-
"""
01 宏观流动性 —— 参数复原
=========================
研报未公开参数，这里按【先对齐信号频率、再对齐净值、最后验收】的顺序分步扫描，
自动逼近研报绩效（年化11.4% / 回撤21.37% / IR0.73 / 信号21次 / 次均58天）。

调整顺序（每一步锁定其它参数、只扫一个）：
  步骤1  扫 p            —— 对齐【信号次数】≈21（阈值高低决定信号频率）
  步骤2  扫 zscore_window —— 对齐【次均天数】≈58（灵敏度决定持仓长短）
  步骤3  扫 smooth_window —— 对齐【年化收益率】≈11.4%（平滑影响信号时点）
  最后   验收 年化IR / 最大回撤，输出复原参数

运行：  python strategies/01_宏观流动性/参数复原.py
产出：  本目录 复原参数.json（供 dashboard“载入复原参数”）、调整日志.csv
"""
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from src.calibrate import run_calibration

_spec = importlib.util.spec_from_file_location("策略", HERE / "策略.py")
策略 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(策略)

# (参数名, 候选值, 该步对齐的研报目标指标)
STEPS = [
    ("p",            [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0],  "信号次数"),
    ("zscore_window", [18, 24, 30, 36, 42, 48, 60],        "次均天数"),
    ("smooth_window", [1, 2, 3, 4, 6],                     "年化收益率"),
]

if __name__ == "__main__":
    run_calibration(策略, STEPS)
