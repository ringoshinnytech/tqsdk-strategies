#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海龟交易策略 (Turtle Trading Strategy)
========================================

策略背景：
    海龟交易法则由 Richard Dennis 和 William Eckhardt 在 1983 年设计，
    并由"海龟学员"在期货市场取得了传奇性的盈利记录。
    本策略是海龟法则的简化版本（System 1）。

策略逻辑：

    1. 趋势判断（唐奇安通道，Donchian Channel）：
        入场规则：
            - 价格创 N1 日新高（上轨突破）→ 做多
            - 价格创 N1 日新低（下轨突破）→ 做空
        出场规则：
            - 多头持仓：价格跌至 N2 日新低（N2 < N1） → 平多
            - 空头持仓：价格涨至 N2 日新高（N2 < N1） → 平空

    2. 仓位管理（ATR 波动率仓位）：
        ATR（Average True Range）= N日真实波幅均值
            True Range = max(最高-最低, |最高-昨收|, |最低-昨收|)
        每手开仓金额 = 账户净值 × RISK_RATIO
        开仓手数 = 每手开仓金额 / (ATR × 合约乘数)

    3. 加仓规则（本策略简化，未实现加仓）：
        完整海龟策略允许每突破 0.5N ATR 加仓一次，最多加仓 4 次

参数说明：
    SYMBOL    : 交易合约代码
    N1        : 入场周期（突破N1日高低点开仓），System 1 通常取 20
    N2        : 出场周期（回撤N2日高低点平仓），System 1 通常取 10
    ATR_PERIOD: ATR 计算周期，通常取 20
    RISK_RATIO: 每笔交易风险占账户净值比例（如 0.01 = 1%）
    CONTRACT_MULTIPLIER: 合约乘数（每手价值 = 价格 × 乘数）

注意：
    - 海龟策略属于趋势跟踪，在震荡市会频繁止损
    - 需要有足够的账户资金承受连续亏损（最大回撤可能较大）

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
         https://doc.shinnytech.com/tqsdk/latest/demo/strategy.html
