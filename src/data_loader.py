# -*- coding: utf-8 -*-
"""
数据导入模块
============
统一从 data/raw/主数据.xlsx 读取各 sheet，并**明确标注每个数据集的原始频率**
（月度 / 日度 / 周度）。回测是周度的，但原始指标频率各不相同，
对齐工作交给 backtest.py（严格用“截至周五收盘可获得的信息”做 ffill，防未来函数）。

频率一览：
    【日度】中证800 等 8 个宽基指数、中债指数、国债ETF、中证500ETF、
            中美国债利差、离岸人民币汇率、融资融券、上证50期权PCR、IC股指期货基差、
            中长期贷款(月度数据已被 Wind 插值成日度)
    【月度】宏观流动性净投放(OMO/SLF/MLF/PSL)
    【周度】无原始周度数据；周度是回测调仓频率，由日度重采样得到
    【缺失】超大单主动净流入（大小单资金策略所需，主数据.xlsx 中没有）
"""
import pandas as pd
from .config import DATA_FILE

pd.options.mode.chained_assignment = None   # 关闭 Wind 竖排表切片赋值的链式告警


def _to_dt(df, col="date"):
    df[col] = pd.to_datetime(df[col])
    return df.sort_values(col).reset_index(drop=True)


# ============================================================ 指数（日度）
def load_index(name="中证800"):
    """加载单个宽基指数日线。频率：日度。

    中证800/中证500 含 amplitude、turnover 列；其余宽基仅 OHLCV。
    返回列：date, open, high, low, close, volume, amount, (pct_chg, turnover, amplitude)
    """
    df = pd.read_excel(DATA_FILE, sheet_name=name)
    df = _to_dt(df)
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


# ============================================================ 1 宏观流动性（月度）
def load_macro_liquidity():
    """宏观流动性净投放。频率：月度（每月最后一日）。

    列：date, month, OMO/SLF/MLF/PSL_net_injection, sum(4工具净投放加总)
    研报口径：OMO+SLF+MLF+PSL 4 个货币政策工具净投放加总作为代理指标。
    """
    df = pd.read_excel(DATA_FILE, sheet_name="宏观流动性净投放")
    df = _to_dt(df)
    tools = ["OMO_net_injection", "SLF_net_injection", "MLF_net_injection", "PSL_net_injection"]
    for c in tools:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    # 4 工具净投放加总（不依赖 Excel 里的公式列）
    df["net_injection"] = df[tools].sum(axis=1)
    return df[["date", "month"] + tools + ["net_injection"]]


# ============================================================ 2 信贷预期（日度，源为月度插值）
def load_long_term_loan():
    """金融机构中长期贷款余额。频率：日度（Wind 已将月度余额插值为日度）。

    原表前两行是标题说明，真实数据从第 3 行起：date, value(亿元)。
    """
    df = pd.read_excel(DATA_FILE, sheet_name="中长期贷款", header=None, skiprows=2,
                       names=["date", "value"])
    df = _to_dt(df)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna()


# ============================================================ 3.1 中美汇率（日度）
def load_usdcnh():
    """美元兑离岸人民币汇率 USDCNH。频率：日度。列：date, close(最新价)"""
    df = pd.read_excel(DATA_FILE, sheet_name="离岸人民币汇率")
    df = df.rename(columns={"最新价": "close"})
    df = _to_dt(df)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df[["date", "close"]].dropna()


# ============================================================ 3.2 中美利差（日度）
def load_us_cn_spread():
    """中美10年期国债利差。频率：日度。spread = 中国10Y - 美国10Y"""
    df = pd.read_excel(DATA_FILE, sheet_name="中美国债利差")
    df = _to_dt(df)
    cn = pd.to_numeric(df["中国国债收益率10年"], errors="coerce")
    us = pd.to_numeric(df["美国国债收益率10年"], errors="coerce")
    out = pd.DataFrame({"date": df["date"], "spread": cn - us}).dropna()
    return out.reset_index(drop=True)


