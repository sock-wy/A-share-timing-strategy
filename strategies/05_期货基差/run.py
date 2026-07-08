# -*- coding: utf-8 -*-
"""运行本子策略：周度 · 中证800 回测 -> 生成 report.html。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))          # 本目录（导入 strategy）
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))      # 仓库根（导入 src）

import strategy
from src.runner import run_strategy

if __name__ == "__main__":
    run_strategy(strategy)
