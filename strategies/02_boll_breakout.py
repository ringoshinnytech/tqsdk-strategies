#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
布林带突破策略 (Bollinger Bands Breakout Strategy)
==================================================

策略逻辑：
    布林带由中轨（N周期移动平均线）和上下轨（中轨 ± K倍标准差）组成：
        上轨 = MA(N) + K × STD(N)
        中轨 = MA(N)
        下轨 = MA(N) - K × STD(N)

    交易信号：
        - 价格向上突破上轨：趋势突破信号，做多
        - 价格向下突破下轨：趋势突破信号，做空
        - 价格回落至中轨以下（多头）或回升至中轨以上（空头）：趋势减弱，平仓

    布林带宽度（带宽）= (上轨 - 下轨) / 中轨
        带宽越大 → 市场波动越大 → 突破信号越有效

【为什么使用 TargetPosTask】
    TargetPosTask 只需声明目标仓位手数，自动处理追单、撤单、部分成交等细节，
    策略逻辑更清晰，无需手动管理订单状态。

适用场景：
    - 适合趋势明显的品种和周期
    - 建议在带宽较大时才入场，避免震荡市假突破

参数说明：
    SYMBOL        : 交易合约代码
    N_PERIOD      : 布林带计算周期（K线根数），常用值 20
    K_TIMES       : 标准差倍数，常用值 2.0
    KLINE_DUR     : K线周期（秒）
    VOLUME        : 持仓手数
    MIN_BAND_WIDTH: 最小带宽比例，低于此值不入场（过滤低波动震荡期）

依赖：pip install tqsdk -U
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ma, std

# ===================== 策略参数 =====================
SYMBOL = "DCE.m2501"
N_PERIOD = 20
K_TIMES = 2.0
KLINE_DUR = 60 * 60
VOLUME = 1
MIN_BAND_WIDTH = 0.01
# ===================================================

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=N_PERIOD + 10)

    # TargetPosTask：声明目标仓位，自动追单直到达到目标
    target_pos = TargetPosTask(api, SYMBOL)

    print(f"[布林带突破] 启动 | {SYMBOL} | 周期:{N_PERIOD} | 倍数:{K_TIMES}")

    while True:
        api.wait_update()
        if not api.is_changing(klines):
            continue

        close = klines.close
        middle = ma(close, N_PERIOD)          # 中轨
        std_dev = std(close, N_PERIOD)        # 标准差
        upper = middle + K_TIMES * std_dev    # 上轨
        lower = middle - K_TIMES * std_dev    # 下轨

        last_close  = close.iloc[-1]
        last_upper  = upper.iloc[-1]
        last_lower  = lower.iloc[-1]
        last_middle = middle.iloc[-1]
        band_width  = (last_upper - last_lower) / last_middle  # 归一化带宽

        print(f"价格:{last_close:.2f} 上轨:{last_upper:.2f} 中轨:{last_middle:.2f} 下轨:{last_lower:.2f} 带宽:{band_width:.3f}")

        # 带宽过滤：波动太小不交易，避免震荡市假突破
        if band_width < MIN_BAND_WIDTH:
            continue

        if last_close > last_upper:
            # 上轨突破 → 做多
            print(">>> 突破上轨，做多")
            target_pos.set_target_volume(VOLUME)

        elif last_close < last_lower:
            # 下轨跌破 → 做空
            print(">>> 跌破下轨，做空")
            target_pos.set_target_volume(-VOLUME)

        elif last_close < last_middle:
            # 价格跌回中轨以下，多头离场
            print(">>> 回落中轨，平多")
            target_pos.set_target_volume(0)

        elif last_close > last_middle:
            # 价格涨回中轨以上，空头离场
            print(">>> 反弹中轨，平空")
            target_pos.set_target_volume(0)

    api.close()

if __name__ == "__main__":
    main()
