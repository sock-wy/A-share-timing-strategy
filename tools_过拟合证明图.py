# -*- coding: utf-8 -*-
"""8成员过拟合证明图：每策略在两个主旋钮上的 样本内 vs 样本外 年化热力图，标出组1点。
组1在高原(周围一片同色)=稳健；孤峰=过拟合；IS/OOS 最优区同块=真信号。"""
import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from src.data_loader import load_index
from src.backtest import run_backtest
from src.runner import load_strategy, build_signal_for

# 中文字体（尽量找一个）
for fp in ['/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
           '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
           '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
    try:
        font_manager.fontManager.addfont(fp); break
    except Exception:
        pass
plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'Noto Sans CJK SC', 'DejaVu Sans']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

BENCH = load_index('中证800')
IS = ('2015-01-05', '2020-12-31'); OOS = ('2021-01-01', '2025-11-28')

def ann(folder, params, s, e):
    mod = load_strategy(folder); sig = build_signal_for(mod, params, '中证800')
    return run_backtest(BENCH, sig, confirm_weeks=1, start=s, end=e)['metrics']['年化收益率'] * 100

# 每个策略：folder, 固定参数, 两个扫描轴(名/取值), 组1点(x,y), 标题
def grid_map(folder, base, xk, xs, yk, ys, seg):
    Z = np.full((len(ys), len(xs)), np.nan)
    for iy, yv in enumerate(ys):
        for ix, xv in enumerate(xs):
            p = dict(base); p[xk] = xv; p[yk] = yv
            if xk in ('short_ma',) and yk in ('long_ma',) and xv >= yv:
                continue
            try:
                Z[iy, ix] = ann(folder, p, *seg)
            except Exception:
                pass
    return Z

STRATS = [
    dict(folder='01_宏观流动性', title='宏观 (组1: sw9,zw3)', base=dict(smooth_window=9, zscore_window=3, p=0.1, full_window=1),
         xk='zscore_window', xs=[2,3,6,9,12,18,24,36], yk='smooth_window', ys=[1,3,5,6,9,12], pt=(3,9)),
    dict(folder='02_信贷预期', title='信贷 (组1: 10/90,EMA,-.002)', base=dict(data_mode='插值', yoy_window=400, ma_kind='EMA', threshold=-0.002),
         xk='short_ma', xs=[5,10,15,20,25,30,40], yk='long_ma', ys=[60,90,120,150,180,210,250], pt=(10,90)),
    dict(folder='03_中美汇率', title='汇率 (组1≈10/40,EMA,-.004)', base=dict(ma_kind='EMA', threshold=-0.004),
         xk='short_ma', xs=[5,8,10,15,20,25,30,40], yk='long_ma', ys=[20,30,40,60,90,120,150,180], pt=(10,40)),
    dict(folder='04_中美利差', title='利差 (组1: 10/80,SMA,-.05)', base=dict(ma_kind='SMA', threshold=-0.05),
         xk='short_ma', xs=[5,8,10,15,20,25,30,40], yk='long_ma', ys=[40,60,80,100,120,150,180,250], pt=(10,80)),
    dict(folder='05_期货基差', title='基差 (组1: sd3,ma74,p1.4)', base=dict(smooth_days=3),
         xk='ma_window', xs=[40,55,65,74,85,100,120,150], yk='p', ys=[0.5,0.8,1.0,1.2,1.4,1.6,1.8], pt=(74,1.4)),
    dict(folder='06_期权PCR', title='PCR (组1: 10/30,SMA,-.025)', base=dict(ma_kind='SMA', threshold=-0.025),
         xk='short_ma', xs=[5,8,10,15,20,25,30,40], yk='long_ma', ys=[20,30,38,50,60,90,120,150], pt=(10,30)),
    dict(folder='07_融资融券', title='融资 (组1≈45/11)', base=dict(),
         xk='short_ma', xs=[5,10,15,20,25,30,40,50], yk='neutral_window', ys=[20,30,45,60,90,120,180,250], pt=(11,45)),
    dict(folder='10_长端动量', title='长端 (组1: L150,amp.85,p0.4)', base=dict(amp_quantile=0.85),
         xk='lookback', xs=[80,110,130,150,180,210,250], yk='p', ys=[0.2,0.3,0.4,0.5,0.7,0.9,1.1], pt=(150,0.4)),
]

fig, axes = plt.subplots(len(STRATS), 2, figsize=(11, 3.0 * len(STRATS)))
for r, S in enumerate(STRATS):
    for c, (seg, lab) in enumerate([(IS, '样本内 2015-2020'), (OOS, '样本外 2021-2025')]):
        Z = grid_map(S['folder'], S['base'], S['xk'], S['xs'], S['yk'], S['ys'], seg)
        ax = axes[r, c]
        im = ax.imshow(Z, aspect='auto', origin='lower', cmap='RdYlGn', vmin=-2, vmax=12)
        ax.set_xticks(range(len(S['xs']))); ax.set_xticklabels(S['xs'], fontsize=7)
        ax.set_yticks(range(len(S['ys']))); ax.set_yticklabels(S['ys'], fontsize=7)
        ax.set_xlabel(S['xk'], fontsize=7); ax.set_ylabel(S['yk'], fontsize=7)
        # 标组1点
        try:
            px = S['xs'].index(S['pt'][0]); py = S['ys'].index(S['pt'][1])
            ax.plot(px, py, marker='*', ms=16, mec='black', mfc='cyan', mew=1.2)
        except ValueError:
            pass
        for iy in range(len(S['ys'])):
            for ix in range(len(S['xs'])):
                if not np.isnan(Z[iy, ix]):
                    ax.text(ix, iy, f"{Z[iy,ix]:.0f}", ha='center', va='center', fontsize=5.5, color='#222')
        ax.set_title(f"{S['title']} · {lab}", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
fig.suptitle('子策略参数稳定性：样本内 vs 样本外 年化(%)   ★=组1   高原=稳健/孤峰=过拟合   IS与OOS最优区同块=真信号',
             fontsize=10, y=1.002)
fig.tight_layout()
import os; os.makedirs('outputs',exist_ok=True); OUT='outputs/过拟合证明图.png'
fig.savefig(OUT, dpi=130, bbox_inches='tight')
print('SAVED', OUT)
print('DONE_FIG')
