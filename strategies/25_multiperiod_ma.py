#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多周期均线共振策略 (Multi-Timeframe Moving Average Confluence)
==============================================================

【策略背景与来源】
多周期共振是技术分析中一个重要的理念：当多个不同时间周期的指标同时指向同一方向时，
交易信号的可靠性大幅提升。这一思想由 Robert Krausz 在其著作《W.D. Gann Treasure
Discovered》中系统阐述，后被众多量化交易者采用并改进。多周期均线共振策略将日线、
小时线、分钟线三个层级的均线趋势方向结合，只有三个周期趋势一致时才入场，
从而大幅减少震荡市中的假信号，提升交易质量。

【核心逻辑】
策略同时监控三个时间周期的均线状态：

  1. 大周期（日线）：MA(20) 方向决定整体趋势
     - close > MA20_day  → 日线趋势向上
     - close < MA20_day  → 日线趋势向下

  2. 中周期（小时线）：MA(20) 方向决定中期趋势
     - close > MA20_hour → 小时线趋势向上
     - close < MA20_hour → 小时线趋势向下

  3. 小周期（15分钟线）：MA(10) 方向决定短期趋势 + 产生入场信号
     - 金叉（MA5上穿MA20）→ 短期趋势转多
     - 死叉（MA5下穿MA20）→ 短期趋势转空

共振入场条件（三重过滤）：
  做多：日线向上 AND 小时线向上 AND 15分钟金叉  → 三级共振，开多
  做空：日线向下 AND 小时线向下 AND 15分钟死叉  → 三级共振，开空

平仓条件：
  多头平仓：15分钟线出现死叉（短期趋势转弱）
  空头平仓：15分钟线出现金叉（短期趋势转强）

【计算公式】
日线趋势   = close_day[-1] vs MA(close_day, 20)[-1]
小时趋势   = close_hour[-1] vs MA(close_hour, 20)[-1]
短期信号   = crossup(MA(close_15m, 5), MA(close_15m, 20))  → 金叉做多
           = crossdown(MA(close_15m, 5), MA(close_15m, 20)) → 死叉做空

【交易信号说明】
入场（全部满足才交易）：
  开多 = 日线 close > MA20 AND 小时 close > MA20 AND 15分钟 MA5金叉MA20
  开空 = 日线 close < MA20 AND 小时 close < MA20 AND 15分钟 MA5死叉MA20

出场（任一满足即平仓）：
  平多 = 15分钟 MA5死叉MA20（短期趋势转弱）
  平空 = 15分钟 MA5金叉MA20（短期趋势转强）

【适用品种和周期】
品种：流动性好、趋势性强的品种，如沪铜（CU）、黄金（AU）、股指（IF/IC）
以15分钟为入场周期，日线+小时线为过滤周期

【优缺点分析】
优点：
  - 三重过滤大幅减少假信号，提升交易质量
  - 顺大趋势交易，盈亏比更优
  - 逻辑层次清晰，符合"从大到小"的分析框架
  - 在趋势行情中信号质量高

缺点：
  - 信号较少，可能错过部分行情
  - 需要同时订阅多个K线，消耗更多资源
  - 在三个周期方向经常不一致时，策略会长期空仓
  - 日线趋势变化慢，转折点附近可能滞后

【参数说明】
  SYMBOL       : 交易合约代码
  DAY_MA_N     : 日线均线周期，默认20日
  HOUR_MA_N    : 小时线均线周期，默认20根
  MIN15_FAST_N : 15分钟快线周期，默认5根
  MIN15_SLOW_N : 15分钟慢线周期，默认20根
  VOLUME       : 每次开仓手数
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma, crossup, crossdown

# ===================== 策略参数 =====================
SYMBOL = "SHFE.au2506"     # 交易合约：沪金2506
DAY_MA_N = 20              # 日线均线周期
HOUR_MA_N = 20             # 小时线均线周期
MIN15_FAST_N = 5           # 15分钟快线周期
MIN15_SLOW_N = 20          # 15分钟慢线周期
VOLUME = 1                 # 每次开仓手数
# ===================================================


