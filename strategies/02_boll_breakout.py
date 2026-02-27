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
        - 价格向上突破上轨：趋势突破信号，开多头
        - 价格向下突破下轨：趋势突破信号，开空头
        - 价格回到中轨附近（±中轨10%区间）：趋势减弱，平仓离场

    布林带宽度（带宽）= (上轨 - 下轨) / 中轨
        带宽越大 → 市场波动越大 → 突破信号越有效

适用场景：
    - 适合趋势明显的品种和周期
    - 建议在带宽较大时才入场，避免震荡市中频繁被套

参数说明：
    SYMBOL   : 交易合约代码
    N_PERIOD : 布林带计算周期（K线根数），常用值 20
    K_TIMES  : 标准差倍数，控制上下轨宽度，常用值 2.0
    KLINE_DUR: K线周期（秒）
    VOLUME   : 每次开仓手数
    MIN_BAND_WIDTH: 最小带宽比例，低于此值不入场（过滤震荡市）

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma, std

# ===================== 策略参数 =====================
SYMBOL = "DCE.m2501"        # 交易合约：大商所豆粕2501合约
N_PERIOD = 20               # 布林带周期：20根K线
K_TIMES = 2.0               # 标准差倍数：上下轨距中轨2倍标准差
KLINE_DUR = 60 * 60         # K线周期：1小时
VOLUME = 1                  # 每次开仓手数
MIN_BAND_WIDTH = 0.01       # 最小带宽比例：1%，低于此值不交易（过滤低波动震荡期）
# ===================================================


def main():
    """布林带突破策略主函数"""

    # 初始化 API（模拟账户）
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅 K 线，数据长度需大于布林带计算周期
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=N_PERIOD + 10)

    # 获取持仓对象引用
    position = api.get_position(SYMBOL)

    print(f"[策略启动] 布林带突破策略 | 合约: {SYMBOL} | 周期: {N_PERIOD} | 倍数: {K_TIMES}")

    while True:
        api.wait_update()

        # 只在 K 线更新时重算指标
        if not api.is_changing(klines):
            continue

        # ---- 计算布林带指标 ----
        close = klines.close

        middle = ma(close, N_PERIOD)               # 中轨：N周期简单移动平均
        std_dev = std(close, N_PERIOD)             # N周期标准差
        upper = middle + K_TIMES * std_dev         # 上轨
        lower = middle - K_TIMES * std_dev         # 下轨

        # 取最新（最后一根K线）的各指标值
        last_close = close.iloc[-1]
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]
        last_middle = middle.iloc[-1]

        # 带宽（归一化）：衡量当前市场波动程度
        band_width = (last_upper - last_lower) / last_middle

        # 当前净持仓
        net_pos = position.volume_long - position.volume_short

        print(
            f"价格: {last_close:.2f} | 上轨: {last_upper:.2f} | "
            f"中轨: {last_middle:.2f} | 下轨: {last_lower:.2f} | "
            f"带宽: {band_width:.3f} | 净持仓: {net_pos}"
        )

        # ---- 带宽过滤：波动太小则跳过，避免震荡市假突破 ----
        if band_width < MIN_BAND_WIDTH:
            print(f"  [过滤] 当前带宽 {band_width:.3f} < 最小带宽 {MIN_BAND_WIDTH}，不交易")
            continue

        # ---- 交易信号：突破上轨 → 做多 ----
        if last_close > last_upper and net_pos <= 0:
            print(">>> 上轨突破！做多开仓")

            # 先平空头（若有）
            if net_pos < 0:
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",
                    offset="CLOSE",
                    volume=abs(net_pos)
                )

            # 开多头
            api.insert_order(
                symbol=SYMBOL,
                direction="BUY",
                offset="OPEN",
                volume=VOLUME
            )

        # ---- 交易信号：跌破下轨 → 做空 ----
        elif last_close < last_lower and net_pos >= 0:
            print(">>> 下轨跌破！做空开仓")

            # 先平多头（若有）
            if net_pos > 0:
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",
                    offset="CLOSE",
                    volume=net_pos
                )

            # 开空头
            api.insert_order(
                symbol=SYMBOL,
                direction="SELL",
                offset="OPEN",
                volume=VOLUME
            )

        # ---- 平仓信号：价格回归中轨 → 离场 ----
        # 持多头且价格回落到中轨以下
        elif net_pos > 0 and last_close < last_middle:
            print(">>> 价格回归中轨，平多离场")
            api.insert_order(
                symbol=SYMBOL,
                direction="SELL",
                offset="CLOSE",
                volume=net_pos
            )

        # 持空头且价格反弹到中轨以上
        elif net_pos < 0 and last_close > last_middle:
            print(">>> 价格回归中轨，平空离场")
            api.insert_order(
                symbol=SYMBOL,
                direction="BUY",
                offset="CLOSE",
                volume=abs(net_pos)
            )

    api.close()


if __name__ == "__main__":
    main()
