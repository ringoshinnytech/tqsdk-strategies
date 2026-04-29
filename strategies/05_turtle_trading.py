#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海龟交易策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
海龟交易策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：唐奇安通道突破 + ATR 仓位管理
脚本默认关注 INE.sc2501，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合方向持续的行情，在横盘震荡中容易反复进出，需要结合风控和周期过滤使用。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
 (Turtle Trading Strategy) - TargetPosTask 版
==========================================================

策略逻辑：
    基于唐奇安通道（Donchian Channel）的经典趋势跟踪策略：
        入场：价格创 N1 日新高 → 做多；创 N1 日新低 → 做空
        出场：价格回落至 N2 日新低（多头）或 N2 日新高（空头）→ 平仓

    仓位管理（ATR 波动率）：
        每手风险额 = ATR × 合约乘数
        开仓手数   = (账户净值 × RISK_RATIO) / 每手风险额

【为什么使用 TargetPosTask】
    TargetPosTask 自动处理追单/撤单/部分成交，仓位管理计算出目标手数后
    直接 set_target_volume 即可，不必跟踪每笔委托的状态。

参数说明：
    SYMBOL             : 交易合约代码
    N1                 : 入场通道周期（20日）
    N2                 : 出场通道周期（10日，应 < N1）
    ATR_PERIOD         : ATR 计算周期
    RISK_RATIO         : 单笔风险占账户净值比例
    CONTRACT_MULTIPLIER: 合约乘数
    MAX_VOLUME         : 最大持仓手数上限

依赖：pip install tqsdk -U
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ===================== 策略参数 =====================
SYMBOL = "INE.sc2501"
N1 = 20
N2 = 10
ATR_PERIOD = 20
RISK_RATIO = 0.01
CONTRACT_MULTIPLIER = 1000
MAX_VOLUME = 10
KLINE_DUR = 86400
# ===================================================

def calc_atr(klines: pd.DataFrame, period: int) -> pd.Series:
    """计算 ATR（Wilder 平滑）"""
    high, low, close = klines.high, klines.low, klines.close
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()

def calc_volume(account, atr_val: float) -> int:
    """ATR 仓位管理：根据账户净值和波动率计算建议手数"""
    if atr_val <= 0:
        return 1
    vol = int(account.balance * RISK_RATIO / (atr_val * CONTRACT_MULTIPLIER))
    return max(1, min(vol, MAX_VOLUME))

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=N1 + 5)
    account = api.get_account()

    # TargetPosTask：声明目标仓位，自动处理下单细节
    target_pos = TargetPosTask(api, SYMBOL)

    print(f"[海龟策略] 启动 | {SYMBOL} | 入场N1={N1} | 出场N2={N2}")

    while True:
        api.wait_update()
        if not api.is_changing(klines):
            continue

        atr_val = calc_atr(klines, ATR_PERIOD).iloc[-1]
        if pd.isna(atr_val) or atr_val <= 0:
            continue

        # 使用已完成K线计算通道（-2为最新完成K线，避免用未完成的）
        high_n1 = klines.high.iloc[-(N1 + 1):-1].max()
        low_n1  = klines.low.iloc[-(N1 + 1):-1].min()
        high_n2 = klines.high.iloc[-(N2 + 1):-1].max()
        low_n2  = klines.low.iloc[-(N2 + 1):-1].min()
        last_close = klines.close.iloc[-2]

        vol = calc_volume(account, atr_val)

        print(f"收盘:{last_close:.2f} ATR:{atr_val:.2f} N1:[{low_n1:.2f},{high_n1:.2f}] N2:[{low_n2:.2f},{high_n2:.2f}] 建议:{vol}手")

        if last_close > high_n1:
            # 突破 N1 日新高 → 做多
            print(f">>> 突破{N1}日新高，做多{vol}手")
            target_pos.set_target_volume(vol)

        elif last_close < low_n1:
            # 跌破 N1 日新低 → 做空
            print(f">>> 跌破{N1}日新低，做空{vol}手")
            target_pos.set_target_volume(-vol)

        elif last_close < low_n2:
            # 多头：跌破 N2 日新低 → 出场
            print(f">>> 跌破{N2}日新低，平多")
            target_pos.set_target_volume(0)

        elif last_close > high_n2:
            # 空头：突破 N2 日新高 → 出场
            print(f">>> 突破{N2}日新高，平空")
            target_pos.set_target_volume(0)

    api.close()

if __name__ == "__main__":
    main()
