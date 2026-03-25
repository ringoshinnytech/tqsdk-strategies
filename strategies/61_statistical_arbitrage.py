#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略61：统计套利跨品种对冲策略
基于协整检验的跨品种统计套利，使用z-score均值回归交易
适用于：黑色系、化工系、农产品系等具有产业链关系的品种
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TargetPosTask

# ========== 策略参数 ==========
# 配对品种列表（可扩展）
PAIRS = [
    ("SHFE.rb205", "SHFE.hc205"),    # 螺纹钢-热卷
    ("DCE.j205", "DCE.jm205"),       # 焦煤-焦炭
    ("DCE.m205", "DCE.y205"),        # 豆粕-豆油
    ("CZCE.SR205", "CZCE.RM205"),    # 白糖-菜粕
    ("CZCE.JD205", "DCE.cs205"),     # 鸡蛋-玉米淀粉
]
ENTRY_ZSCORE = 1.5                   # 入场Z-score阈值
EXIT_ZSCORE = 0.3                   # 平仓Z-score阈值
LOOKBACK = 60                       # 计算均值与标准差的窗口
HEDGE_RATIOS = {}                   # 对冲比率（动态计算）
INIT_PORTFOLIO = 1000000

def calculate_hedge_ratio(series1, series2, window=20):
    """使用滚动协方差/方差计算动态对冲比率"""
    if len(series1) < window or len(series2) < window:
        return 1.0
    cov = series1.diff().rolling(window).cov(series2.diff())
    var = series1.diff().rolling(window).var()
    hr = (cov / var).iloc[-1]
    return float(hr) if not np.isnan(hr) else 1.0

def calculate_zscore(spread, window=60):
    """计算价差的Z-score"""
    if len(spread) < window:
        return 0.0
    mean = spread.iloc[-window:].mean()
    std = spread.iloc[-window:].std()
    current = spread.iloc[-1]
    if std == 0:
        return 0.0
    return (current - mean) / std

def get_spread(series1, series2, hedge_ratio):
    """计算价差序列"""
    return series1 - hedge_ratio * series2

# ========== 策略主体 ==========
def main():
    api = TqApi(auth=TqAuth("auto", "auto"))
    target_pos = TargetPosTask(api)

    print(f"[策略61] 统计套利跨品种对冲策略启动 | 配对数: {len(PAIRS)}")

    klines = {}
    quotes = {}
    spread_history = {pair: pd.Series(dtype=float) for pair in PAIRS}
    positions = {pair: 0 for pair in PAIRS}

    for pair in PAIRS:
        sym1, sym2 = pair
        klines[sym1] = api.get_kline_serial(sym1, 86400, data_length=LOOKBACK + 20)
        klines[sym2] = api.get_kline_serial(sym2, 86400, data_length=LOOKBACK + 20)
        quotes[sym1] = api.get_quote(sym1)
        quotes[sym2] = api.get_quote(sym2)

    print("[策略61] 等待历史数据积累...")

    while True:
        api.wait_update()

        for pair in PAIRS:
            sym1, sym2 = pair
            kl1 = klines[sym1]
            kl2 = klines[sym2]

            if len(kl1.close) < LOOKBACK or len(kl2.close) < LOOKBACK:
                continue

            s1 = pd.Series(kl1.close)
            s2 = pd.Series(kl2.close)

            # 更新对冲比率
            hr = calculate_hedge_ratio(s1, s2, window=20)
            HEDGE_RATIOS[pair] = hr

            # 计算价差
            spread = get_spread(s1, s2, hr)
            zscore = calculate_zscore(spread, window=LOOKBACK)

            price1 = quotes[sym1].last_price
            price2 = quotes[sym2].last_price

            # ========== 交易逻辑 ==========
            # zscore > ENTRY_ZSCORE: 价差偏高，做空价差（空sym1多sym2）
            # zscore < -ENTRY_ZSCORE: 价差偏低，做多价差（多sym1空sym2）
            # |zscore| < EXIT_ZSCORE: 平仓

            position_value = INIT_PORTFOLIO / len(PAIRS)
            margin1 = price1 * 10 * 0.12
            margin2 = price2 * 10 * 0.12
            lot1 = max(1, int(position_value / margin1)) if margin1 > 0 else 1
            lot2 = max(1, int(position_value * hr / margin2)) if margin2 > 0 else 1

            if zscore > ENTRY_ZSCORE and positions[pair] == 0:
                # 价差高估：空sym1多sym2
                target_pos.set_target_pos(sym1, -lot1)
                target_pos.set_target_pos(sym2, lot2)
                positions[pair] = -1
                print(f"[策略61] {pair} | Z={zscore:.2f} | 做空价差 | HR={hr:.3f}")

            elif zscore < -ENTRY_ZSCORE and positions[pair] == 0:
                # 价差低估：多sym1空sym2
                target_pos.set_target_pos(sym1, lot1)
                target_pos.set_target_pos(sym2, -lot2)
                positions[pair] = 1
                print(f"[策略61] {pair} | Z={zscore:.2f} | 做多价差 | HR={hr:.3f}")

            elif abs(zscore) < EXIT_ZSCORE and positions[pair] != 0:
                # 回归均值：平仓
                target_pos.set_target_pos(sym1, 0)
                target_pos.set_target_pos(sym2, 0)
                print(f"[策略61] {pair} | Z={zscore:.2f} | 平仓 | 收益锁定")
                positions[pair] = 0

    api.close()

if __name__ == "__main__":
    main()
