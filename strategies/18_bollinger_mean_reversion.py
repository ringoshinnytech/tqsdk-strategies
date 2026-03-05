#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
策略18：布林带均值回归策略（Bollinger Band Mean Reversion）
================================================================================

【策略背景与来源】
布林带（Bollinger Bands）由John Bollinger于1980年代发明，是技术分析中
最常用的技术指标之一。布林带由中轨（移动平均线）和上下两条轨道线组成，
能够有效识别价格的相对高低位和波动率变化。当价格触及下轨时可能被低估，
触及上轨时可能被高估，这种特性使布林带非常适合用于均值回归交易。

【核心逻辑】
1. 计算布林带中轨（N周期简单移动平均）
2. 计算标准差确定上下轨（通常±2倍标准差）
3. 当价格触及下轨且RSI处于超卖状态时，做多
4. 当价格触及上轨且RSI处于超买状态时，做空
5. 当价格回归到中轨附近时平仓

【参数说明】
SYMBOL        : 交易品种
BB_PERIOD     : 布林带周期，默认20
BB_STD        : 标准差倍数，默认2.0
RSI_PERIOD    : RSI周期，默认14
RSI_OVERSOLD  : RSI超卖阈值，默认30
RSI_OVERBOUGHT: RSI超买阈值，默认70
KLINE_DURATION: K线周期（秒），默认300
VOLUME        : 每次交易手数，默认1
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ma

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.rb2505"    # 交易品种：螺纹钢主力合约
BB_PERIOD      = 20               # 布林带周期
BB_STD         = 2.0              # 标准差倍数
RSI_PERIOD     = 14               # RSI周期
RSI_OVERSOLD   = 30               # RSI超卖阈值
RSI_OVERBOUGHT = 70               # RSI超买阈值
KLINE_DURATION = 5 * 60           # K线周期：5分钟
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 200              # 历史K线数量


def calc_bollinger_bands(close, period, std_multiplier):
    """计算布林带"""
    middle = ma(close, period)                    # 中轨
    std = close.rolling(window=period).std()     # 标准差
    upper = middle + std * std_multiplier        # 上轨
    lower = middle - std * std_multiplier        # 下轨
    return upper, middle, lower


def calc_rsi(close, period):
    """计算RSI"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print(f"[布林带均值回归] 启动，品种={SYMBOL}")

    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    target_pos = TargetPosTask(api, SYMBOL)

    try:
        while True:
            api.wait_update()
            if api.is_changing(klines.iloc[-1], "datetime"):
                close = klines["close"]
                
                upper, middle, lower = calc_bollinger_bands(close, BB_PERIOD, BB_STD)
                rsi = calc_rsi(close, RSI_PERIOD)
                
                price = close.iloc[-1]
                upper_val = upper.iloc[-1]
                middle_val = middle.iloc[-1]
                lower_val = lower.iloc[-1]
                rsi_val = rsi.iloc[-1]
                
                print(f"[{klines.iloc[-1]['datetime']}] 价格={price:.2f}, "
                      f"布林={lower_val:.2f}~{middle_val:.2f}~{upper_val:.2f}, RSI={rsi_val:.1f}")
                
                # 做多：价格触及下轨且RSI超卖
                if price <= lower_val and rsi_val < RSI_OVERSOLD:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 开多仓（触及下轨，RSI超卖）")
                
                # 做空：价格触及上轨且RSI超买
                elif price >= upper_val and rsi_val > RSI_OVERBOUGHT:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 开空仓（触及上轨，RSI超买）")
                
                # 平多：价格回归到中轨
                elif price >= middle_val and target_pos.get_target_volume() > 0:
                    target_pos.set_target_volume(0)
                    print(f"  → 平多仓（回归中轨）")
                
                # 平空：价格回归到中轨
                elif price <= middle_val and target_pos.get_target_volume() < 0:
                    target_pos.set_target_volume(0)
                    print(f"  → 平空仓（回归中轨）")
    
    finally:
        api.close()
        print("[布林带均值回归策略] 已退出")


if __name__ == "__main__":
    main()
