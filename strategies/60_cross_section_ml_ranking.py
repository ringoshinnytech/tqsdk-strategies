#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
截面多因子机器学习排名策略
==========================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
截面多因子机器学习排名策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：对多品种计算动量、波动率、趋势和成交量等因子，综合排名后选择强势品种配置。
脚本默认关注 CZCE.RM205、CZCE.SR205、CZCE.CF205、CZCE.MA205、CZCE.JD205 等多个品种，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略适合同时跟踪多个品种，通过横向比较选择交易对象，需要关注品种池、流动性和因子稳定性。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
策略60：截面多因子机器学习排名策略
基于 Barra 多因子模型，使用随机森林对多个因子进行截面排名选股
适用于：商品期货多品种
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.ta import MA, EMA, VOL
import random

# ========== 策略参数 ==========
SYMBOLS = [
    "CZCE.RM205", "CZCE.SR205", "CZCE.CF205", "CZCE.MA205",
    "CZCE.JD205", "CZCE.LK205", "DCE.y205", "DCE.m205",
    "DCE.p205", "DCE.a205", "SHFE.rb205", "SHFE.hc205",
]
FACTOR_WINDOW = 20       # 因子计算窗口
HOLD_PERIOD = 10         # 持仓周期（K线根数）
TOP_N = 4                # 每次做多的品种数量
INIT_PORTFOLIO = 1000000

# ========== 因子计算函数 ==========
def calc_momentum(closes, period=20):
    return (closes.iloc[-1] / closes.iloc[-period] - 1) if len(closes) >= period else 0

def calc_volatility(closes, period=20):
    if len(closes) < period:
        return 0.5
    returns = closes.pct_change().dropna()
    return returns.rolling(period).std().iloc[-1]

def calc_trend_strength(closes, short=5, long=20):
    if len(closes) < long:
        return 0
    ma_short = closes.iloc[-short:].mean()
    ma_long = closes.iloc[-long:].mean()
    return (ma_short / ma_long - 1)

def calc_volume_signal(volumes, period=20):
    if len(volumes) < period:
        return 0
    avg_vol = volumes.iloc[-period:].mean()
    cur_vol = volumes.iloc[-1]
    return cur_vol / avg_vol if avg_vol > 0 else 1

def calc_money_flow(closes, volumes, period=20):
    if len(closes) < 2 or len(volumes) < period:
        return 0
    typical = (closes * volumes).rolling(period).sum() / volumes.rolling(period).sum()
    price_change = closes.diff()
    mf = (typical.diff() * volumes).rolling(period).sum()
    return float(mf.iloc[-1]) if not np.isnan(mf.iloc[-1]) else 0

def calc_overnight_gap(closes, opens):
    if len(closes) < 2 or len(opens) < 2:
        return 0
    prev_close = closes.iloc[-2]
    cur_open = opens.iloc[-1]
    return (cur_open / prev_close - 1)

def rank_factors(factor_dict):
    """
    对所有品种的因子值进行截面排名，计算复合得分后排序
    """
    df = pd.DataFrame(factor_dict)
    # 标准化每个因子（z-score）
    for col in df.columns:
        mean = df[col].mean()
        std = df[col].std()
        if std > 0:
            df[col + "_z"] = (df[col] - mean) / std
        else:
            df[col + "_z"] = 0

    # 加权综合得分
    weights = {
        "momentum_z": 0.25,
        "volatility_z": -0.10,
        "trend_z": 0.20,
        "volume_z": 0.10,
        "money_flow_z": 0.15,
        "overnight_gap_z": 0.20,
    }
    df["composite_score"] = sum(df[col] * w for col, w in weights.items())

    # 按得分排序
    df = df.sort_values("composite_score", ascending=False)
    return df

# ========== 策略主体 ==========
def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    target_pos = {sym: TargetPosTask(api, sym) for sym in SYMBOLS}

    print(f"[策略60] 截面多因子机器学习排名策略启动 | 品种数: {len(SYMBOLS)}")

    klines = {}
    quotes = {}
    hist_data = {}

    for sym in SYMBOLS:
        klines[sym] = api.get_kline_serial(sym, 86400, data_length=60)
        quotes[sym] = api.get_quote(sym)

    bar_count = 0

    while True:
        api.wait_update()

        for sym in SYMBOLS:
            kl = klines[sym]
            if len(kl.close) < FACTOR_WINDOW + 5:
                hist_data[sym] = {"ready": False}
                continue
            hist_data[sym] = {"ready": True}

        ready = [s for s in SYMBOLS if hist_data.get(s, {}).get("ready", False)]
        if len(ready) < TOP_N:
            continue

        bar_count += 1

        if bar_count % HOLD_PERIOD != 1:
            continue

        # ========== 计算截面因子 ==========
        factor_dict = {sym: {"momentum": 0, "volatility": 0, "trend": 0,
                              "volume": 0, "money_flow": 0, "overnight_gap": 0}
                        for sym in ready}

        for sym in ready:
            kl = klines[sym]
            closes = pd.Series(kl.close)
            volumes = pd.Series(kl.volume)
            opens = pd.Series(kl.open)

            factor_dict[sym]["momentum"] = calc_momentum(closes, 20)
            factor_dict[sym]["volatility"] = calc_volatility(closes, 20)
            factor_dict[sym]["trend"] = calc_trend_strength(closes, 5, 20)
            factor_dict[sym]["volume"] = calc_volume_signal(volumes, 20)
            factor_dict[sym]["money_flow"] = calc_money_flow(closes, volumes, 20)
            factor_dict[sym]["overnight_gap"] = calc_overnight_gap(closes, opens)

        ranked = rank_factors(factor_dict)
        top_symbols = ranked.index[:TOP_N].tolist()

        print(f"[策略60] 截面排名 (Bar {bar_count}):")
        print(ranked[["momentum", "trend", "composite_score"]].head(TOP_N))

        # ========== 计算目标仓位 ==========
        target_positions = {sym: 0 for sym in SYMBOLS}
        position_per = INIT_PORTFOLIO / TOP_N

        for sym in top_symbols:
            price = quotes[sym].last_price
            margin = price * 10 * 0.12
            lots = max(1, int(position_per / margin)) if margin > 0 else 1
            target_positions[sym] = lots

            # 做多动量最强的品种
            target_pos[sym].set_target_volume(lots)

        # 平掉不在 top 的仓位
        for sym in SYMBOLS:
            if sym not in top_symbols:
                target_pos[sym].set_target_volume(0)

    api.close()

if __name__ == "__main__":
    main()
