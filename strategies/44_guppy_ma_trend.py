#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略44 - 顾比均线复合趋势策略
原理：
    采用顾比均线（Guppy Multiple Moving Average）思想，
    使用短期均线组（6条）和长期均线组（6条）判断趋势。
    当短期组上穿长期组时做多，下穿时做空。

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - 短期均线：3,5,8,10,12,15
    - 长期均线：30,35,40,45,50,60
    - 止损：2%

适用行情：趋势行情
作者：ringoshinnytech / tqsdk-strategies
日期：2026-03-11
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 15 * 60        # 15分钟K线
SHORT_PERIODS = [3, 5, 8, 10, 12, 15]   # 短期均线组
LONG_PERIODS = [30, 35, 40, 45, 50, 60] # 长期均线组
STOP_LOSS = 0.02                # 2%止损
TAKE_PROFIT = 0.04              # 4%止盈

# ============ 均线计算 ============
def calc_ma(closes, period):
    """计算简单移动平均"""
    if len(closes) < period:
        return None
    return np.mean(closes[-period:])

def calc_guppy_group(closes, periods):
    """计算顾比均线组"""
    values = []
    for p in periods:
        ma = calc_ma(closes, p)
        if ma is not None:
            values.append(ma)
    return values

def guppy_trend(closes, short_periods, long_periods):
    """判断顾比均线趋势"""
    short_group = calc_guppy_group(closes, short_periods)
    long_group = calc_guppy_group(closes, long_periods)
    
    if not short_group or not long_group:
        return 0
    
    short_ma = np.mean(short_group)
    long_ma = np.mean(long_group)
    
    # 多头排列
    if short_ma > long_ma:
        return 1
    # 空头排列
    elif short_ma < long_ma:
        return -1
    return 0

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：顾比均线复合趋势策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < 70:
                continue
            
            closes = klines['close'].values
            
            # 计算均线趋势
            trend = guppy_trend(closes, SHORT_PERIODS, LONG_PERIODS)
            
            current_price = closes[-1]
            
            # 计算短期均线用于更精细的入场
            short_ma_5 = calc_ma(closes, 5)
            short_ma_10 = calc_ma(closes, 10)
            
            if short_ma_5 and short_ma_10:
                print(f"价格: {current_price:.2f}, 短期均线: {short_ma_5:.2f}, 趋势: {'多头' if trend==1 else '空头' if trend==-1 else '震荡'}")
            
            # 买入信号：趋势转多
            if position == 0 and trend == 1:
                position = 1
                entry_price = current_price
                print(f"买入开仓，价格：{entry_price}")
            
            # 卖出信号：趋势转空
            elif position == 0 and trend == -1:
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
