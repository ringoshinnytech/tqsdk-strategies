#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dual Thrust 日内突破策略
=========================

策略简介：
    经典日内突破策略，每日根据过去 N 日高低收价计算上下轨：
        Range    = max(HH - LC, HC - LL)
        上轨     = 今日开盘价 + K1 × Range
        下轨     = 今日开盘价 - K2 × Range
    价格突破上轨做多，跌破下轨做空，收盘前强制平仓。

【为什么使用 TargetPosTask】
    日内策略需要频繁调整仓位（突破→平仓→反手），TargetPosTask 自动
    处理追单/撤单/部分成交，策略只需关注目标仓位数字。
    收盘平仓只需 set_target_volume(0) 即可。

参数说明：
    SYMBOL    : 交易合约代码
    N_DAYS    : 回溯天数，用于计算 Range
    K1        : 上轨系数
    K2        : 下轨系数
    VOLUME    : 持仓手数
    CLOSE_HOUR/MINUTE: 日内强制平仓时刻

依赖：pip install tqsdk -U
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from datetime import time
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ===================== 策略参数 =====================
SYMBOL = "SHFE.cu2501"
N_DAYS = 4
K1 = 0.5
K2 = 0.5
VOLUME = 1
CLOSE_HOUR = 14
CLOSE_MINUTE = 50
# ===================================================

def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    daily_klines = api.get_kline_serial(SYMBOL, 86400, data_length=N_DAYS + 2)
    quote = api.get_quote(SYMBOL)

    # TargetPosTask：声明目标仓位，自动处理下单细节
    target_pos = TargetPosTask(api, SYMBOL)

    today_date = None
    buy_line = sell_line = None

    print(f"[Dual Thrust] 启动 | {SYMBOL} | N={N_DAYS} | K1={K1} | K2={K2}")

    while True:
        api.wait_update()

        if not quote.datetime:
            continue

        current_date = quote.datetime[:10]

        # 新交易日：重新计算轨道
        if current_date != today_date:
            today_date = current_date
            today_open = quote.open
            hist_high  = daily_klines.high.iloc[-(N_DAYS + 1):-1]
            hist_low   = daily_klines.low.iloc[-(N_DAYS + 1):-1]
            hist_close = daily_klines.close.iloc[-(N_DAYS + 1):-1]
            hh = hist_high.max()
            ll = hist_low.min()
            lc = hist_close.min()
            hc = hist_close.max()
            price_range = max(hh - lc, hc - ll)
            buy_line  = today_open + K1 * price_range   # 上轨
            sell_line = today_open - K2 * price_range   # 下轨
            print(f"[{today_date}] 开盘:{today_open} 上轨:{buy_line:.2f} 下轨:{sell_line:.2f}")

        if buy_line is None:
            continue

        last_price = quote.last_price
        t = time(*[int(x) for x in quote.datetime[11:19].split(":")])

        # 收盘前强制平仓
        if t >= time(CLOSE_HOUR, CLOSE_MINUTE):
            target_pos.set_target_volume(0)
            continue

        # 突破上轨 → 做多
        if last_price > buy_line:
            target_pos.set_target_volume(VOLUME)

        # 跌破下轨 → 做空
        elif last_price < sell_line:
            target_pos.set_target_volume(-VOLUME)

    api.close()

if __name__ == "__main__":
    main()
