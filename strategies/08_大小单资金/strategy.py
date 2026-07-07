# -*- coding: utf-8 -*-
"""
08 大小单资金 —— 信号构造【占位，待补数据】
===========================================
缺“超大单主动净流入”数据，暂不实现。数据补齐后，参照下方 TODO 完成即可。

预期实现（与 config.PARAMS['大小单资金'] 对应）：
    强度 = 超大单主动净流入 / A股流通市值(load_float_mktcap)
    方向 = ma_diff(强度, short_ma, long_ma)
    signal = sign_signal(方向, positive_is_long=True)   # 正->做多，负->空仓
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

NAME = "大小单资金"
REPORT_KEY = "大小单资金"


def build_signal():
    raise NotImplementedError(
        "缺“超大单主动净流入”数据，无法构造大小单资金信号。"
        "请先在 data/raw/主数据.xlsx 补充该表，并在 data_loader.py 增加 load_super_large_order()。"
    )
