#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略45 - 趋势过滤RSI震荡策略
原理：
    结合趋势指标和RSI震荡指标进行双重过滤。
    只在趋势明确的方向上进行RSI超买超卖交易，
    避免逆势交易，提高交易胜率。

参数：
    - 合约：SHFE.rb2505
    - 周期：1小时
    - 趋势周期：60（MA）
    - RSI周期：14
    - RSI超卖：30
    - RSI超买：70
    - 止损：1.5%

适用行情：趋势回调行情
作者：ringoshinnytech / tqsdk-strategies
日期：2026-03-11
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 60 * 60        # 1小时K线
TREND_PERIOD = 60               # 趋势均线周期
RSI_PERIOD = 14                 # RSI周期
RSI_OVERSOLD = 30               # RSI超卖阈值
RSI_OVERBOUGHT = 70             # RSI超买阈值
STOP_LOSS = 0.015              # 1.5%止损
TAKE_PROFIT = 0.03              # 3%止盈

# ============ 指标计算 ============
def calc_ma(closes, period):
    """计算移动平均"""
    if len(closes) < period:
        return None
    return np.mean(closes[-period:])

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
    
    print("启动：趋势过滤RSI震荡策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)
    
    position = 0
    entry_price = 0
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < TREND_PERIOD + RSI_PERIOD + 10:
                continue
            
            closes = klines['close'].values
            
            # 计算趋势均线
            trend_ma = calc_ma(closes, TREND_PERIOD)
            if trend_ma is None:
                continue
            
            # 计算RSI
            rsi = calc_rsi(closes, RSI_PERIOD)
            
            current_price = closes[-1]
            
            # 判断趋势方向
            trend_up = current_price > trend_ma
            trend_down = current_price < trend_ma
            
            print(f"价格: {current_price:.2f}, 趋势线: {trend_ma:.2f}, RSI: {rsi:.1f}, 趋势: {'上涨' if trend_up else '下跌' if trend_down else '震荡'}")
            
            # 买入信号：上升趋势中RSI超卖
            if position == 0 and trend_up and rsi < RSI_OVERSOLD:
                position = 1
                entry_price = current_price
                print(f"买入开仓（回调），价格：{entry_price}")
            
            # 卖出信号：下跌趋势中RSI超买
            elif position == 0 and trend_down and rsi > RSI_OVERBOUGHT:
                position = -1
                entry_price = current_price
                print(f"卖出开仓（反弹），价格：{entry_price}")
            
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
