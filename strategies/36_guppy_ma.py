#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顾比均线复合策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
顾比均线复合策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：用短期均线组和长期均线组判断趋势状态，短期组强于长期组时偏多，弱于长期组时偏空。
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
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
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
