#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略42 - 布林带均值回归策略
原理：
    利用布林带识别价格回归特性，当价格触及下轨获得支撑时做多，
    触及上轨遇到阻力时做空，配合RSI确认超卖超买状态。

参数：
    - 合约：SHFE.rb2505
    - 周期：30分钟
    - 布林周期：20
    - 布林倍数：2.0
    - RSI周期：14
    - 止损：1.5%

适用行情：震荡行情
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 30 * 60        # 30分钟K线
BB_PERIOD = 20                  # 布林带周期
BB_STD = 2.0                    # 布林带标准差倍数
RSI_PERIOD = 14                 # RSI周期
STOP_LOSS = 0.015              # 1.5%止损
TAKE_PROFIT = 0.03              # 3%止盈

# ============ 指标计算 ============
def calc_bollinger_bands(closes, period=20, std_dev=2.0):
    """计算布林带"""
    if len(closes) < period:
        return None, None, None
    recent = closes[-period:]
    ma = np.mean(recent)
    std = np.std(recent)
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    return upper, ma, lower

def calc_rsi(closes, period=14):
    """计算RSI"""
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：布林带均值回归策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < BB_PERIOD + RSI_PERIOD + 10:
                continue
            
            closes = klines['close'].values
            
            # 计算布林带
            upper, middle, lower = calc_bollinger_bands(closes, BB_PERIOD, BB_STD)
            if upper is None:
                continue
            
            # 计算RSI
            rsi = calc_rsi(closes, RSI_PERIOD)
            
            current_price = closes[-1]
            
            print(f"价格: {current_price:.2f}, 布林上: {upper:.2f}, 中: {middle:.2f}, 下: {lower:.2f}, RSI: {rsi:.1f}")
            
            # 买入信号：价格触及下轨且RSI超卖
            if position == 0 and current_price <= lower and rsi < 35:
                position = 1
                entry_price = current_price
                print(f"买入开仓，价格：{entry_price}")
            
            # 卖出信号：价格触及上轨且RSI超买
            elif position == 0 and current_price >= upper and rsi > 65:
                position = -1
                entry_price = current_price
                print(f"卖出开仓，价格：{entry_price}")
            
            # 止损止盈
            elif position != 0:
                pnl = (current_price - entry_price) / entry_price if position == 1 else (entry_price - current_price) / entry_price
                
                if pnl <= -STOP_LOSS:
                    print(f"止损平仓，盈亏：{pnl*100:.2f}%")
                    position = 0
                elif pnl >= TAKE_PROFIT:
                    print(f"止盈平仓，盈亏：{pnl*100:.2f}%")
                    position = 0

if __name__ == "__main__":
    main()
