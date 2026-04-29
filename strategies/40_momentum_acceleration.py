#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
趋势动量加速策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
趋势动量加速策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：在趋势已经确认后观察动量是否继续增强，捕捉趋势加速阶段。
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
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
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
