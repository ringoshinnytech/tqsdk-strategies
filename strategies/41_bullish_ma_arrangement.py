#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略41 - 均线多头排列趋势策略
原理：
    当短期、中期、长期均线形成多头排列时，确认上升趋势，
    回踩均线时买入，持有至趋势反转。

参数：
    - 合约：SHFE.rb2505
    - 周期：30分钟
    - 短期均线：10
    - 中期均线：30
    - 长期均线：60
    - 止损：2.5%

适用行情：稳定上升趋势
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 30 * 60         # 30分钟K线
MA_SHORT = 10                    # 短期均线
MA_MID = 30                      # 中期均线  
MA_LONG = 60                     # 长期均线
STOP_LOSS = 0.025                # 2.5%止损
TAKE_PROFIT = 0.08               # 8%止盈

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：均线多头排列趋势策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < MA_LONG + 10:
                continue
            
            closes = klines['close'].values
            
            # 计算各周期均线
            ma_short = np.mean(closes[-MA_SHORT:])
            ma_mid = np.mean(closes[-MA_MID:])
            ma_long = np.mean(closes[-MA_LONG:])
            
            # 多头排列：短 > 中 > 长
            bullish_arrangement = ma_short > ma_mid > ma_long
            # 空头排列：短 < 中 < 长
            bearish_arrangement = ma_short < ma_mid < ma_long
            
            # 买入信号：多头排列且价格回踩中期均线
            if position == 0 and bullish_arrangement:
                if closes[-1] <= ma_mid * 1.01:  # 回踩均线附近
                    position = 1
                    entry_price = closes[-1]
                    print(f"买入开仓，价格：{entry_price}, MA{MA_SHORT}={ma_short:.2f}, MA{MA_MID}={ma_mid:.2f}, MA{MA_LONG}={ma_long:.2f}")
            
            # 卖出信号：空头排列
            elif position == 1 and bearish_arrangement:
                pnl = (closes[-1] - entry_price) / entry_price
                print(f"卖出平仓，价格：{closes[-1]}, 盈亏：{pnl*100:.2f}%")
                position = 0
            
            # 止损止盈
            elif position == 1:
                pnl = (closes[-1] - entry_price) / entry_price
                
                if pnl <= -STOP_LOSS:
                    print(f"止损平仓，亏损：{pnl*100:.2f}%")
                    position = 0
                elif pnl >= TAKE_PROFIT:
                    print(f"止盈平仓盈利：{pnl*100:.2f}%")
                    position = 0

if __name__ == "__main__":
    main()
