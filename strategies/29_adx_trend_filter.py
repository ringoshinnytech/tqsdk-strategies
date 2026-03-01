#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【关于 TqSdk —— 天勤量化开发包】

TqSdk 是由信易科技发起并开源的 Python 量化交易框架，专为国内期货市场设计，
是国内最主流的期货量化开发工具之一。

核心优势：
  ● 极简代码：几十行即可构建完整策略，内置 MA/MACD/BOLL/RSI/ATR 等近百个技术指标
  ● 全品种实时行情：期货、期权、股票，毫秒级推送，数据全在内存，零延迟
  ● 全流程支持：历史回测 → 模拟交易 → 实盘交易 → 运行监控，一套 API 全覆盖
  ● 广泛兼容：支持 90%+ 期货公司 CTP 直连及主流资管柜台
  ● Pandas 友好：K 线 / Tick 数据直接返回 DataFrame，与 NumPy 无缝配合

官方资源：
  📘 官方文档：https://doc.shinnytech.com/tqsdk/latest/
  🐙 GitHub  ：https://github.com/shinnytech/tqsdk-python
  🧑‍💻 账户注册：https://account.shinnytech.com/
  💬 用户社区：https://www.shinnytech.com/qa/

安装：pip install tqsdk -U
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

策略29：ADX 趋势强度过滤策略
==============================

【策略背景与理论基础】

ADX（Average Directional Index，平均趋向指数）是由 J. Welles Wilder 于1978年
在其经典著作《技术交易系统的新概念》（New Concepts in Technical Trading Systems）
中提出的，与 RSI、ATR、抛物线 SAR 同出一源，是衡量趋势"强度"而非"方向"的
重要技术指标。

ADX 与 DMI（Directional Movement Index，趋向运动指标）系统配套使用：
  - +DI（Positive Directional Indicator）：上涨方向强度
  - -DI（Negative Directional Indicator）：下跌方向强度
  - ADX：+DI 与 -DI 差值的平滑均值，反映趋势的整体强弱

【核心数学原理】

1. 计算真实波幅（True Range, TR）：
   TR = max(H-L, |H-C_pre|, |L-C_pre|)
   其中 H=当日最高价，L=当日最低价，C_pre=前日收盘价

2. 计算方向运动（Directional Movement, DM）：
   +DM = H - H_pre（若 H > H_pre 且 H - H_pre > L_pre - L，则取此值，否则为0）
   -DM = L_pre - L（若 L < L_pre 且 L_pre - L > H - H_pre，则取此值，否则为0）

3. 对 TR、+DM、-DM 进行 N 周期（通常14）指数平滑：
   TR14 = 前13日TR14 - (前13日TR14 / 14) + 当日TR
   +DM14、-DM14 同理

4. 计算方向指标：
   +DI14 = (+DM14 / TR14) × 100
   -DI14 = (-DM14 / TR14) × 100

5. 计算 DX（方向指数）：
   DX = |+DI14 - -DI14| / (+DI14 + -DI14) × 100

6. ADX 为 DX 的 N 周期指数移动平均：
   ADX = EMA(DX, N)

【信号解读规则】

ADX 的取值范围为 0～100，通常有以下经验性阈值：
  - ADX < 20：市场处于盘整（震荡）状态，趋势不明显，不适合趋势跟踪策略
  - ADX 20～25：趋势开始形成，信号需谨慎对待
  - ADX 25～50：趋势较为明显，是趋势跟踪策略的理想入场区间
  - ADX > 50：趋势非常强劲，但此时往往已接近趋势末期
  - ADX 由上向下拐头：趋势可能开始减弱，考虑减仓或平仓

【本策略的交易逻辑】

本策略将 ADX 作为趋势强度"过滤器"，结合 +DI/-DI 的多空方向信号：

  **入场条件：**
  1. ADX > adx_threshold（默认25）：确认市场处于趋势状态
  2. +DI > -DI（多头方向更强）：做多；-DI > +DI（空头方向更强）：做空
  3. 额外过滤：价格需突破最近 N 根K线的高点（做多）或低点（做空）

  **出场条件（三选一）：**
  1. +DI / -DI 发生方向反转（趋势方向改变）
  2. ADX 跌破 adx_exit（默认20）：趋势减弱，保守退出
  3. 价格跌破 ATR 追踪止损线（动态风控）

【ADX 策略的适用场景】

ADX 策略在以下市场环境中表现最佳：
  ✅ 大趋势行情：商品期货大牛/大熊市初中期（如2020年黑色金属大涨）
  ✅ 趋势持续时间较长的品种：原油、黄金、大豆等基本面驱动的品种
  ✅ 中长周期：日线、4小时线（短周期噪音过多，ADX 有效性下降）

  ❌ 震荡市场：ADX<20 时策略不交易，会错过部分震荡行情（这是正确的！）
  ❌ 超短线交易：ADX 本身有一定滞后性，不适合1分钟以下超短线

