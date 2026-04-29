#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSI 均值回归策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
RSI 均值回归策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：RSI<30 超卖做多、RSI>70 超买做空
脚本默认关注 CZCE.MA501，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合震荡或偏离修复行情，遇到单边趋势时可能连续逆势亏损。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
RSI 超买超卖均值回归策略 (RSI Mean Reversion Strategy)
=======================================================

策略逻辑：
    RSI（相对强弱指数）范围 0-100，用于衡量价格涨跌力量：
        RSI < 30（超卖）→ 价格跌幅过大，预期反弹 → 做多
        RSI > 70（超买）→ 价格涨幅过大，预期回落 → 做空
        RSI 回归 40~60 中性区 → 动量平衡，平仓离场

    RSI 计算（Wilder 平滑）：
        RS  = EWM平均上涨幅 / EWM平均下跌幅（alpha=1/period）
        RSI = 100 - 100 / (1 + RS)

【为什么使用 TargetPosTask】
    只需声明目标仓位，TargetPosTask 自动处理追单、撤单、部分成交等细节，
    避免手动管理订单状态的复杂性。

适用场景：震荡行情效果好；强趋势行情中慎用。

参数说明：
    SYMBOL     : 交易合约代码
    RSI_PERIOD : RSI 计算周期，默认 14
    OVERBOUGHT : 超买阈值，默认 70
    OVERSOLD   : 超卖阈值，默认 30
    KLINE_DUR  : K线周期（秒）
    VOLUME     : 持仓手数

依赖：pip install tqsdk -U
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ===================== 策略参数 =====================
SYMBOL = "CZCE.MA501"
RSI_PERIOD = 14
OVERBOUGHT = 70
OVERSOLD = 30
KLINE_DUR = 60 * 15
VOLUME = 1
# ===================================================

def calc_rsi(close_series: pd.Series, period: int) -> pd.Series:
    """计算 RSI（Wilder 平滑方法）"""
    delta = close_series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    return 100 - 100 / (1 + rs)

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=RSI_PERIOD * 3)

    # TargetPosTask：声明目标仓位，自动追单
    target_pos = TargetPosTask(api, SYMBOL)

    print(f"[RSI均值回归] 启动 | {SYMBOL} | RSI周期:{RSI_PERIOD} | 超卖:{OVERSOLD} | 超买:{OVERBOUGHT}")

    while True:
        api.wait_update()
        if not api.is_changing(klines):
            continue

        rsi_series = calc_rsi(klines.close, RSI_PERIOD)
        rsi = rsi_series.iloc[-1]
        if pd.isna(rsi):
            continue

        print(f"RSI: {rsi:.2f}")

        if rsi < OVERSOLD:
            # 超卖 → 做多
            print(f">>> RSI={rsi:.1f} 超卖，做多")
            target_pos.set_target_volume(VOLUME)

        elif rsi > OVERBOUGHT:
            # 超买 → 做空
            print(f">>> RSI={rsi:.1f} 超买，做空")
            target_pos.set_target_volume(-VOLUME)

        elif 40 < rsi < 60:
            # RSI 回归中性区，平仓
            print(f">>> RSI={rsi:.1f} 回归中性，平仓")
            target_pos.set_target_volume(0)

    api.close()

if __name__ == "__main__":
    main()
