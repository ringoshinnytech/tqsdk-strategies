#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
均线金叉死叉趋势策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
均线金叉死叉趋势策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：短期均线上穿长期均线做多，下穿长期均线做空，并结合成交量确认。
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
策略43 - 均线金叉死叉趋势策略
原理：
    使用短期和长期均线的交叉作为趋势信号。
    短期均线上穿长期均线形成金叉做多，下穿形成死叉做空。
    配合成交量确认信号有效性。

参数：
    - 合约：SHFE.rb2505
    - 周期：1小时
    - 短期均线：10
    - 长期均线：60
    - 成交量确认：1.5倍
    - 止损：2%

适用行情：趋势明显的单边行情
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth
import numpy as np

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2505"          # 螺纹钢
KLINE_DURATION = 60 * 60        # 1小时K线
FAST_MA = 10                    # 短期均线
SLOW_MA = 60                    # 长期均线
VOLUME_CONFIRM = 1.5            # 成交量确认倍数
STOP_LOSS = 0.02                # 2%止损
TAKE_PROFIT = 0.06              # 6%止盈

# ============ 主策略 ============
def main():
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
    print("启动：均线金叉死叉趋势策略")
    
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=150)
    
    position = 0
    entry_price = 0
    prev_fast_ma = None
    prev_slow_ma = None
    
    while True:
        api.wait_update()
        
        if api.is_changing(klines):
            if len(klines) < SLOW_MA + 20:
                continue
            
            closes = klines['close'].values
            volumes = klines['volume'].values
            
            # 计算均线
            fast_ma = np.mean(closes[-FAST_MA:])
            slow_ma = np.mean(closes[-SLOW_MA:])
            
            # 计算平均成交量
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            
            current_price = closes[-1]
            
            # 计算前一时刻均线位置
            if prev_fast_ma is None or prev_slow_ma is None:
                prev_fast_ma = fast_ma
                prev_slow_ma = slow_ma
                continue
            
            # 金叉：短期均线上穿长期均线
            gold_cross = prev_fast_ma <= prev_slow_ma and fast_ma > slow_ma
            # 死叉：短期均线下穿长期均线
            death_cross = prev_fast_ma >= prev_slow_ma and fast_ma < slow_ma
            
            # 成交量确认
            volume_confirmed = current_volume > avg_volume * VOLUME_CONFIRM
            
            print(f"价格: {current_price:.2f}, 快线: {fast_ma:.2f}, 慢线: {slow_ma:.2f}, 成交量: {current_volume:.0f}")
            
            # 买入信号：金叉且成交量放大
            if position == 0 and gold_cross and volume_confirmed:
                position = 1
                entry_price = current_price
                print(f"金叉买入开仓，价格：{entry_price}，成交量放大确认")
            
            # 卖出信号：死叉且成交量放大
            elif position == 0 and death_cross and volume_confirmed:
                position = -1
                entry_price = current_price
                print(f"死叉卖出开仓，价格：{entry_price}，成交量放大确认")
            
            # 止损止盈
            elif position != 0:
                pnl = (current_price - entry_price) / entry_price if position == 1 else (entry_price - current_price) / entry_price
                
                if pnl <= -STOP_LOSS:
                    print(f"止损平仓，盈亏：{pnl*100:.2f}%")
                    position = 0
                elif pnl >= TAKE_PROFIT:
                    print(f"止盈平仓，盈亏：{pnl*100:.2f}%")
                    position = 0
            
            # 更新均线状态
            prev_fast_ma = fast_ma
            prev_slow_ma = slow_ma

if __name__ == "__main__":
    main()
