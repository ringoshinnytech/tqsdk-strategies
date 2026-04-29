#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顾比均线复合趋势策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
顾比均线复合趋势策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：通过两组顾比均线判断短期资金与长期趋势是否共振，趋势共振时顺势交易。
脚本默认关注 SHFE.rb2505，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合方向持续的行情，在横盘震荡中容易反复进出，需要结合风控和周期过滤使用。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
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
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
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
