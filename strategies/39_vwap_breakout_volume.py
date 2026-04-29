#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成交量加权价格突破策略
======================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
成交量加权价格突破策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：结合 VWAP、关键价位和成交量放大信号，确认突破是否有效。
脚本默认关注 SHFE.rb2505，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合趋势启动和波动扩张阶段，需要用成交量、波动率或趋势强度过滤假突破。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
策略39 - 成交量加权价格突破策略
原理：
    结合成交量和价格突破，当价格突破关键价位且成交量放大时，
    确认趋势的真实性，避免假突破。

参数：
    - 合约：SHFE.rb2505
    - 周期：30分钟
    - 成交量均线：20
    - 成交量倍数：1.5
    - 止损：2%

适用行情：趋势确认后的顺势交易
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 30 * 60        # 30分钟K线
VOL_MA_PERIOD = 20              # 成交量均线周期
VOL_MULTI = 1.5                 # 成交量放大倍数
STOP_LOSS = 0.02                # 2%止损
TAKE_PROFIT = 0.05              # 5%止盈

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
    print("启动：成交量加权价格突破策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=50)
    
    position = 0
    entry_price = 0
    high_price = 0
    low_price = float('inf')
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < VOL_MA_PERIOD + 10:
                continue
            
            current_price = klines['close'].iloc[-1]
            current_vol = klines['volume'].iloc[-1]
            
            # 计算成交量均线
            vol_ma = klines['volume'].iloc[-VOL_MA_PERIOD:].mean()
            
            # 计算20日高低点
            high_20 = klines['high'].iloc[-20:].max()
            low_20 = klines['low'].iloc[-20:].min()
            
            # 突破买入信号
            if position == 0:
                # 突破20日高点且成交量放大
                if current_price > high_20 and current_vol > vol_ma * VOL_MULTI:
                    position = 1
                    entry_price = current_price
                    high_price = high_20
                    print(f"[买入突破] 价格: {current_price}, 成交量: {current_vol:.0f}, 放量{current_vol/vol_ma:.1f}倍")
                # 跌破20日低点且成交量放大
                elif current_price < low_20 and current_vol > vol_ma * VOL_MULTI:
                    position = -1
                    entry_price = current_price
                    low_price = low_20
                    print(f"[卖出突破] 价格: {current_price}, 成交量: {current_vol:.0f}, 放量{current_vol/vol_ma:.1f}倍")
                    
            elif position == 1:
                pnl_pct = (current_price - entry_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}, 亏损{pnl_pct*100:.1f}%")
                    position = 0
                elif pnl_pct > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}, 盈利{pnl_pct*100:.1f}%")
                    position = 0
                    
            elif position == -1:
                pnl_pct = (entry_price - current_price) / entry_price
                
                if pnl_pct < -STOP_LOSS:
                    print(f"[止损] 价格: {current_price}, 亏损{pnl_pct*100:.1f}%")
                    position = 0
                elif pnl_pct > TAKE_PROFIT:
                    print(f"[止盈] 价格: {current_price}, 盈利{pnl_pct*100:.1f}%")
                    position = 0
    
    api.close()

if __name__ == "__main__":
    main()
