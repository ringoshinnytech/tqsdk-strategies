#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual Thrust 日内突破策略
=========================

策略简介：
    Dual Thrust 是一种经典的日内突破策略，由 Michael Chalek 开发，
    广泛应用于期货量化交易中。

策略逻辑：
    每日开盘前，根据过去 N 个交易日的高低收价格，计算当日的上下突破轨道：

        Range = max(HH - LC, HC - LL)
            HH = 过去N日的最高价（Highest High）
            LC = 过去N日对应最高价当日的收盘价（或最低收盘价）
            HC = 过去N日对应最低价当日的收盘价（或最高收盘价）
            LL = 过去N日的最低价（Lowest Low）

        上轨（BuyLine）  = 今日开盘价 + K1 × Range
        下轨（SellLine） = 今日开盘价 - K2 × Range

    交易信号（日内）：
        - 价格突破上轨 → 做多
        - 价格跌破下轨 → 做空
        - 每日收盘前平仓（日内策略，不隔夜）

参数说明：
    SYMBOL    : 交易合约代码
    N_DAYS    : 回溯天数，用于计算 Range，常用值 3~5
    K1        : 上轨系数（控制上轨距开盘价的距离），常用值 0.5
    K2        : 下轨系数（控制下轨距开盘价的距离），常用值 0.5
    VOLUME    : 每次开仓手数
    CLOSE_TIME: 每日收盘平仓时间（秒，距00:00:00）

注意：
    - Dual Thrust 是日内策略，不应隔夜持仓
    - K1=K2 时上下轨对称；K1≠K2 可创建非对称策略
    - 回溯天数 N 越大轨道越稳定，越小轨道对近期行情越敏感

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from datetime import time
from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import hhv, llv

# ===================== 策略参数 =====================
SYMBOL = "SHFE.cu2501"      # 交易合约：上期所铜2501合约
N_DAYS = 4                  # Range 计算回溯天数
K1 = 0.5                    # 上轨系数
K2 = 0.5                    # 下轨系数（通常与 K1 相同，可调整为非对称）
VOLUME = 1                  # 每次开仓手数
CLOSE_HOUR = 14             # 日内平仓时刻（小时）：14:30 前平仓（期货日盘收盘为 15:00）
CLOSE_MINUTE = 50           # 日内平仓时刻（分钟）
# ===================================================


def main():
    """Dual Thrust 日内策略主函数"""

    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅日线数据：用于计算过去 N 日的 HH/LC/HC/LL
    # 注意：日线周期为 86400 秒（24小时），期货实际为一个交易日
    daily_klines = api.get_kline_serial(SYMBOL, 86400, data_length=N_DAYS + 2)

    # 订阅分钟线：用于实时监控价格是否突破轨道
    minute_klines = api.get_kline_serial(SYMBOL, 60, data_length=2)

    # 获取行情报价（用于获取实时价格）
    quote = api.get_quote(SYMBOL)

    # 持仓引用
    position = api.get_position(SYMBOL)

    # 当日状态变量
    today_open = None       # 今日开盘价
    buy_line = None         # 上轨（多头开仓线）
    sell_line = None        # 下轨（空头开仓线）
    today_date = None       # 当前交易日期（用于检测是否换日）

    print(f"[策略启动] Dual Thrust 策略 | 合约: {SYMBOL} | N={N_DAYS} | K1={K1} | K2={K2}")

    while True:
        api.wait_update()

        # ---- 检测是否为新交易日：如果是，重新计算轨道 ----
        # quote.datetime 格式为 "YYYY-MM-DD HH:MM:SS.ffffff"
        if quote.datetime:
            current_date = quote.datetime[:10]  # 取日期部分 "YYYY-MM-DD"
        else:
            continue

        if current_date != today_date:
            # 新的交易日：计算当日的 Range 和上下轨
            today_date = current_date
            today_open = quote.open           # 今日开盘价

            # 过去 N 日（不含今日）的高低收价格序列
            hist_high = daily_klines.high.iloc[-(N_DAYS + 1):-1]
            hist_low = daily_klines.low.iloc[-(N_DAYS + 1):-1]
            hist_close = daily_klines.close.iloc[-(N_DAYS + 1):-1]

            # 计算 Dual Thrust Range
            hh = hist_high.max()              # N日最高价
            ll = hist_low.min()               # N日最低价
            lc = hist_close.min()             # N日最低收盘价
            hc = hist_close.max()             # N日最高收盘价

            # Range = max(最高价 - 最低收盘价, 最高收盘价 - 最低价)
            price_range = max(hh - lc, hc - ll)

            # 计算当日上下轨
            buy_line = today_open + K1 * price_range
            sell_line = today_open - K2 * price_range

            print(
                f"[新交易日 {today_date}] 开盘价: {today_open} | "
                f"Range: {price_range:.2f} | "
                f"上轨: {buy_line:.2f} | 下轨: {sell_line:.2f}"
            )

        # 轨道未计算完成则跳过
        if buy_line is None or sell_line is None:
            continue

        # ---- 获取当前价格和时间 ----
        last_price = quote.last_price
        net_pos = position.volume_long - position.volume_short

        # 解析当前时间（判断是否到收盘平仓时刻）
        current_time_str = quote.datetime[11:19] if quote.datetime else "00:00:00"
        current_time = time(*[int(x) for x in current_time_str.split(":")])
        close_time = time(CLOSE_HOUR, CLOSE_MINUTE)

        # ---- 收盘前强制平仓 ----
        if current_time >= close_time:
            if net_pos > 0:
                print(f"[收盘平仓] {current_time_str} 平多头")
                api.insert_order(SYMBOL, "SELL", "CLOSE", net_pos)
            elif net_pos < 0:
                print(f"[收盘平仓] {current_time_str} 平空头")
                api.insert_order(SYMBOL, "BUY", "CLOSE", abs(net_pos))
            continue

        # ---- 突破信号判断 ----

        # 价格突破上轨 → 做多
        if last_price > buy_line and net_pos <= 0:
            print(f">>> 突破上轨 {buy_line:.2f}！做多 | 当前价: {last_price}")

            if net_pos < 0:
                # 先平空
                api.insert_order(SYMBOL, "BUY", "CLOSE", abs(net_pos))

            api.insert_order(SYMBOL, "BUY", "OPEN", VOLUME)

        # 价格跌破下轨 → 做空
        elif last_price < sell_line and net_pos >= 0:
            print(f">>> 跌破下轨 {sell_line:.2f}！做空 | 当前价: {last_price}")

            if net_pos > 0:
                # 先平多
                api.insert_order(SYMBOL, "SELL", "CLOSE", net_pos)

            api.insert_order(SYMBOL, "SELL", "OPEN", VOLUME)

    api.close()


if __name__ == "__main__":
    main()
