#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海龟交易策略 (Turtle Trading Strategy) - TargetPosTask 版
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
