#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唐奇安通道策略 (Donchian Channel Strategy) - 简化版
=====================================================

【策略背景与来源】
唐奇安通道（Donchian Channel）由理查德·唐奇安（Richard Donchian）在20世纪50年代提出，
是最经典的趋势跟踪通道指标之一。唐奇安本人被誉为"现代期货交易之父"，其通道理论直接
启发了后来著名的海龟交易法则（Turtle Trading）。与海龟策略不同，本策略为简化版，
仅使用单一通道突破信号，不加入ATR仓位管理和加仓规则，适合初学者理解通道突破的核心逻辑。

【核心逻辑】
唐奇安通道由三条线构成：
  上轨（Upper Band）= 过去N根K线的最高价  →  价格向上突破时做多
  下轨（Lower Band）= 过去N根K线的最低价  →  价格向下跌破时做空
  中轨（Middle Band）= (上轨 + 下轨) / 2   →  可作为止盈/平仓参考

通道宽度直接反映近N期的价格波动范围：
  - 通道宽 → 市场波动大，趋势行情中更可信的突破
  - 通道窄 → 市场整理，突破可能是假突破

策略核心思想：价格突破历史N期最高点，说明多头力量创出新高，趋势向上确认；
价格跌破历史N期最低点，说明空头力量创出新低，趋势向下确认。

【计算公式】
Upper_N  = max(High[-N:-1])     # 过去N根完成K线的最高价（不含当前未完成K线）
Lower_N  = min(Low[-N:-1])      # 过去N根完成K线的最低价
Middle_N = (Upper_N + Lower_N) / 2

入场信号：
  close > Upper_N  → 突破上轨，做多
  close < Lower_N  → 跌破下轨，做空

出场信号（使用更短周期N2的通道）：
  多头：close < min(Low[-N2:-1])  → 跌破N2期最低，平多离场
  空头：close > max(High[-N2:-1]) → 突破N2期最高，平空离场

【交易信号说明】
1. 等待价格突破N期通道上/下轨（已完成K线收盘价确认）
2. 突破上轨：平空（如有）→ 开多（通过 set_target_volume(VOLUME) 实现）
3. 跌破下轨：平多（如有）→ 开空（通过 set_target_volume(-VOLUME) 实现）
4. 持多头且价格跌破N2期下轨：平多止损/止盈（set_target_volume(0)）
5. 持空头且价格突破N2期上轨：平空止损/止盈（set_target_volume(0)）

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑，代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发

【适用品种和周期】
品种：趋势性强的品种，如原油（SC）、铜（CU）、螺纹钢（RB）、股指（IF）
周期：建议日线或4小时线，K线周期越短假突破越多
推荐参数：N=20（入场），N2=10（出场）

【优缺点分析】
优点：
  - 逻辑最简洁清晰，纯价格突破，无参数优化空间的陷阱
  - 完全客观，消除主观判断
  - 在强趋势行情中表现优异，单次盈利空间大
  - 是海龟交易等经典策略的基础

缺点：
  - 无仓位管理，每次固定手数，不适合大资金
  - 震荡市中频繁假突破，连续止损
  - 入场点通常在趋势已经发展一段时间后，初始回撤较大
  - 未考虑流动性、时间过滤等实盘因素

【参数说明】
  SYMBOL      : 交易合约代码，默认 SHFE.rb2501（螺纹钢）
  N_ENTER     : 入场通道周期，默认20根K线
  N_EXIT      : 出场通道周期，默认10根K线（应 < N_ENTER）
  KLINE_DUR   : K线周期（秒），默认86400（日线）
  VOLUME      : 每次开仓手数，默认1手
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ===================== 策略参数 =====================
SYMBOL = "SHFE.rb2501"     # 交易合约：螺纹钢主力
N_ENTER = 20               # 入场通道周期：20根K线突破
N_EXIT = 10                # 出场通道周期：10根K线回撤平仓
KLINE_DUR = 86400          # K线周期：日线
VOLUME = 1                 # 每次开仓手数
# ===================================================


def main():
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 需要足够多的K线来计算入场通道
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=N_ENTER + 5)

    # 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    print(f"[唐奇安通道] 启动 | {SYMBOL} | 入场N={N_ENTER} | 出场N={N_EXIT}")

    while True:
        api.wait_update()

        if not api.is_changing(klines):
            continue

        # ---- 计算通道 ----
        # 使用已完成的K线（iloc[-(N+1):-1] 取倒数N+1到倒数第1根，即前N根完成K线）
        high_enter = klines.high.iloc[-(N_ENTER + 1):-1].max()   # 入场上轨
        low_enter  = klines.low.iloc[-(N_ENTER + 1):-1].min()    # 入场下轨
        high_exit  = klines.high.iloc[-(N_EXIT + 1):-1].max()    # 出场上轨
        low_exit   = klines.low.iloc[-(N_EXIT + 1):-1].min()     # 出场下轨

        # 最新完成K线的收盘价（-2是最近完成的那根）
        last_close = klines.close.iloc[-2]

        print(
            f"收盘: {last_close:.2f} | "
            f"入场通道: [{low_enter:.2f}, {high_enter:.2f}] | "
            f"出场通道: [{low_exit:.2f}, {high_exit:.2f}]"
        )

        # ---- 入场：突破上轨做多 ----
        if last_close > high_enter:
            print(f">>> 突破入场上轨 {high_enter:.2f}，做多")
            target_pos.set_target_volume(VOLUME)

        # ---- 入场：跌破下轨做空 ----
        elif last_close < low_enter:
            print(f">>> 跌破入场下轨 {low_enter:.2f}，做空")
            target_pos.set_target_volume(-VOLUME)

        # ---- 出场：多头跌破出场下轨，平多 ----
        elif last_close < low_exit:
            print(f">>> 多头跌破出场下轨 {low_exit:.2f}，平多")
            target_pos.set_target_volume(0)

        # ---- 出场：空头突破出场上轨，平空 ----
        elif last_close > high_exit:
            print(f">>> 空头突破出场上轨 {high_exit:.2f}，平空")
            target_pos.set_target_volume(0)

    api.close()


if __name__ == "__main__":
    main()
