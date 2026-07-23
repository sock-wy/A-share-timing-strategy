# -*- coding: utf-8 -*-
"""
一次性核对：全策略汇总 vs 组合，8 个成员用的参数是否一致。
用法：  python 核对组合参数一致.py
读你本地 strategies/<成员>/我的参数组.json 的「组1」，不修改任何文件。

背景：
· 组合（等权/动态赋权）= _group1_params：读「组1」，剔除 confirm_weeks（强制按 1 计算），用原版策略.py。
· 全策略汇总 = compute_group1：读「组1」（8 成员均无进阶变体，故不涉及进阶），confirm 用组内存的值。
=> 参数天然一致；唯一可能的差异是 confirm_weeks≠1（汇总按 N、组合按 1，数字会不同）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
import sys; sys.path.insert(0, str(ROOT))
from src.config import COMPOSITE_MEMBERS, PARAMS

print(f"\n{'成员':<8}{'组1参数(组合与汇总同源)':<52}{'confirm':>8}   结论")
print("-" * 92)
all_ok = True
for name, folder in COMPOSITE_MEMBERS:
    f = ROOT / "strategies" / folder / "我的参数组.json"
    if not f.exists():
        print(f"{name:<8}{'（无 我的参数组.json → 两者都用代码默认，仍一致）':<52}{'-':>8}   ℹ️ 用默认")
        continue
    g = json.load(open(f, encoding="utf-8")).get("组1")
    if not g:
        print(f"{name:<8}{'（无「组1」→ 两者都用代码默认，仍一致）':<52}{'-':>8}   ℹ️ 用默认")
        continue
    cw = int(g.get("confirm_weeks", 1))
    pstr = ", ".join(f"{k}={v}" for k, v in g.items() if k != "confirm_weeks")
    if cw == 1:
        verdict = "✅ 一致"
    else:
        verdict = f"⚠️ 汇总按{cw}周/组合按1周 → 数字会不同"
        all_ok = False
    print(f"{name:<8}{pstr[:50]:<52}{cw:>8}   {verdict}")

print("-" * 92)
if all_ok:
    print("✅ 全部一致：8 个成员的组1 confirm 都是 1，汇总页与组合用的完全是同一套参数、同样口径。\n")
else:
    print("⚠️ 有成员组1 的 confirm≠1：该成员在『汇总页』按其 confirm 去抖，在『组合』里被强制按 1，两处数字会不同。")
    print("   如需一致：在面板把该成员参数重存一次（确认周数旋钮已删、保存即写回 confirm=1）。\n")