# ============================================================ 5.1 融资融券（日度）
def load_margin():
    """融资融券。频率：日度。列：date, margin_buy(融资买入额), short_sell(融券卖出额)"""
    df = pd.read_excel(DATA_FILE, sheet_name="融资融券")
    df = _to_dt(df)
    for c in ["margin_buy", "short_sell"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna()


def load_float_mktcap():
    """A股流通市值（融资融券/超大单强度的分母）。频率：日度。

    原表为 Wind 竖排格式，标题占前若干行，真实表头在第 4 行。
    """
    df = pd.read_excel(DATA_FILE, sheet_name="A股流通市值", header=3)
    df = df.rename(columns={df.columns[0]: "date"})
    df = df[pd.to_datetime(df["date"], errors="coerce").notna()].copy()
    df = _to_dt(df)
    df["float_mktcap"] = pd.to_numeric(df.iloc[:, -1], errors="coerce")
    return df[["date", "float_mktcap"]].dropna()


# ============================================================ 4.1 期货基差（日度）
def load_ic_basis():
    """IC股指期货基差。频率：日度。基差 = IC期货收盘 − 中证500现货收盘。

    原表 Wind 竖排：前 5 行为标题，数据从第 6 行；列 = date, IC.CFE(期货), 000905.SH(现货)。
    注意：IC 于 2015-04-16 上市，之前期货为空 -> 基差从该日起才有效。
    """
    df = pd.read_excel(DATA_FILE, sheet_name="IC股指期货基差", header=None, skiprows=5,
                       names=["date", "fut", "spot"])
    df = _to_dt(df)
    df["fut"] = pd.to_numeric(df["fut"], errors="coerce")
    df["spot"] = pd.to_numeric(df["spot"], errors="coerce")
    df["basis"] = df["fut"] - df["spot"]                 # 基差（点）
    df["basis_rate"] = df["basis"] / df["spot"]          # 基差率（归一化，更稳健）
    return df.dropna(subset=["basis_rate"])[["date", "basis", "basis_rate"]]


# ============================================================ 4.2 期权PCR（日度）
def load_pcr():
    """上证50ETF期权 认沽/认购持仓量比 PCR。频率：日度。

    原表前 6 行为标题，数据从第 7 行；列 = date, calloi(认购持仓), putoi(认沽持仓)。
    PCR = 认沽持仓 / 认购持仓；期权 2015-02-09 上市，之前为 0 -> 剔除。
    """
    df = pd.read_excel(DATA_FILE, sheet_name="上证50认沽认购持仓量比", header=None, skiprows=6,
                       names=["date", "calloi", "putoi"])
    df = _to_dt(df)
    for c in ["calloi", "putoi"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[(df["calloi"] > 0) & (df["putoi"] > 0)].copy()
    df["pcr"] = df["putoi"] / df["calloi"]
    return df[["date", "pcr"]].reset_index(drop=True)


# ============================================================ 6.1 筹码结构用：宽基换手率（日度）
def load_turnover(name="中证800"):
    """各宽基指数日换手率（%）。频率：日度。

    原表前 5 行为标题，数据从第 6 行；列含 8 个宽基。返回 date + 指定指数换手率。
    """
    # header=3 取“日期/上证指数/…/中证800/…”中文名行；下一行(代码行)由日期非法被过滤
    df = pd.read_excel(DATA_FILE, sheet_name="各宽基换手率", header=3)
    df = df.rename(columns={df.columns[0]: "date"})
    df = df[pd.to_datetime(df["date"], errors="coerce").notna()].copy()
    df = _to_dt(df)
    df["turnover"] = pd.to_numeric(df[name], errors="coerce")
    return df[["date", "turnover"]].dropna()


# ============================================================ 通用工具
def load_all_indices():
    """一次性加载全部 8 个宽基指数（用于泛化测试）。频率：日度。"""
    names = ["中证800", "中证500", "沪深300", "上证50", "中证1000",
             "上证综指", "深证成指", "创业板指"]
    return {n: load_index(n) for n in names}


if __name__ == "__main__":
    # 快速自检：打印各数据集频率与区间
    for name, fn in [("中证800(日度)", lambda: load_index("中证800")),
                     ("宏观流动性净投放(月度)", load_macro_liquidity),
                     ("中长期贷款(日度)", load_long_term_loan),
                     ("离岸人民币(日度)", load_usdcnh),
                     ("中美利差(日度)", load_us_cn_spread),
                     ("融资融券(日度)", load_margin)]:
        d = fn()
        print(f"{name:24s} rows={len(d):5d}  {d['date'].min().date()} ~ {d['date'].max().date()}")
