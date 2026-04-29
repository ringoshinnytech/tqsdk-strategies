#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均线多头排列趋势策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
均线多头排列趋势策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：短中长期均线形成多头排列时确认上升趋势，回踩后继续顺势做多。
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
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
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
