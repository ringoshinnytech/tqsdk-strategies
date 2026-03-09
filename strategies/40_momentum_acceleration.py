#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略40 - 趋势动量加速策略
原理：
    结合趋势判断和动量加速指标，当趋势确认且动量加速时入场，
    捕捉趋势加速阶段的行情。

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - 趋势周期：50
    - 动量周期：14
    - 止损：2%

适用行情：趋势加速阶段
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 15 * 60         # 15分钟K线
TREND_PERIOD = 50                # 趋势判断周期
MOMENTUM_PERIOD = 14             # 动量周期
STOP_LOSS = 0.02                 # 2%止损
TAKE_PROFIT = 0.06               # 6%止盈

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：趋势动量加速策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < TREND_PERIOD + 10:
                continue
            
            closes = klines['close'].values
            highs = klines['high'].values
            lows = klines['low'].values
            
            # 计算均线判断趋势
            ma = np.mean(closes[-TREND_PERIOD:])
            trend_up = closes[-1] > ma
            
            # 计算动量
            momentum = closes[-1] - closes[-MOMENTUM_PERIOD]
            momentum_accelerating = momentum > (closes[-MOMENTUM_PERIOD] - closes[-2*MOMENTUM_PERIOD])
            
            # 买入信号
            if position == 0 and trend_up and momentum > 0 and momentum_accelerating:
                position = 1
                entry_price = closes[-1]
                print(f"买入开仓，价格：{entry_price}")
            
            # 卖出信号
            elif position == 0 and not trend_up and momentum < 0 and not momentum_accelerating:
                position = -1
                entry_price = closes[-1]
                print(f"卖出开仓，价格：{entry_price}")
            
            # 止损止盈
            elif position != 0:
                pnl = (closes[-1] - entry_price) / entry_price if position == 1 else (entry_price - closes[-1]) / entry_price
                
                if pnl <= -STOP_LOSS or pnl >= TAKE_PROFIT:
                    print(f"平仓止盈/止损，盈亏：{pnl*100:.2f}%")
                    position = 0

if __name__ == "__main__":
    main()
