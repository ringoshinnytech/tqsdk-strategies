#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VWAP 日内均值回归策略
==========================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
VWAP 日内均值回归策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：围绕日内 VWAP 衡量价格偏离，价格过度偏离后做回归交易，并在回归或尾盘时退出。
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
VWAP均值回归策略 (VWAP Mean Reversion Strategy)
================================================

策略逻辑：
    - 计算成交量加权平均价（VWAP）作为基准线
    - 当价格偏离VWAP超过一定幅度时，进行均值回归交易
    - 价格高于VWAP时做空，低于VWAP时做多
    - 使用 TargetPosTask 管理持仓

适用品种：
    日内交易活跃的品种，如股指期货、金属期货等

风险提示：
    - 趋势行情中可能出现较大亏损
    - 建议设置止损保护
    - 本代码仅供学习参考，不构成任何投资建议

参数说明：
    SYMBOL      : 交易合约代码
    VWAP_PERIOD : VWAP计算周期
    DEVIATION   : 偏离VWAP的开仓阈值（百分比）
    KLINE_DUR   : K线周期（秒）
    VOLUME      : 持仓手数

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
日期：2026-03-06
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import std, mean

# ===================== 策略参数 =====================
SYMBOL = "SHFE.rb2505"      # 交易合约
VWAP_PERIOD = 20            # VWAP计算周期
DEVIATION = 0.5             # 偏离阈值（百分比）
KLINE_DUR = 300             # 5分钟K线
VOLUME = 5                  # 持仓手数
# ====================================================

def calculate_vwap(close_list, vol_list, period):
    """计算成交量加权平均价"""
    if len(close_list) < period:
        return None
    recent_close = close_list[-period:]
    recent_vol = vol_list[-period:]
    vwap = sum(c * v for c, v in zip(recent_close, recent_vol)) / sum(recent_vol)
    return vwap

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
    kline = api.get_kline_serial(SYMBOL, KLINE_DUR)
    target_pos = TargetPosTask(api, SYMBOL)
    
    print(f"启动VWAP均值回归策略: {SYMBOL}")
    print(f"参数: VWAP周期={VWAP_PERIOD}, 偏离阈值={DEVIATION}%")
    
    while True:
        api.wait_update()
        
        if len(kline) < VWAP_PERIOD + 1:
            continue
        
        close_list = list(kline["close"])
        vol_list = list(kline["volume"])
        
        vwap = calculate_vwap(close_list, vol_list, VWAP_PERIOD)
        if vwap is None:
            continue
        
        current_price = close_list[-1]
        deviation_pct = (current_price - vwap) / vwap * 100
        
        if deviation_pct > DEVIATION:
            # 价格高于VWAP，做空
            target_pos.set_target_volume(-VOLUME)
            print(f"[卖出] 价格:{current_price:.2f} VWAP:{vwap:.2f} 偏离:{deviation_pct:.2f}%")
        elif deviation_pct < -DEVIATION:
            # 价格低于VWAP，做多
            target_pos.set_target_volume(VOLUME)
            print(f"[买入] 价格:{current_price:.2f} VWAP:{vwap:.2f} 偏离:{deviation_pct:.2f}%")
        elif abs(deviation_pct) < DEVIATION / 2:
            # 回归原点，平仓
            target_pos.set_target_volume(0)
            print(f"[平仓] 价格:{current_price:.2f} VWAP:{vwap:.2f} 偏离:{deviation_pct:.2f}%")

if __name__ == "__main__":
    main()
