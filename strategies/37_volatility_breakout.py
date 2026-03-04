#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略37 - 波动率突破策略
原理：
    基于ATR（平均真实波幅）衡量市场波动性。
    当价格突破基于ATR计算的动态通道时顺势交易。

参数：
    - 合约：SHFE.rb2505
    - 周期：1小时
    - ATR周期：14
    - 通道倍数：2.5
    - 止损：2%

适用行情：趋势启动时
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import ATR
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 60 * 60        # 1小时K线
ATR_PERIOD = 14                 # ATR周期
CHANNEL_MULTI = 2.5             # 通道倍数
STOP_LOSS = 0.02                # 2%止损
TAKE_PROFIT = 0.04              # 4%止盈

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：波动率突破策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=50)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < ATR_PERIOD + 10:
                continue
                
            atr = ATR(klines, ATR_PERIOD).iloc[-1]
            current_price = klines['close'].iloc[-1]
            
            # 计算中轨（20日均价）
            ma20 = klines['close'].iloc[-20:].mean()
            
            # 计算上下轨
            upper = ma20 + atr * CHANNEL_MULTI
            lower = ma20 - atr * CHANNEL_MULTI
            
            print(f"价格: {current_price}, ATR: {atr:.2f}, 上轨: {upper:.2f}, 下轨: {lower:.2f}")
            
            if position == 0:
                # 突破上轨做多
                if current_price > upper:
                    position = 1
                    entry_price = current_price
                    print(f"[买入突破] 价格: {current_price}, 突破上轨")
                # 突破下轨做空
                elif current_price < lower:
                    position = -1
                    entry_price = current_price
                    print(f"[卖出突破] 价格: {current_price}, 突破下轨")
                    
            elif position == 1:
                pnl_pct = (current_price - entry_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif pnl_pct > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}")
                    position = 0
                elif current_price < ma20:
                    print(f"[平仓] 回归中轨")
                    position = 0
                    
            elif position == -1:
                pnl_pct = (entry_price - current_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif pnl_pct > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}")
                    position = 0
                elif current_price > ma20:
                    print(f"[平仓] 回归中轨")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