def main():
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 同时订阅三个周期的K线数据
    klines_day  = api.get_kline_serial(SYMBOL, 86400, data_length=DAY_MA_N + 5)    # 日线
    klines_hour = api.get_kline_serial(SYMBOL, 3600,  data_length=HOUR_MA_N + 5)   # 小时线
    klines_15m  = api.get_kline_serial(SYMBOL, 900,   data_length=MIN15_SLOW_N + 5) # 15分钟线

    position = api.get_position(SYMBOL)

    print(f"[多周期共振] 启动 | {SYMBOL} | 日MA{DAY_MA_N} + 时MA{HOUR_MA_N} + 15m MA{MIN15_FAST_N}/{MIN15_SLOW_N}")

    while True:
        api.wait_update()

        # 任意一个周期K线更新时重新判断
        if not (api.is_changing(klines_day) or
                api.is_changing(klines_hour) or
                api.is_changing(klines_15m)):
            continue

        # ---- 计算各周期均线 ----
        # 日线趋势：收盘价 vs MA20
        ma_day = ma(klines_day.close, DAY_MA_N)
        day_trend_up   = klines_day.close.iloc[-2] > ma_day.iloc[-2]   # 日线趋势向上
        day_trend_down = klines_day.close.iloc[-2] < ma_day.iloc[-2]   # 日线趋势向下

        # 小时线趋势：收盘价 vs MA20
        ma_hour = ma(klines_hour.close, HOUR_MA_N)
        hour_trend_up   = klines_hour.close.iloc[-2] > ma_hour.iloc[-2]  # 小时趋势向上
        hour_trend_down = klines_hour.close.iloc[-2] < ma_hour.iloc[-2]  # 小时趋势向下

        # 15分钟线：快慢均线金叉/死叉产生入场信号
        ma_fast = ma(klines_15m.close, MIN15_FAST_N)   # 15m 快线
        ma_slow = ma(klines_15m.close, MIN15_SLOW_N)   # 15m 慢线
        cross_up   = bool(crossup(ma_fast, ma_slow).iloc[-2])    # 金叉信号
        cross_down = bool(crossdown(ma_fast, ma_slow).iloc[-2])  # 死叉信号

        # 当前净持仓
        net_pos = position.volume_long - position.volume_short

        print(
            f"日线{'↑' if day_trend_up else '↓'} | "
            f"小时{'↑' if hour_trend_up else '↓'} | "
            f"15m快线={ma_fast.iloc[-2]:.2f} 慢线={ma_slow.iloc[-2]:.2f} | "
            f"金叉={cross_up} 死叉={cross_down} | 持仓={net_pos}"
        )

        # ---- 三重共振做多 ----
        if day_trend_up and hour_trend_up and cross_up and net_pos <= 0:
            print(">>> 三周期共振向上！开多")
            if net_pos < 0:
                api.insert_order(SYMBOL, "BUY", "CLOSE", abs(net_pos))
            api.insert_order(SYMBOL, "BUY", "OPEN", VOLUME)

        # ---- 三重共振做空 ----
        elif day_trend_down and hour_trend_down and cross_down and net_pos >= 0:
            print(">>> 三周期共振向下！开空")
            if net_pos > 0:
                api.insert_order(SYMBOL, "SELL", "CLOSE", net_pos)
            api.insert_order(SYMBOL, "SELL", "OPEN", VOLUME)

        # ---- 短期信号反转，平仓 ----
        elif net_pos > 0 and cross_down:
            print(">>> 15m死叉，平多离场")
            api.insert_order(SYMBOL, "SELL", "CLOSE", net_pos)

        elif net_pos < 0 and cross_up:
            print(">>> 15m金叉，平空离场")
            api.insert_order(SYMBOL, "BUY", "CLOSE", abs(net_pos))

    api.close()


if __name__ == "__main__":
    main()
