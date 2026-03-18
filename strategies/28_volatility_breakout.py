#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
波动率动量突破策略（Volatility Momentum Breakout Strategy）
===========================================================

策略逻辑：
    结合 ATR（Average True Range）波动率突破与动量确认进行趋势跟踪。
    当价格突破「过去 N 日最高价」且 ATR 处于高位时，视为强势突破信号；
    当价格跌破「过去 N 日最低价」且 ATR 处于高位时，视为弱势突破信号。
    配合动量指标（DMI/ADX）确认趋势方向，过滤假突破。

【核心思想】
    1. 波动率放大时突破信号更可靠（量价配合原理）
    2. DMI+ADX 过滤震荡行情中的噪音信号
    3. ATR 动态止损，让利润奔跑、快速截断亏损
    4. 突破 N 日高点代表买方力量占优，突破 N 日低点代表卖方力量占优

适用品种：
    趋势性强、波动率适中的品种，如原油（INE.sc）、橡胶（RU）、棕榈油（P）等

风险提示：
    - 震荡行情中高点突破策略容易频繁止损
    - 建议配合成交量过滤使用（放量突破更可靠）
    - 本代码仅供学习参考，不构成任何投资建议

参数说明：
    SYMBOL         : 交易合约代码
    BREAKOUT_PERIOD: 突破回看周期（K线根数）
    ATR_PERIOD     : ATR 计算周期
    ADX_PERIOD     : ADX 计算周期
    ADX_THRESHOLD  : ADX 阈值（高于此值表示趋势明显）
    VOLUME         : 持仓手数
    KLINE_DUR      : K线周期（秒）

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import atr, dx
import numpy as np

# ===================== 策略参数 =====================
SYMBOL = "INE.sc2501"         # 交易合约：原油主力合约
KLINE_DUR = 60 * 60          # K线周期：3600秒 = 1小时K线
BREAKOUT_PERIOD = 20          # 突破回看周期：20根K线
ATR_PERIOD = 14               # ATR 周期
ADX_PERIOD = 14               # ADX 周期
ADX_THRESHOLD = 25            # ADX 阈值（高于此值认为趋势明显）
ATR_MULT = 1.5                # ATR 止损倍数
VOLUME = 1                    # 持仓手数
# ===================================================


def calc_adx(high, low, close, period):
    """计算 ADX（Average Directional Index）"""
    if len(high) < period + 1:
        return np.nan
    dx_vals = dx(high, low, close, period)
    adx = atr(high, low, close, period)
    if len(dx_vals) < period or adx == 0:
        return np.nan
    return np.mean(dx_vals[-period:]) / adx * 100


def main():
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    klines = api.get_kline_serial(
        SYMBOL, KLINE_DUR,
        data_length=BREAKOUT_PERIOD + ATR_PERIOD + ADX_PERIOD + 10
    )
    target_pos = TargetPosTask(api, SYMBOL)

    print(
        f"[策略启动] 波动率动量突破策略 | 合约: {SYMBOL} | "
        f"突破周期: {BREAKOUT_PERIOD} | ADX阈值: {ADX_THRESHOLD}"
    )

    position = 0  # 当前持仓方向: 1=多头, -1=空头, 0=空仓

    while True:
        api.wait_update()

        if not api.is_changing(klines):
            continue

        close = klines.close.values
        high = klines.high.values
        low = klines.low.values

        # ---- 计算指标 ----
        atr_val = atr(high, low, close, ATR_PERIOD)[-1]
        adx_val = calc_adx(high, low, close, ADX_PERIOD)

        # ---- 突破信号 ----
        highest_high = np.max(close[-BREAKOUT_PERIOD:])
        lowest_low = np.min(close[-BREAKOUT_PERIOD:])
        current_close = close[-1]

        is_breakout_up = current_close > highest_high  # 突破N日高点
        is_breakout_down = current_close < lowest_low   # 跌破N日低点

        # ---- 止损价格（ATR动态止损） ----
        stop_loss_long = current_close - ATR_MULT * atr_val
        stop_loss_short = current_close + ATR_MULT * atr_val

        # ---- 信号判断 ----
        signal = 0

        # 多头信号：突破N日高点 + ADX > 阈值（趋势明显）
        if is_breakout_up and (adx_val is not None and adx_val > ADX_THRESHOLD):
            signal = 1
            print(
                f"[突破信号] 突破N日高点 | ADX: {adx_val:.1f} | "
                f"当前价: {current_close:.2f} | ATR: {atr_val:.2f} | 止损: {stop_loss_long:.2f}"
            )

        # 空头信号：跌破N日低点 + ADX > 阈值
        if is_breakout_down and (adx_val is not None and adx_val > ADX_THRESHOLD):
            signal = -1
            print(
                f"[突破信号] 跌破N日低点 | ADX: {adx_val:.1f} | "
                f"当前价: {current_close:.2f} | ATR: {atr_val:.2f} | 止损: {stop_loss_short:.2f}"
            )

        # ---- 持仓管理 ----
        if signal == 1 and position != 1:
            print(f">>> 开多仓 | 目标: +{VOLUME}")
            target_pos.set_target_volume(VOLUME)
            position = 1

        elif signal == -1 and position != -1:
            print(f">>> 开空仓 | 目标: -{VOLUME}")
            target_pos.set_target_volume(-VOLUME)
            position = -1

        # ---- 止损检查（主动止损，不依赖信号） ----
        if position == 1 and close[-1] < stop_loss_long:
            print(f">>> ATR止损平多 | 当前价: {close[-1]:.2f} < 止损价: {stop_loss_long:.2f}")
            target_pos.set_target_volume(0)
            position = 0

        elif position == -1 and close[-1] > stop_loss_short:
            print(f">>> ATR止损平空 | 当前价: {close[-1]:.2f} > 止损价: {stop_loss_short:.2f}")
            target_pos.set_target_volume(0)
            position = 0

    api.close()


if __name__ == "__main__":
    main()