【参数优化建议】

  - ADX 周期（14）：适当缩短（如10）可提高灵敏度，延长（如20）可减少噪音
  - ADX 阈值（25）：牛市可适当提高到30，震荡市可降低到20
  - 追踪止损倍数（2.0×ATR）：可根据品种波动特性调整为1.5～3.0

【风险提示】

  - ADX 是滞后指标，趋势确认时往往已有一段涨跌幅；需接受部分"吃不到鱼头"
  - 趋势结束时 ADX 也会滞后反应，可能导致部分盈利回撤
  - 建议与震荡判断指标（如布林带带宽）结合使用，进一步过滤假信号
  - 本策略为演示策略，实盘前请在更长历史数据上充分验证
"""

from tqsdk import TqApi, TqAuth, TqBacktest, TqSim
from datetime import date
import numpy as np

# ===== 策略参数配置 =====
SYMBOL = "DCE.i2601"        # 交易品种：铁矿石主力合约（趋势性较强）
KLINE_DURATION = 4 * 60 * 60  # K线周期：4小时（单位：秒）
DMI_PERIOD = 14             # DMI/ADX 计算周期（Wilder 默认14）
ADX_PERIOD = 14             # ADX 平滑周期
ADX_ENTRY = 25.0            # ADX 入场阈值：大于此值才允许趋势交易
ADX_EXIT = 20.0             # ADX 出场阈值：小于此值趋势减弱，平仓离场
BREAKOUT_PERIOD = 10        # 突破过滤：入场需突破最近N根K线高/低点
ATR_PERIOD = 14             # ATR 计算周期（用于追踪止损）
ATR_MULTI = 2.0             # ATR 追踪止损倍数
TRADE_VOLUME = 1            # 每次交易手数


def calc_dmi_adx(high, low, close, dmi_period=14, adx_period=14):
    """
    计算 DMI（+DI / -DI）和 ADX 指标。

    参数：
      high       - 最高价数组（numpy array）
      low        - 最低价数组（numpy array）
      close      - 收盘价数组（numpy array）
      dmi_period - DM 平滑周期，默认14
      adx_period - ADX 平滑周期，默认14

    返回：
      plus_di  - +DI 数组
      minus_di - -DI 数组
      adx      - ADX 数组

    实现说明：
      使用 Wilder 平滑（Wilder's Smoothing Method），等效于 EMA(alpha=1/period)。
      首个有效值从第 dmi_period 根K线开始计算。
    """
    n = len(close)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr_arr = np.zeros(n)

    # 逐根计算 TR、+DM、-DM
    for i in range(1, n):
        h_cur, h_pre = high[i], high[i - 1]
        l_cur, l_pre = low[i], low[i - 1]
        c_pre = close[i - 1]

        # 真实波幅 TR = max(H-L, |H-C_pre|, |L-C_pre|)
        tr_arr[i] = max(h_cur - l_cur, abs(h_cur - c_pre), abs(l_cur - c_pre))

        # +DM：上涨方向运动
        up_move = h_cur - h_pre
        # -DM：下跌方向运动
        down_move = l_pre - l_cur

        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder 平滑：初始值为前 dmi_period 根之和
    tr14 = np.zeros(n)
    pdm14 = np.zeros(n)
    mdm14 = np.zeros(n)

    if n <= dmi_period:
        # 数据不足，全返回0
        return np.zeros(n), np.zeros(n), np.zeros(n)

    # 第一个有效平滑值：直接求和
    tr14[dmi_period] = np.sum(tr_arr[1: dmi_period + 1])
    pdm14[dmi_period] = np.sum(plus_dm[1: dmi_period + 1])
    mdm14[dmi_period] = np.sum(minus_dm[1: dmi_period + 1])

    # 后续采用 Wilder 递推公式
    for i in range(dmi_period + 1, n):
        tr14[i] = tr14[i - 1] - (tr14[i - 1] / dmi_period) + tr_arr[i]
        pdm14[i] = pdm14[i - 1] - (pdm14[i - 1] / dmi_period) + plus_dm[i]
        mdm14[i] = mdm14[i - 1] - (mdm14[i - 1] / dmi_period) + minus_dm[i]

    # 计算 +DI 和 -DI
    plus_di = np.where(tr14 > 0, (pdm14 / tr14) * 100, 0.0)
    minus_di = np.where(tr14 > 0, (mdm14 / tr14) * 100, 0.0)

    # 计算 DX
    di_sum = plus_di + minus_di
    dx = np.where(di_sum > 0, np.abs(plus_di - minus_di) / di_sum * 100, 0.0)

    # 计算 ADX：对 DX 进行 Wilder 平滑
    adx = np.zeros(n)
    start_idx = dmi_period + adx_period
    if n <= start_idx:
        return plus_di, minus_di, adx

    # ADX 第一个有效值：DX 在 [dmi_period, dmi_period+adx_period-1] 区间的均值
    adx[start_idx] = np.mean(dx[dmi_period: dmi_period + adx_period])

    # 后续 ADX Wilder 递推
    for i in range(start_idx + 1, n):
        adx[i] = (adx[i - 1] * (adx_period - 1) + dx[i]) / adx_period

    return plus_di, minus_di, adx


def calc_atr(high, low, close, period=14):
    """
    计算 ATR（Average True Range，平均真实波幅）。

    采用 Wilder 平滑方式，与 DMI/ADX 保持一致性。
    """
    n = len(close)
    tr_arr = np.zeros(n)
    for i in range(1, n):
        tr_arr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )

    atr = np.zeros(n)
    if n <= period:
        return atr

    atr[period] = np.mean(tr_arr[1: period + 1])
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr_arr[i]) / period

    return atr


def main():
    # ===== 初始化 TqApi =====
    api = TqApi(
        backtest=TqBacktest(
            start_dt=date(2025, 1, 1),
            end_dt=date(2025, 12, 31)
        ),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
        account=TqSim(init_balance=300000)  # 模拟账户，初始资金30万（铁矿石保证金较高）
    )

    # ===== 订阅行情数据 =====
    # 获取4小时K线，保留600根历史数据以确保指标计算稳定
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=600)
    quote = api.get_quote(SYMBOL)
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(f"[ADX 趋势强度过滤策略] 启动，品种：{SYMBOL}，K线周期：4小时")
    print(f"DMI周期：{DMI_PERIOD}，ADX入场阈值：{ADX_ENTRY}，ATR止损倍数：{ATR_MULTI}")

    # ===== 状态变量 =====
    last_signal = None          # 上次交易信号 ('long' / 'short' / None)
    stop_loss_price = None      # 当前追踪止损价格
    last_bar_id = None          # 用于检测新K线

    # ===== 主循环 =====
    while True:
        api.wait_update()

        # 仅在新K线完成时触发计算（避免在同一根K线内重复计算）
        if not api.is_changing(klines.iloc[-1], "datetime"):
            continue

        current_bar_id = klines.iloc[-1]["id"]
        if current_bar_id == last_bar_id:
            continue
        last_bar_id = current_bar_id

        n = len(klines)
        min_data = DMI_PERIOD + ADX_PERIOD + BREAKOUT_PERIOD + 5
        if n < min_data:
            # 历史数据不足，等待更多K线
            continue

        # ===== 提取价格数据 =====
        high_arr = klines["high"].values.astype(float)
        low_arr = klines["low"].values.astype(float)
        close_arr = klines["close"].values.astype(float)

        # ===== 计算 DMI / ADX =====
        plus_di, minus_di, adx = calc_dmi_adx(
            high_arr, low_arr, close_arr, DMI_PERIOD, ADX_PERIOD
        )

        # ===== 计算 ATR（追踪止损用）=====
        atr_arr = calc_atr(high_arr, low_arr, close_arr, ATR_PERIOD)

        # 当前最新值
        adx_cur = adx[-1]
        adx_pre = adx[-2]
        pdi_cur = plus_di[-1]
        mdi_cur = minus_di[-1]
        pdi_pre = plus_di[-2]
        mdi_pre = minus_di[-2]
        atr_cur = atr_arr[-1]
        close_cur = close_arr[-1]

        # 检查关键值是否有效
        if adx_cur == 0 or atr_cur == 0:
            continue

        # ===== 突破过滤条件 =====
        # 做多需要价格突破最近 BREAKOUT_PERIOD 根K线的最高点
        recent_high = np.max(high_arr[-BREAKOUT_PERIOD - 1: -1])
        # 做空需要价格跌破最近 BREAKOUT_PERIOD 根K线的最低点
        recent_low = np.min(low_arr[-BREAKOUT_PERIOD - 1: -1])

        # ===== 追踪止损更新 =====
        # 多头：止损线 = max(历史止损, 当前价格 - ATR*倍数)
        # 空头：止损线 = min(历史止损, 当前价格 + ATR*倍数)
        net_pos = position.pos_long - position.pos_short

        if net_pos > 0 and stop_loss_price is not None:
            # 多头追踪止损（只上移，不下移）
            new_stop = close_cur - atr_cur * ATR_MULTI
            stop_loss_price = max(stop_loss_price, new_stop)
        elif net_pos < 0 and stop_loss_price is not None:
            # 空头追踪止损（只下移，不上移）
            new_stop = close_cur + atr_cur * ATR_MULTI
            stop_loss_price = min(stop_loss_price, new_stop)

        # ===== 出场逻辑（先检查止损和趋势减弱）=====
        if net_pos > 0:
            # 多头持仓出场判断
            exit_reason = None
            if stop_loss_price is not None and close_cur < stop_loss_price:
                exit_reason = f"触及追踪止损 {stop_loss_price:.1f}"
            elif adx_cur < ADX_EXIT:
                exit_reason = f"ADX={adx_cur:.1f} 跌破出场阈值 {ADX_EXIT}"
            elif mdi_cur > pdi_cur and mdi_pre <= pdi_pre:
                exit_reason = f"方向反转：-DI({mdi_cur:.1f}) 上穿 +DI({pdi_cur:.1f})"

            if exit_reason:
                print(f"[平多] {exit_reason}，当前价格={close_cur:.1f}")
                api.insert_order(SYMBOL, direction="SELL", offset="CLOSE",
                                 volume=position.pos_long)
                last_signal = None
                stop_loss_price = None

        elif net_pos < 0:
            # 空头持仓出场判断
            exit_reason = None
            if stop_loss_price is not None and close_cur > stop_loss_price:
                exit_reason = f"触及追踪止损 {stop_loss_price:.1f}"
            elif adx_cur < ADX_EXIT:
                exit_reason = f"ADX={adx_cur:.1f} 跌破出场阈值 {ADX_EXIT}"
            elif pdi_cur > mdi_cur and pdi_pre <= mdi_pre:
                exit_reason = f"方向反转：+DI({pdi_cur:.1f}) 上穿 -DI({mdi_cur:.1f})"

            if exit_reason:
                print(f"[平空] {exit_reason}，当前价格={close_cur:.1f}")
                api.insert_order(SYMBOL, direction="BUY", offset="CLOSE",
                                 volume=position.pos_short)
                last_signal = None
                stop_loss_price = None

        # ===== 重新获取持仓（平仓后净持仓变化）=====
        net_pos = position.pos_long - position.pos_short

        # ===== 入场逻辑 =====
        if net_pos == 0:
            # 多头入场：ADX 强势 + +DI > -DI + 价格突破近期高点
            bull_entry = (
                adx_cur >= ADX_ENTRY and
                pdi_cur > mdi_cur and
                close_cur > recent_high and
                last_signal != 'long'
            )

            # 空头入场：ADX 强势 + -DI > +DI + 价格跌破近期低点
            bear_entry = (
                adx_cur >= ADX_ENTRY and
                mdi_cur > pdi_cur and
                close_cur < recent_low and
                last_signal != 'short'
            )

            if bull_entry:
                # 计算初始止损（入场价格下方 ATR 倍数处）
                stop_loss_price = close_cur - atr_cur * ATR_MULTI
                print(f"[开多] ADX={adx_cur:.1f}(>={ADX_ENTRY}) | "
                      f"+DI={pdi_cur:.1f} > -DI={mdi_cur:.1f} | "
                      f"价格={close_cur:.1f} 突破近期高点={recent_high:.1f} | "
                      f"初始止损={stop_loss_price:.1f}")
                api.insert_order(SYMBOL, direction="BUY", offset="OPEN",
                                 volume=TRADE_VOLUME)
                last_signal = 'long'

            elif bear_entry:
                stop_loss_price = close_cur + atr_cur * ATR_MULTI
                print(f"[开空] ADX={adx_cur:.1f}(>={ADX_ENTRY}) | "
                      f"-DI={mdi_cur:.1f} > +DI={pdi_cur:.1f} | "
                      f"价格={close_cur:.1f} 跌破近期低点={recent_low:.1f} | "
                      f"初始止损={stop_loss_price:.1f}")
                api.insert_order(SYMBOL, direction="SELL", offset="OPEN",
                                 volume=TRADE_VOLUME)
                last_signal = 'short'

        # 每根K线输出当前指标状态，便于监控
        trend_state = "震荡" if adx_cur < 20 else ("弱趋势" if adx_cur < 25 else "强趋势")
        direction = "+DI主导(多)" if pdi_cur > mdi_cur else "-DI主导(空)"
        print(f"[状态] ADX={adx_cur:.1f}({trend_state}) | {direction} | "
              f"+DI={pdi_cur:.1f} -DI={mdi_cur:.1f} | "
              f"ATR={atr_cur:.1f} | 价格={close_cur:.1f} | "
              f"净持仓={net_pos} | 权益={account.balance:.0f}")


if __name__ == "__main__":
    main()
