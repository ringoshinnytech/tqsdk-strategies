#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多标的截面多空对冲策略
======================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
多标的截面多空对冲策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：动量因子截面排名+趋势过滤+流动性过滤，构建等权多空对冲组合剥离系统性风险
脚本默认关注 SHFE.rb2501、SHFE.hc2501、DCE.i2501、DCE.jm2501、DCE.j2501 等多个品种，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略重点观察相对强弱和价差偏离，不是单纯预测某一个品种涨跌，需要特别关注品种相关性和价差稳定性。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
策略54 - 多标的截面多空对冲策略（Multi-Asset Cross-Section Long-Short Hedge）
==============================================================================

原理：
    本策略构建一个跨多个期货品种的截面多空组合，核心思想是"强者恒强、弱者恒弱"。
    每个交易日结束时，对候选品种池按动量因子（过去20日收益率）进行截面排名：
    做多排名最靠前（前20%）的品种，做空排名最靠后（后20%）的品种。
    通过等权或风险平价加权，构建市场中性的多空对冲组合，
    剥离大盘系统性风险，获取品种间相对强弱差异的超额收益（Alpha）。

    为提高信号质量，叠加以下过滤条件：
    1. 趋势过滤：仅在20日均线方向与持仓方向一致时入场（过滤逆势）
    2. 波动率过滤：排除近20日波动率处于历史1/4分位以下的低波品种
    3. 流动性过滤：排除成交量不足前20日平均50%的低流动性品种

参数：
    - 品种池：覆盖黑色系（rb/hc/i/jm/j）、有色（cu/al/zn/pb/ni）、
              能化系（ma/pp/ta/vl）、农产品（m/y/p/cs）
    - 动量周期：20根日K
    - 换仓周期：每日收盘
    - 多空比：等权（各50%总仓位）
    - 最大持仓品种数：各不超过5个

适用行情：趋势分化明显、品种间强弱差异大的行情
风险提示：极端单边行情下多空对冲可能双向亏损
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import numpy as np
import pandas as pd
import time

# ============ 参数配置 ============
SYMBOLS = [
    "SHFE.rb2501", "SHFE.hc2501", "DCE.i2501", "DCE.jm2501", "DCE.j2501",
    "SHFE.cu2501", "SHFE.al2501", "SHFE.zn2501",
    "DCE.m2501", "DCE.y2501",
    "CZCE.MA2501", "CZCE.TA2501",
]
KLINE_DUR = 86400                    # 日K
MOM_PERIOD = 20                      # 动量计算周期
VOL_PERIOD = 20                      # 波动率计算周期
TOP_PCT = 0.20                       # 做多比例（前20%）
BOTTOM_PCT = 0.20                    # 做空比例（后20%）
LOT = 1                              # 每品种手数
# ==================================


def calc_momentum(close_prices, period):
    """计算动量：收益率"""
    if len(close_prices) < period + 1:
        return np.nan
    return (close_prices.iloc[-1] / close_prices.iloc[-period - 1]) - 1


def calc_volatility(close_prices, period):
    """计算年化波动率"""
    if len(close_prices) < period + 1:
        return np.nan
    rets = close_prices.pct_change().dropna()
    return rets.std() * np.sqrt(252)


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))

    print("=" * 60)
    print("策略54：多标的截面多空对冲策略")
    print("=" * 60)

    klines = {}
    target_pos_tasks = {}
    for sym in SYMBOLS:
        try:
            klines[sym] = api.get_kline_serial(sym, KLINE_DUR)
            target_pos_tasks[sym] = TargetPosTask(api, sym)
        except Exception as e:
            print(f"  [跳过] {sym} 无法订阅: {e}")
            continue

    print(f"已订阅 {len(klines)} 个品种")

    last_rebalance_date = None

    while True:
        api.wait_update()

        for sym, kl in klines.items():
            if api.is_changing(kl.iloc[-1], "datetime"):
                current_dt = pd.Timestamp(kl.iloc[-1]["datetime"])
                if current_dt.hour == 15:
                    if last_rebalance_date != current_dt.date():
                        last_rebalance_date = current_dt.date()
                        do_rebalance(api, klines, target_pos_tasks)
                    break

        if any(api.is_changing(kl, "close") for kl in klines.values()):
            for sym in SYMBOLS:
                pos = target_pos_tasks[sym].target_pos
                if pos != 0:
                    price = klines[sym].iloc[-1]["close"]
                    print(f"  [{sym}] 持仓: {pos} 手, 价格: {price:.2f}")

        time.sleep(5)


def do_rebalance(api, klines, target_pos_tasks):
    """执行换仓逻辑"""
    records = []

    for sym, kl in klines.items():
        if len(kl) < MOM_PERIOD + 1:
            continue
        close = kl["close"]

        mom = calc_momentum(close, MOM_PERIOD)
        vol = calc_volatility(close, VOL_PERIOD)
        ma20 = close.rolling(20).mean()
        ma_trend = (close.iloc[-1] - ma20.iloc[-2]) > 0

        records.append({
            "symbol": sym,
            "momentum": mom,
            "volatility": vol,
            "ma_trend": ma_trend,
            "volume_avg20": kl["volume"].rolling(20).mean().iloc[-1],
            "volume_current": kl["volume"].iloc[-1],
        })

    df = pd.DataFrame(records)
    df = df.dropna(subset=["momentum", "volatility"])

    if len(df) < 4:
        print("[换仓] 可用品种不足，跳过本次换仓")
        return

    df = df[df["volume_current"] >= 0.5 * df["volume_avg20"]]

    if len(df) < 4:
        print("[换仓] 流动性过滤后品种不足，跳过")
        return

    df = df.sort_values("momentum", ascending=False).reset_index(drop=True)

    n_long = max(1, int(len(df) * TOP_PCT))
    n_short = max(1, int(len(df) * BOTTOM_PCT))

    long_symbols = df.iloc[:n_long]["symbol"].tolist()
    short_symbols = df.iloc[-n_short:]["symbol"].tolist()

    print(f"\n[{pd.Timestamp.now()}] 换仓日 — 做多: {long_symbols}, 做空: {short_symbols}")

    filtered_long = [s for s in long_symbols if df[df["symbol"] == s]["ma_trend"].values[0]]
    filtered_short = [s for s in short_symbols if not df[df["symbol"] == s]["ma_trend"].values[0]]

    print(f"  趋势过滤后 — 做多: {filtered_long}, 做空: {filtered_short}")

    for sym, task in target_pos_tasks.items():
        if sym in filtered_long:
            task.set_target_volume(1)
        elif sym in filtered_short:
            task.set_target_volume(-1)
        else:
            task.set_target_volume(0)

    print("  换仓完成")


if __name__ == "__main__":
    main()