"""

import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import hhv, llv

# ===================== 策略参数 =====================
SYMBOL = "INE.sc2501"       # 交易合约：上海能源交易所原油2501合约
N1 = 20                     # 入场唐奇安通道周期（突破20日新高/新低入场）
N2 = 10                     # 出场唐奇安通道周期（回撤10日新低/新高出场）
ATR_PERIOD = 20             # ATR 计算周期
RISK_RATIO = 0.01           # 每笔交易风险占账户净值的比例（1%）
CONTRACT_MULTIPLIER = 1000  # 合约乘数：原油期货每手1000桶
MAX_VOLUME = 10             # 最大持仓手数上限（保护设置）
KLINE_DUR = 86400           # K线周期：1天（日线）
# ===================================================


def calc_atr(klines: pd.DataFrame, period: int) -> pd.Series:
    """
    计算 ATR（Average True Range，平均真实波幅）

    True Range = max(当日最高 - 当日最低, |当日最高 - 昨日收盘|, |当日最低 - 昨日收盘|)
    ATR = N 期 True Range 的指数加权平均（Wilder 方法）

    Args:
        klines: K线 DataFrame，需包含 high/low/close 列
        period: ATR 计算周期

    Returns:
        pandas.Series：ATR 序列
    """
    high = klines.high
    low = klines.low
    close = klines.close
    prev_close = close.shift(1)  # 前一根K线的收盘价

    # 真实波幅三种情况取最大
    tr = pd.concat([
        high - low,                         # 当日最高 - 当日最低
        (high - prev_close).abs(),          # |当日最高 - 前收|
        (low - prev_close).abs(),           # |当日最低 - 前收|
    ], axis=1).max(axis=1)

    # Wilder 平滑（等价于 EWM alpha=1/period）
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return atr


def calc_position_size(account, atr_value: float) -> int:
    """
    根据账户资金和 ATR 计算开仓手数（海龟仓位管理）

    公式：
        每手风险额 = ATR × 合约乘数
        开仓手数  = (账户净值 × RISK_RATIO) / 每手风险额

    Args:
        account:   tqsdk 账户对象（含 balance 等字段）
        atr_value: 当前 ATR 值

    Returns:
        int：建议开仓手数（最小1手，最大 MAX_VOLUME）
    """
    if atr_value <= 0:
        return 1

    # 账户净值（balance = 静态权益 + 浮动盈亏）
    equity = account.balance

    # 每手风险额（价格波动一个ATR单位，单手的盈亏）
    risk_per_contract = atr_value * CONTRACT_MULTIPLIER

    # 可承受的总风险 / 每手风险 = 建议手数
    volume = int(equity * RISK_RATIO / risk_per_contract)

    # 限制在 [1, MAX_VOLUME] 范围内
    return max(1, min(volume, MAX_VOLUME))


def main():
    """海龟交易策略主函数"""

    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅日线 K 线：需要足够的历史数据用于 N1 通道计算
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=N1 + 5)

    # 账户和持仓引用
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(
        f"[策略启动] 海龟交易策略 | 合约: {SYMBOL} | "
        f"入场N1={N1} | 出场N2={N2} | ATR周期={ATR_PERIOD}"
    )

    while True:
        api.wait_update()

        # 仅在日线更新时重新计算
        if not api.is_changing(klines):
            continue

        # ---- 计算技术指标 ----
        atr_series = calc_atr(klines, ATR_PERIOD)
        atr_value = atr_series.iloc[-1]

        if pd.isna(atr_value) or atr_value <= 0:
            continue

        # 入场通道（N1日）：最近 N1 根K线（不含当前最后一根，用已完成的K线）
        # iloc[-(N1+1):-1] 取倒数 N1+1 到倒数第1根（即前 N1 根完成K线）
        high_n1 = klines.high.iloc[-(N1 + 1):-1].max()  # N1 日最高价（入场上轨）
        low_n1 = klines.low.iloc[-(N1 + 1):-1].min()    # N1 日最低价（入场下轨）

        # 出场通道（N2日）
        high_n2 = klines.high.iloc[-(N2 + 1):-1].max()  # N2 日最高价（空头出场线）
        low_n2 = klines.low.iloc[-(N2 + 1):-1].min()    # N2 日最低价（多头出场线）

        # 最新收盘价（使用已完成K线的收盘价）
        last_close = klines.close.iloc[-2]

        # 当前净持仓
        net_pos = position.volume_long - position.volume_short

        # 建议开仓手数（基于 ATR 仓位管理）
        vol = calc_position_size(account, atr_value)

        print(
            f"收盘价: {last_close:.2f} | ATR: {atr_value:.2f} | "
            f"N1通道: [{low_n1:.2f}, {high_n1:.2f}] | "
            f"N2通道: [{low_n2:.2f}, {high_n2:.2f}] | "
            f"净持仓: {net_pos} | 建议开仓: {vol}手"
        )

        # ---- 入场信号 ----

        # 价格突破 N1 日新高 → 趋势向上，做多
        if last_close > high_n1 and net_pos <= 0:
            print(f">>> 突破 {N1} 日新高 {high_n1:.2f}！做多 {vol} 手")

            if net_pos < 0:
                # 先平空头（反手做多）
                api.insert_order(SYMBOL, "BUY", "CLOSE", abs(net_pos))

            api.insert_order(SYMBOL, "BUY", "OPEN", vol)

        # 价格突破 N1 日新低 → 趋势向下，做空
        elif last_close < low_n1 and net_pos >= 0:
            print(f">>> 跌破 {N1} 日新低 {low_n1:.2f}！做空 {vol} 手")

            if net_pos > 0:
                # 先平多头（反手做空）
                api.insert_order(SYMBOL, "SELL", "CLOSE", net_pos)

            api.insert_order(SYMBOL, "SELL", "OPEN", vol)

        # ---- 出场信号（N2 通道止损/止盈） ----

        # 持多头，价格跌破 N2 日新低 → 趋势减弱，平多
        elif net_pos > 0 and last_close < low_n2:
            print(f">>> 多头跌破 {N2} 日新低 {low_n2:.2f}，平多离场")
            api.insert_order(SYMBOL, "SELL", "CLOSE", net_pos)

        # 持空头，价格突破 N2 日新高 → 趋势减弱，平空
        elif net_pos < 0 and last_close > high_n2:
            print(f">>> 空头突破 {N2} 日新高 {high_n2:.2f}，平空离场")
            api.insert_order(SYMBOL, "BUY", "CLOSE", abs(net_pos))

    api.close()


if __name__ == "__main__":
    main()
