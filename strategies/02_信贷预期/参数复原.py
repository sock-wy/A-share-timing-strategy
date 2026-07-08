# -*- coding: utf-8 -*-
"""
信贷预期 —— 参数复原【占位·待配置】
========
研报未公开参数。建议调整顺序（先对齐信号频率、再对齐净值、最后验收）：
  注意：中长期贷款为【自然日】序列，yoy_window 应≈365。
  步骤1 扫 long_ma  —— 对齐【信号次数】≈12
  步骤2 扫 short_ma —— 对齐【次均天数】≈87
  步骤3 扫 yoy_window —— 对齐【年化收益率】≈8.4%

启用方法：参照 01_宏观流动性/参数复原.py，取消下方 STEPS 注释并按需微调候选值，
然后 `python strategies/02_信贷预期/参数复原.py` 即可跑分步扫描、生成 复原参数.json。
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

# —— 待配置：取消注释并按需调整候选值 ——
# STEPS = [("long_ma",[120,180,250,365],"信号次数"),
#          ("short_ma",[20,40,60,90],"次均天数"),
#          ("yoy_window",[300,365,504],"年化收益率")]

if __name__ == "__main__":
    # run_calibration(策略, STEPS)
    print("【信贷预期】参数复原尚未配置：请先在本文件填写 STEPS 并取消注释。")
