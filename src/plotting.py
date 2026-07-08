# -*- coding: utf-8 -*-
"""
可视化模块
==========
每个子策略回测后生成一个自包含 report.html（用浏览器直接打开、可交互）：
  ① 净值图：中证800净值 / 策略净值 / 策略超额 + 做多窗口阴影（对应研报图3-图12）
  ② 逐笔交易表：每一笔做多的进出场、持仓天数、收益、盈亏
  ③ 指标对照表：研报绩效 vs 本次复现
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import REPORT_PERF, OUTPUT_DIR

_PCT = {"年化收益率", "年化波动率", "最大回撤", "周胜率", "信号次胜率"}


def _fmt(k, v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "-"
    if k in _PCT:
        return f"{v*100:.2f}%"
    if k in {"次均天数", "信号次数"}:
        return f"{v:.0f}"
    return f"{v:.2f}"


def _long_windows(wk: pd.DataFrame):
    """返回做多窗口 [(起,止), ...]，用于净值图阴影。"""
    pos = wk["position"].values
    spans, i, n = [], 0, len(wk)
    while i < n:
        if pos[i] == 1:
            j = i
            while j + 1 < n and pos[j + 1] == 1:
                j += 1
            spans.append((wk.index[i], wk.index[j]))
            i = j + 1
        else:
            i += 1
    return spans


def nav_figure(result: dict, title=None):
    """构造净值图 Plotly Figure（策略/中证800/超额 + 做多窗口阴影），供 HTML 与 dashboard 复用。"""
    wk, name = result["weekly"], result["name"]
    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Scatter(x=wk.index, y=wk["bench_nav"], name="中证800",
                             line=dict(color="#9aa0a6", width=1.5)))
    fig.add_trace(go.Scatter(x=wk.index, y=wk["strat_nav"], name="策略净值",
                             line=dict(color="#d93025", width=2)))
    fig.add_trace(go.Scatter(x=wk.index, y=wk["excess_nav"], name="策略超额",
                             line=dict(color="#1a73e8", width=1.5, dash="dot")))
    for a, b in _long_windows(wk):
        fig.add_vrect(x0=a, x1=b, fillcolor="#fbbc04", opacity=0.12, line_width=0)
    fig.update_layout(
        title=title or f"{name}｜择时净值（黄色=做多窗口）",
        template="plotly_white", height=460, hovermode="x unified",
        legend=dict(orientation="h", y=1.08),
        margin=dict(l=50, r=30, t=70, b=30),
    )
    fig.update_yaxes(title="净值")
    return fig


def build_report(result: dict, report_key: str, out_path=None) -> str:
    """生成 HTML 报告，返回文件路径。report_key 用于取研报基准（如 '宏观流动性'）。"""
    wk, trades, m = result["weekly"], result["trades"], result["metrics"]
    name = result["name"]

    # ---------------- ① 净值图 ----------------
    chart_html = nav_figure(result).to_html(full_html=False, include_plotlyjs="cdn")

    # ---------------- ② 指标对照表 ----------------
    rep = REPORT_PERF.get(report_key, {})
    order = ["年化收益率", "年化波动率", "年化IR", "最大回撤", "Calmar比率",
             "周胜率", "周赔率", "信号次胜率", "信号次赔率", "次均天数", "信号次数"]
    rows = "".join(
        f"<tr><td>{k}</td><td class='num'>{_fmt(k, m.get(k))}</td>"
        f"<td class='num rep'>{_fmt(k, rep.get(k))}</td></tr>"
        for k in order
    )
    metric_table = f"""
    <table class='tbl'><thead><tr><th>指标</th><th>本次复现</th><th>研报</th></tr></thead>
    <tbody>{rows}</tbody></table>"""

    # ---------------- ③ 逐笔交易表 ----------------
    if len(trades):
        t = trades.copy()
        t["每笔收益"] = (t["trade_return"] * 100).round(2).astype(str) + "%"
        t = t[["序号", "进场日期", "出场日期", "持仓周数", "holding_days",
               "进场价", "出场价", "每笔收益", "盈亏"]]
        t = t.rename(columns={"holding_days": "持仓天数"})
        trade_rows = "".join(
            "<tr>" + "".join(f"<td class='num'>{v}</td>" for v in row) +
            f"</tr>" for row in t.values
        )
        trade_head = "".join(f"<th>{c}</th>" for c in t.columns)
        trade_table = f"<table class='tbl'><thead><tr>{trade_head}</tr></thead><tbody>{trade_rows}</tbody></table>"
    else:
        trade_table = "<p>无做多交易。</p>"

    html = f"""<!doctype html><html lang='zh'><head><meta charset='utf-8'>
<title>{name} 择时回测</title>
<style>
 body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;margin:24px;color:#202124;background:#fff}}
 h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px;border-left:4px solid #d93025;padding-left:8px}}
 .tbl{{border-collapse:collapse;font-size:13px;margin-top:8px}}
 .tbl th,.tbl td{{border:1px solid #e0e0e0;padding:5px 10px;text-align:left}}
 .tbl th{{background:#f5f5f5}} .num{{text-align:right;font-variant-numeric:tabular-nums}}
 .rep{{color:#5f6368}} .wrap{{overflow-x:auto}}
</style></head><body>
<h1>{name}｜周度 · 中证800 择时回测</h1>
<h2>① 择时净值</h2>{chart_html}
<h2>② 绩效指标（复现 vs 研报）</h2>{metric_table}
<h2>③ 逐笔交易明细（每一笔做多）</h2><div class='wrap'>{trade_table}</div>
</body></html>"""

    out_path = out_path or (OUTPUT_DIR / f"{name}_report.html")
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return str(out_path)
