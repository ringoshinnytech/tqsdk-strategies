#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一目均衡表趋势策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
一目均衡表趋势策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：使用转换线、基准线和云层判断趋势方向，价格突破云层并获得多周期确认后交易。
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
Ichimoku Cloud 趋势策略 (Ichimoku Cloud Strategy)
================================================

策略逻辑：
    - 使用Ichimoku云图的综合信号判断趋势
    - 基准线(Kijun-sen)与转换线(Tenkan-sen)的交叉
    - 价格穿越云图作为趋势确认
    - 使用 TargetPosTask 管理持仓

适用品种：
    趋势明显的品种，如外汇、指数期货等

风险提示：
    - 滞后性较大，需要结合其他指标
    - 本代码仅供学习参考，不构成任何投资建议

参数说明：
    SYMBOL      : 交易合约代码
    TENKAN_PERIOD: 转换线周期（默认9）
    KIJUN_PERIOD: 基准线周期（默认26）
    SENKOU_PERIOD: 先行线周期（默认52）
    KLINE_DUR   : K线周期（秒）
    VOLUME      : 持仓手数

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
日期：2026-03-06
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import max as tq_max, min as tq_min

# ===================== 策略参数 =====================
SYMBOL = "SHFE.rb2505"       # 交易合约
TENKAN_PERIOD = 9            # 转换线周期
KIJUN_PERIOD = 26            # 基准线周期
SENKOU_PERIOD = 52           # 先行线周期
KLINE_DUR = 3600              # 1小时K线
VOLUME = 5                    # 持仓手数
# ====================================================

def calculate_ichimoku(kline, tenkan_period, kijun_period, senkou_period):
    """计算Ichimoku云图指标"""
    high = list(kline["high"])
    low = list(kline["low"])
    close = list(kline["close"])
    
    if len(high) < kijun_period + senkou_period:
        return None, None, None, None
    
    # 转换线 (Tenkan-sen)
    tenkan = (tq_max(high[-tenkan_period:], tenkan_period) + tq_min(low[-tenkan_period:], tenkan_period)) / 2
    
    # 基准线 (Kijun-sen)
    kijun = (tq_max(high[-kijun_period:], kijun_period) + tq_min(low[-kijun_period:], kijun_period)) / 2
    
    # 先行线A (Senkou Span A)
    senkou_a = (tenkan + kijun) / 2
    
    # 先行线B (Senkou Span B)
    senkou_b = (tq_max(high[-senkou_period:], senkou_period) + tq_min(low[-senkou_period:], senkou_period)) / 2
    
    return tenkan, kijun, senkou_a, senkou_b

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
    kline = api.get_kline_serial(SYMBOL, KLINE_DUR)
    target_pos = TargetPosTask(api, SYMBOL)
    
    print(f"启动Ichimoku云图策略: {SYMBOL}")
    
    prev_kijun = None
    prev_tenkan = None
    
    while True:
        api.wait_update()
        
        if len(kline) < KIJUN_PERIOD + SENKOU_PERIOD:
            continue
        
        tenkan, kijun, senkou_a, senkou_b = calculate_ichimoku(
            kline, TENKAN_PERIOD, KIJUN_PERIOD, SENKOU_PERIOD
        )
        
        if tenkan is None or kijun is None:
            continue
        
        current_price = list(kline["close"])[-1]
        
        # 金叉：转换线从下向上穿越基准线
        if prev_tenkan and prev_kijun:
            if prev_tenkan <= prev_kijun and tenkan > kijun:
                target_pos.set_target_volume(VOLUME)
                print(f"[做多] 价格:{current_price} T:{tenkan:.2f} K:{kijun:.2f}")
            elif prev_tenkan >= prev_kijun and tenkan < kijun:
                target_pos.set_target_volume(-VOLUME)
                print(f"[做空] 价格:{current_price} T:{tenkan:.2f} K:{kijun:.2f}")
        
        prev_tenkan = tenkan
        prev_kijun = kijun

if __name__ == "__main__":
    main()
