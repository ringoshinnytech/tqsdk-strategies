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
布林带均值回归策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：价格触及布林带下轨做多、触及上轨做空，等待价格回到中轨附近平仓。
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
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
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
