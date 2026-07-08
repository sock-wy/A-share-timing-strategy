# A股权益择时多策略框架（复现）

复现开源证券《权益择时的多策略框架：从宏观驱动到微观验证》（2025-12-06）。
6 维度共 **10 个子策略** + **等权/动态赋权** 2 个合成模型。

## 统一回测口径（研报 P5）
- 区间 **20150105–20251128**；基准 **中证800**；
- **周度调仓**（每周最后一个交易日收盘价）；
- 信号 **> 0 满仓做多**、**≤ 0 空仓**。

## 目录结构
```
data/raw/            主数据.xlsx（你现有的数据）、校准信息.xlsx
src/                 公共引擎（所有子策略共用，改一处全局生效）
  ├─ config.py       全局口径 + 各子策略参数(p值/长短均线) + 研报绩效基准
  ├─ data_loader.py  数据导入，逐表标注【月度/日度/周度】
  ├─ signal_utils.py 信号公共函数（均线差/Zscore阈值/延续信号）
  ├─ backtest.py     周度回测引擎（防未来函数对齐）
  ├─ metrics.py      研报全部指标（年化/IR/回撤/Calmar/周胜赔率/次胜赔率/次均天数/次数）
  └─ plotting.py     生成自包含 report.html（净值+做多窗口+逐笔交易+指标对照）
strategies/          10 个子策略，每个 = README(原文) + strategy.py(产信号) + run.py
  ├─ 01_宏观流动性/ 02_信贷预期/          ✅ 已实现
  ├─ 03_中美汇率/ 04_中美利差/           ✅ 已实现
  ├─ 05_期货基差/ 06_期权PCR/            ✅ 已实现
  ├─ 07_融资融券/                        ✅ 已实现
  ├─ 08_大小单资金/                      ⛔ 缺“超大单主动净流入”数据，留空占位
  └─ 09_筹码结构/ 10_长端动量/           ✅ 已实现
composite/           等权合成 / 动态赋权（骨架）
dashboard/           Streamlit 面板（骨架）
outputs/             回测生成的 report.html
```

## 环境
```bash
pip install -r requirements.txt
```

## 怎么跑、在哪看结果
**单个子策略**（生成可交互 HTML，浏览器打开即可看净值+每一笔交易+指标对照）：
```bash
python strategies/01_宏观流动性/run.py     # -> outputs/宏观流动性_report.html
python strategies/02_信贷预期/run.py       # -> outputs/信贷预期_report.html
```
**最终面板**（后期）：
```bash
streamlit run dashboard/app.py            # 下拉选策略、并排比指标
```

## 关于参数校准 ⚠️
研报**只公开信号方向，未公开 p 值 / 均线长度**。所有参数集中在 `src/config.py -> PARAMS`，
请对照 `校准信息.xlsx` 与研报绩效表（已录入 `config.REPORT_PERF`）反复调参逼近。
report.html 里自带“复现 vs 研报”对照表，方便边调边看。

> 注意：`中长期贷款` 为自然日序列（3981 行），窗口按自然日设（同比≈365）；
> 其余日度序列为交易日。
