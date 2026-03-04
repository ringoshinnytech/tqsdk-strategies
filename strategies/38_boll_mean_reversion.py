#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略38 - 布林带均值回归策略
原理：
    利用布林带识别价格极端区域，当价格触及下轨时做多，
    触及上轨时做空，等待价格回归中轨时平仓。

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - 布林带周期：20
    - 标准差倍数：2.0
    - 止损：1.5%

适用行情：震荡行情
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import BOLL
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 15 * 60        # 15分钟K线
BOLL_PERIOD = 20                # 布林带周期
BOLL_STD = 2.0                  # 标准差倍数
STOP_LOSS = 0.015               # 1.5%止损

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：布林带均值回归策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=BOLL_PERIOD + 20)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < BOLL_PERIOD + 5:
                continue
            
            boll = BOLL(klines, BOLL_PERIOD, BOLL_STD)
            upper = boll['upper'].iloc[-1]
            middle = boll['middle'].iloc[-1]
            lower = boll['lower'].iloc[-1]
            current_price = klines['close'].iloc[-1]
            
            print(f"价格: {current_price}, 上轨: {upper:.2f}, 中轨: {middle:.2f}, 下轨: {lower:.2f}")
            
            if position == 0:
                # 触及下轨做多
                if current_price <= lower:
                    position = 1
                    entry_price = current_price
                    print(f"[买入] 价格: {current_price}, 触及下轨")
                # 触及上轨做空
                elif current_price >= upper:
                    position = -1
                    entry_price = current_price
                    print(f"[卖出] 价格: {current_price}, 触及上轨")
                    
            elif position == 1:
                pnl_pct = (current_price - entry_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif current_price >= middle:
                    print(f"[平仓] 回归中轨")
                    position = 0
                    
            elif position == -1:
                pnl_pct = (entry_price - current_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}")
                    position = 0
                elif current_price <= middle:
                    print(f"[平仓] 回归中轨")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
