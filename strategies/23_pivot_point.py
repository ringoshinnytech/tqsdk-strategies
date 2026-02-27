"""
================================================================================
策略23：枢轴点支撑阻力策略（Pivot Point Support & Resistance Strategy）
================================================================================

【策略背景与来源】
枢轴点（Pivot Point，简称PP）是最古老也是最经典的技术分析工具之一，起源于
20世纪中期的纽约交易所，最初由场内交易员（Floor Trader）用来在每天开盘前
快速计算当日的关键价格支撑和阻力水平。由于其计算方法简单（仅需昨日高低收
三个数据），又能提供多级支撑阻力位，枢轴点至今仍是职业期货交易员最常用的
盘前分析工具之一，也是众多技术分析软件的标准功能。

枢轴点策略的核心假设是：市场价格在关键位置（枢轴点、支撑位、阻力位）附近
会发生反应——或者反转，或者突破加速。本策略采用"在阻力位做空、在支撑位做多"
的反转交易思路，适合在价格区间震荡时使用。

【核心逻辑】
1. 每天（或每根日线K线）收盘后，用当日高、低、收计算次日的6个关键价位
2. 交易时，观察价格与这些关键位的关系：
   - 价格触及阻力位R1/R2 → 预期受阻回落 → 做空
   - 价格触及支撑位S1/S2 → 预期获得支撑 → 做多
   - 价格突破PP从下方向上 → 看多情绪 → 做多
   - 价格跌破PP从上方向下 → 看空情绪 → 做空
3. 以PP（枢轴点）作为中轴止损线：多仓跌破PP止损，空仓涨破PP止损

【计算公式】
基于昨日（前一根日线K线）的高（H）、低（L）、收（C）：

  PP = (H + L + C) / 3          # 枢轴点（轴心价）

  R1 = 2 × PP - L               # 第一阻力位
  R2 = PP + (H - L)             # 第二阻力位
  S1 = 2 × PP - H               # 第一支撑位
  S2 = PP - (H - L)             # 第二支撑位

共5条线（S2 < S1 < PP < R1 < R2），将价格空间分为4个区间。

【交易信号说明】
做多信号：
  1. 价格从PP以下上穿PP → 做多（突破枢轴点，情绪转多）
  2. 价格触及S1且反弹（价格在S1附近且开始上升）→ 做多
  
做空信号：
  1. 价格从PP以上下穿PP → 做空（跌破枢轴点，情绪转空）
  2. 价格触及R1且回落（价格在R1附近且开始下降）→ 做空

止损/平仓：
  多仓：价格重新跌回PP以下止损 / 到达R1止盈
  空仓：价格重新涨回PP以上止损 / 到达S1止盈

【适用品种和周期】
适用品种：流动性好的主流品种，如股指IF/IC/IM、黄金AU、铜CU
适用周期：分钟K线（日内交易），每日收盘后更新支撑阻力位
最佳场景：在前一日价格范围内震荡的行情（当日价格未突破昨日高低点）
不适合：跳空高开/低开导致价格直接穿越所有支撑阻力位的强趋势日

【优缺点分析】
优点：
  1. 计算极简，仅需昨日三个数据，快速得出多级支撑阻力
  2. 在震荡市中效果出色，支撑阻力位往往具有实际意义
  3. 全球机构和职业交易员都在关注这些价位，具有自我实现效应
  4. 可结合其他指标进行综合判断，提升精准度

缺点：
  1. 在强趋势行情中，价格会快速突破所有支撑阻力位
  2. 支撑/阻力是一个"区域"而非精确价格点，实际触及有误差
  3. 每日重新计算，不能捕捉多日趋势
  4. 策略逆趋势性质，需要严格止损纪律

【参数说明】
SYMBOL         : 交易品种，默认股指期货 CFFEX.IF2405
DAY_DURATION   : 日线K线周期（秒），86400秒=1天
TRADE_DURATION : 交易用K线周期（秒），默认300秒（5分钟）
TOUCH_RANGE    : 触及支撑/阻力位的判断范围（点数），默认5点
VOLUME         : 每次下单手数，默认1手
DATA_LENGTH    : 日线K线数量，默认50根（只需最新1根日线的数据）
TRADE_LENGTH   : 交易K线数量，默认500根
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim

# ==================== 策略参数配置 ====================
SYMBOL         = "CFFEX.IF2406"  # 交易品种：沪深300股指期货
DAY_DURATION   = 86400            # 日线K线：1天（秒）
TRADE_DURATION = 5 * 60           # 交易K线：5分钟（秒）
TOUCH_RANGE    = 5.0              # 触及支撑/阻力位的允许误差范围（点数）
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 50               # 日线K线数量（只需最近几根）
TRADE_LENGTH   = 500              # 分钟K线数量


def calc_pivot_points(prev_high, prev_low, prev_close):
    """
    根据昨日高低收计算今日枢轴点和支撑阻力位
    
    参数：
        prev_high:  昨日最高价
        prev_low:   昨日最低价
        prev_close: 昨日收盘价
    
    返回：
        pp: 枢轴点
        r1, r2: 第一、第二阻力位
        s1, s2: 第一、第二支撑位
    """
    pp = (prev_high + prev_low + prev_close) / 3.0  # 枢轴点
    r1 = 2.0 * pp - prev_low                         # 第一阻力位
    r2 = pp + (prev_high - prev_low)                 # 第二阻力位
    s1 = 2.0 * pp - prev_high                        # 第一支撑位
    s2 = pp - (prev_high - prev_low)                 # 第二支撑位
    return pp, r1, r2, s1, s2


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[枢轴点策略] 启动，品种={SYMBOL}, 触及范围={TOUCH_RANGE}点")

    # 获取日线K线（用于计算枢轴点）
    day_klines   = api.get_kline_serial(SYMBOL, DAY_DURATION, data_length=DATA_LENGTH)

    # 获取分钟K线（用于交易信号）
    trade_klines = api.get_kline_serial(SYMBOL, TRADE_DURATION, data_length=TRADE_LENGTH)

    account  = api.get_account()
    position = api.get_position(SYMBOL)

    # 当前有效的枢轴点和支撑阻力位（初始为None）
    pp = r1 = r2 = s1 = s2 = None

    try:
        while True:
            api.wait_update()

            # ====== 当日线K线更新时，重新计算枢轴点 ======
            if api.is_changing(day_klines.iloc[-1], "datetime"):
                # 用前一根日线K线（已完成的昨日K线）计算枢轴点
                prev_day = day_klines.iloc[-2]  # 昨日日线
                pp, r1, r2, s1, s2 = calc_pivot_points(
                    prev_day["high"],
                    prev_day["low"],
                    prev_day["close"]
                )
                print(f"\n[日线更新] 新枢轴点 PP={pp:.2f}, "
                      f"R1={r1:.2f}, R2={r2:.2f}, "
                      f"S1={s1:.2f}, S2={s2:.2f}")

            # ====== 在分钟K线更新时执行交易逻辑 ======
            if api.is_changing(trade_klines.iloc[-1], "datetime") and pp is not None:

                # 获取最新两根分钟K线收盘价
                curr_close = trade_klines["close"].iloc[-1]   # 当前收盘价
                prev_close = trade_klines["close"].iloc[-2]   # 上一根收盘价

                # 读取持仓状态
                pos_long  = position.volume_long
                pos_short = position.volume_short

                # ====== 检测PP穿越信号 ======
                # 上穿PP：前一根在PP以下，当前收盘在PP以上
                cross_pp_up   = (prev_close < pp) and (curr_close >= pp)
                # 下穿PP：前一根在PP以上，当前收盘在PP以下
                cross_pp_down = (prev_close > pp) and (curr_close <= pp)

                # ====== 检测触及支撑/阻力位 ======
                # 触及S1（价格在S1附近，且价格在S1~PP之间）
                touch_s1 = abs(curr_close - s1) <= TOUCH_RANGE and curr_close < pp
                # 触及R1（价格在R1附近，且价格在PP~R1之间）
                touch_r1 = abs(curr_close - r1) <= TOUCH_RANGE and curr_close > pp

                print(f"[{trade_klines.iloc[-1]['datetime']}] "
                      f"Close={curr_close:.2f} | PP={pp:.2f} "
                      f"R1={r1:.2f} S1={s1:.2f} | 多={pos_long}, 空={pos_short}")

                # ====== 交易逻辑 ======

                # --- 信号1：价格上穿PP → 做多（枢轴点以上看多） ---
                if cross_pp_up:
                    if pos_short > 0:
                        # 先平空仓（止损）
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",
                            offset    = "CLOSE",
                            volume    = pos_short
                        )
                        print(f"  → 空仓止损平仓（价格上穿PP={pp:.2f}）")

                    if pos_long == 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",
                            offset    = "OPEN",
                            volume    = VOLUME
                        )
                        print(f"  → 开多仓 {VOLUME}手（上穿枢轴点PP={pp:.2f}）")

                # --- 信号2：价格下穿PP → 做空（枢轴点以下看空） ---
                elif cross_pp_down:
                    if pos_long > 0:
                        # 先平多仓（止损）
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",
                            offset    = "CLOSE",
                            volume    = pos_long
                        )
                        print(f"  → 多仓止损平仓（价格下穿PP={pp:.2f}）")

                    if pos_short == 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",
                            offset    = "OPEN",
                            volume    = VOLUME
                        )
                        print(f"  → 开空仓 {VOLUME}手（下穿枢轴点PP={pp:.2f}）")

                # --- 信号3：价格触及S1 → 做多（支撑位反弹） ---
                elif touch_s1 and pos_long == 0 and pos_short == 0:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "BUY",
                        offset    = "OPEN",
                        volume    = VOLUME
                    )
                    print(f"  → 开多仓 {VOLUME}手（触及S1={s1:.2f}支撑反弹）")

                # --- 信号4：价格触及R1 → 做空（阻力位回落） ---
                elif touch_r1 and pos_long == 0 and pos_short == 0:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "SELL",
                        offset    = "OPEN",
                        volume    = VOLUME
                    )
                    print(f"  → 开空仓 {VOLUME}手（触及R1={r1:.2f}阻力回落）")

                # --- 多仓止盈：价格到达R1 ---
                elif pos_long > 0 and curr_close >= r1:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "SELL",
                        offset    = "CLOSE",
                        volume    = pos_long
                    )
                    print(f"  → 多仓止盈平仓（到达R1={r1:.2f}）")

                # --- 空仓止盈：价格到达S1 ---
                elif pos_short > 0 and curr_close <= s1:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "BUY",
                        offset    = "CLOSE",
                        volume    = pos_short
                    )
                    print(f"  → 空仓止盈平仓（到达S1={s1:.2f}）")

    finally:
        api.close()
        print("[枢轴点策略] 已退出")


if __name__ == "__main__":
    main()
