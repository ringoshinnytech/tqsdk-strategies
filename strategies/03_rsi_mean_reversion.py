#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSI 超买超卖均值回归策略 (RSI Mean Reversion Strategy)
=======================================================

策略逻辑：
    RSI（相对强弱指数）是衡量价格上涨和下跌力量的动量指标，范围 0-100：
        - RSI > 70（超买区）：价格涨幅过大，可能回落 → 做空
        - RSI < 30（超卖区）：价格跌幅过大，可能反弹 → 做多
        - RSI 回到 50 附近：动量趋于平衡 → 平仓

    RSI 计算方式（Wilder 平滑方法）：
        RS  = 平均上涨幅度 / 平均下跌幅度（N周期 EMA 平滑）
        RSI = 100 - 100 / (1 + RS)

    使用 tqsdk 的 sma() 函数实现 Wilder 平滑（等价于 EMA(2/(N+1))）

适用场景：
    - 震荡行情、区间振荡的品种效果好
    - 强趋势行情中 RSI 容易持续超买/超卖，不适合单独使用

参数说明：
    SYMBOL      : 交易合约代码
    RSI_PERIOD  : RSI 计算周期，常用值 14
    OVERBOUGHT  : 超买阈值（默认 70），超过此值做空
    OVERSOLD    : 超卖阈值（默认 30），低于此值做多
    EXIT_LEVEL  : 平仓阈值（默认 50），RSI 回到此区间平仓
    KLINE_DUR   : K线周期（秒）
    VOLUME      : 每次开仓手数

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim

# ===================== 策略参数 =====================
SYMBOL = "CZCE.MA501"       # 交易合约：郑商所甲醇2501合约
RSI_PERIOD = 14             # RSI 计算周期
OVERBOUGHT = 70             # 超买线：RSI > 70 做空
OVERSOLD = 30               # 超卖线：RSI < 30 做多
EXIT_LEVEL = 50             # 平仓线：RSI 回到 50 附近时离场
KLINE_DUR = 60 * 15         # K线周期：15分钟
VOLUME = 1                  # 每次开仓手数
# ===================================================


def calc_rsi(close_series: pd.Series, period: int) -> pd.Series:
    """
    计算 RSI（相对强弱指数）

    使用 Wilder 平滑方法（与 TradingView / 文华财经等平台一致）：
        1. 计算每根 K 线的涨跌幅
        2. 用指数加权平均平滑上涨均值和下跌均值
        3. RSI = 100 - 100 / (1 + RS)

    Args:
        close_series: 收盘价序列（pandas.Series）
        period:       RSI 计算周期

    Returns:
        pandas.Series：RSI 值序列，范围 [0, 100]
    """
    # 计算相邻两根K线的价格变动量
    delta = close_series.diff()

    # 分离上涨幅度（gain）和下跌幅度（loss）
    gain = delta.clip(lower=0)   # 上涨：保留正数，负数变0
    loss = -delta.clip(upper=0)  # 下跌：保留正数（取绝对值），正数变0

    # 使用指数加权平均（EWM）平滑，alpha = 1/period（Wilder 方法）
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    # 避免除以零（当 avg_loss=0 时，RSI=100）
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    rsi = 100 - 100 / (1 + rs)

    return rsi


def main():
    """RSI 均值回归策略主函数"""

    # 初始化 API（模拟账户）
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅 K 线，数据长度需足够计算 RSI（至少 period×2 根）
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=RSI_PERIOD * 3)

    # 持仓引用
    position = api.get_position(SYMBOL)

    print(
        f"[策略启动] RSI 均值回归策略 | 合约: {SYMBOL} | "
        f"RSI周期: {RSI_PERIOD} | 超买: {OVERBOUGHT} | 超卖: {OVERSOLD}"
    )

    while True:
        api.wait_update()

        # 只在 K 线数据更新时计算
        if not api.is_changing(klines):
            continue

        # ---- 计算 RSI ----
        rsi_series = calc_rsi(klines.close, RSI_PERIOD)
        rsi_value = rsi_series.iloc[-1]   # 最新 RSI 值

        if pd.isna(rsi_value):
            # 数据不足时跳过（RSI 初始几根K线为 NaN）
            continue

        # 当前净持仓
        net_pos = position.volume_long - position.volume_short

        print(f"RSI: {rsi_value:.2f} | 净持仓: {net_pos}")

        # ---- 交易信号判断 ----

        # 超卖 → 做多（均值回归：价格跌过头了，预计反弹）
        if rsi_value < OVERSOLD and net_pos <= 0:
            print(f">>> RSI={rsi_value:.1f} 超卖！做多开仓")

            if net_pos < 0:
                # 先平空头
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",
                    offset="CLOSE",
                    volume=abs(net_pos)
                )

            api.insert_order(
                symbol=SYMBOL,
                direction="BUY",
                offset="OPEN",
                volume=VOLUME
            )

        # 超买 → 做空（均值回归：价格涨过头了，预计回落）
        elif rsi_value > OVERBOUGHT and net_pos >= 0:
            print(f">>> RSI={rsi_value:.1f} 超买！做空开仓")

            if net_pos > 0:
                # 先平多头
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",
                    offset="CLOSE",
                    volume=net_pos
                )

            api.insert_order(
                symbol=SYMBOL,
                direction="SELL",
                offset="OPEN",
                volume=VOLUME
            )

        # RSI 回到中性区（40~60）→ 信号消失，平仓离场
        elif 40 < rsi_value < 60:

            if net_pos > 0:
                print(f">>> RSI={rsi_value:.1f} 回归中性，平多离场")
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",
                    offset="CLOSE",
                    volume=net_pos
                )

            elif net_pos < 0:
                print(f">>> RSI={rsi_value:.1f} 回归中性，平空离场")
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",
                    offset="CLOSE",
                    volume=abs(net_pos)
                )

    api.close()


if __name__ == "__main__":
    main()
