# -*- coding: utf-8 -*-
"""运行本子策略：周度 · 中证800 回测 -> 生成 report.html。"""
import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))          # 仓库根（导入 src）

from src.runner import run_strategy

# 加载同目录下中文名的 策略.py
_spec = importlib.util.spec_from_file_location("策略", HERE / "策略.py")
策略 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(策略)

if __name__ == "__main__":
    run_strategy(策略)
