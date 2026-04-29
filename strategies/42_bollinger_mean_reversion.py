#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带均值回归策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
布林带均值回归策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：用布林带定位价格极端区间，并结合 RSI 过滤超买超卖状态。
脚本默认关注 SHFE.rb2505，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合震荡或偏离修复行情，遇到单边趋势时可能连续逆势亏损。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
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
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
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
