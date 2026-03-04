#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略39 - 成交量加权价格突破策略
原理：
    结合成交量和价格突破，当价格突破关键价位且成交量放大时，
    确认趋势的真实性，避免假突破。

参数：
    - 合约：SHFE.rb2505
    - 周期：30分钟
    - 成交量均线：20
    - 成交量倍数：1.5
    - 止损：2%

适用行情：趋势确认后的顺势交易
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 30 * 60        # 30分钟K线
VOL_MA_PERIOD = 20              # 成交量均线周期
VOL_MULTI = 1.5                 # 成交量放大倍数
STOP_LOSS = 0.02                # 2%止损
TAKE_PROFIT = 0.05              # 5%止盈

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：成交量加权价格突破策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=50)
    
    position = 0
    entry_price = 0
    high_price = 0
    low_price = float('inf')
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < VOL_MA_PERIOD + 10:
                continue
            
            current_price = klines['close'].iloc[-1]
            current_vol = klines['volume'].iloc[-1]
            
            # 计算成交量均线
            vol_ma = klines['volume'].iloc[-VOL_MA_PERIOD:].mean()
            
            # 计算20日高低点
            high_20 = klines['high'].iloc[-20:].max()
            low_20 = klines['low'].iloc[-20:].min()
            
            # 突破买入信号
            if position == 0:
                # 突破20日高点且成交量放大
                if current_price > high_20 and current_vol > vol_ma * VOL_MULTI:
                    position = 1
                    entry_price = current_price
                    high_price = high_20
                    print(f"[买入突破] 价格: {current_price}, 成交量: {current_vol:.0f}, 放量{current_vol/vol_ma:.1f}倍")
                # 跌破20日低点且成交量放大
                elif current_price < low_20 and current_vol > vol_ma * VOL_MULTI:
                    position = -1
                    entry_price = current_price
                    low_price = low_20
                    print(f"[卖出突破] 价格: {current_price}, 成交量: {current_vol:.0f}, 放量{current_vol/vol_ma:.1f}倍")
                    
            elif position == 1:
                pnl_pct = (current_price - entry_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}, 亏损{pnl_pct*100:.1f}%")
                    position = 0
                elif pnl_pct > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}, 盈利{pnl_pct*100:.1f}%")
                    position = 0
                    
            elif position == -1:
                pnl_pct = (entry_price - current_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}, 亏损{pnl_pct*100:.1f}%")
                    position = 0
                elif pnl_pct > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}, 盈利{pnl_pct*100:.1f}%")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
