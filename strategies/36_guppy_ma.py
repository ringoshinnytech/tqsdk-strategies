#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略36 - 顾比均线复合策略
原理：
    顾比均线（Guppy Multiple Moving Average）由两组均线组成：
    短期组（3、5、8、10、12、15）和长期组（30、35、40、45、50、60）。
    短期组上穿长期组做多，下穿做空。

参数：
    - 合约：SHFE.rb2505
    - 周期：15分钟
    - 短期均线：3,5,8,10,12,15
    - 长期均线：30,35,40,45,50,60
    - 止损：3%

适用行情：趋势行情
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
from tqsdk.ta import MA
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 15 * 60        # 15分钟K线
SHORT_PERIODS = [3, 5, 8, 10, 12, 15]
LONG_PERIODS = [30, 35, 40, 45, 50, 60]
STOP_LOSS = 0.03                # 3%止损

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print("启动：顾比均线复合策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < 60:
                continue
                
            # 计算短期组均线均值
            short_ma = []
            for p in SHORT_PERIODS:
                ma = MA(klines, p)
                short_ma.append(ma.iloc[-1])
            short_avg = np.mean(short_ma)
            
            # 计算长期组均线均值
            long_ma = []
            for p in LONG_PERIODS:
                ma = MA(klines, p)
                long_ma.append(ma.iloc[-1])
            long_avg = np.mean(long_ma)
            
            current_price = klines['close'].iloc[-1]
            
            print(f"价格: {current_price}, 短期组均值: {short_avg:.2f}, 长期组均值: {long_avg:.2f}")
            
            if position == 0:
                # 短期上穿长期，做多
                if short_avg > long_avg:
                    position = 1
                    entry_price = current_price
                    print(f"[买入] 短期组上穿长期组, 价格: {current_price}")
                    
            elif position == 1:
                # 短期下穿长期，平仓
                if short_avg < long_avg:
                    print(f"[平仓] 短期组下穿长期组, 价格: {current_price}")
                    position = 0
                # 止损检查
                elif current_price < entry_price * (1 - STOP_LOSS):
                    print(f"[止损] 价格: {current_price}")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
