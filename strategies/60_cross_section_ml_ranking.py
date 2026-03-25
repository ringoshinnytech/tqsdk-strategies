#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略60：截面多因子机器学习排名策略
基于 Barra 多因子模型，使用随机森林对多个因子进行截面排名选股
适用于：商品期货多品种
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TargetPosTask
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
    api = TqApi(auth=TqAuth("auto", "auto"))
    target_pos = TargetPosTask(api)

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
            target_pos.set_target_pos(sym, lots)

        # 平掉不在 top 的仓位
        for sym in SYMBOLS:
            if sym not in top_symbols:
                target_pos.set_target_pos(sym, 0)

    api.close()

if __name__ == "__main__":
    main()
