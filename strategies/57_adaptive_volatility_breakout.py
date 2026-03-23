#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略57 - 自适应波动率突破策略（基于波动锥 Adaptive Volatility Breakout via Volatility Cone）
================================================================================================

原理：
    本策略利用"波动锥"（Volatility Cone）概念，根据历史波动率分位数动态调整入场和风控参数。

    【波动锥（Volatility Cone）】
    - 在不同时间窗口（5日、20日、60日）上计算历史波动率
    - 将当前波动率与历史分布比较，判断当前处于高波动还是低波动环境
    - 波动锥上轨 = 历史波动率的75分位数（高波动上界）
    - 波动锥下轨 = 历史波动率的25分位数（低波动下界）
    - 当前波动率分位数 = (当前波动率 - 历史最低) / (历史最高 - 历史最低)

    【入场逻辑】
    - 价格突破长期布林带上轨（20日均值+2倍标准差）且波动率处于历史高位（>75分位）
    - 高波动环境下的突破往往是真正趋势的开始，假突破概率较低
    - 趋势确认：ADX > 25 表明趋势明确

    【动态止损（波动锥自适应）】
    - 止损设置在入场价 - N倍ATR处
    - N根据波动率分位数动态调整：
        高波动（分位>75%）：止损 = 3.0 * ATR（大止损，给趋势空间）
        中波动（分位25-75%）：止损 = 2.0 * ATR
        低波动（分位<25%）：止损 = 1.5 * ATR（紧止损，防止假突破）
    - 随着价格朝有利方向移动，追踪止损同步上移

    【动态仓位管理】
    - 波动率越高，可承受仓位越小（风险等权原则）
    - 目标波动率 = 15%（年化）
    - 仓位 = 目标波动率 / 当前波动率 * 基础仓位
    - 波动率急剧扩大时（分位数从低跳到高），立即减仓50%

    【波动率突破预警】
    - 当波动率突破历史90分位时，产生"波动率预警"信号
    - 此时不追涨，改为等待回调后入场

参数：
    - 标的：螺纹钢（SHFE.rb）
    - K线周期：30分钟K线（1800秒）
    - 布林周期：20
    - 布林倍数：2.0
    - ATR周期：14
    - ADX周期：14
    - 波动锥窗口：5/20/60日
    - 目标波动率：15%（年化）
    - 波动锥分位阈值：上轨75%，下轨25%

适用行情：趋势启动初期、波动率从低位启动的行情
风险提示：波动率急剧扩大时风险急速上升；低流动性合约不适用
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import numpy as np
import pandas as pd
import time

# ============ 参数配置 ============
SYMBOL = "SHFE.rb2501"             # 螺纹钢主力合约
KLINE_DUR = 1800                   # 30分钟K线
BOLL_PERIOD = 20                   # 布林带周期
BOLL_MULT = 2.0                    # 布林带倍数
ATR_PERIOD = 14                    # ATR周期
ADX_PERIOD = 14                    # ADX周期
VOL_CONE_WINDOWS = [5, 20, 60]     # 波动锥窗口（日，转换K线周期）
UPPER_PCT = 75                     # 上轨分位数
LOWER_PCT = 25                     # 下轨分位数
TARGET_VOL = 0.15                  # 目标年化波动率
BASE_LOT = 1                       # 基础仓位
VOL_ALERT_PCT = 90                 # 波动率预警分位
# ==================================


def calc_atr(high, low, close, period=14):
    """计算平均真实波幅（ATR）"""
    if len(high) < period + 1:
        return np.nan
    tr_list = []
    for i in range(-period, 0):
        tr1 = high.iloc[i] - low.iloc[i]
        tr2 = abs(high.iloc[i] - close.iloc[i - 1])
        tr3 = abs(low.iloc[i] - close.iloc[i - 1])
        tr_list.append(max(tr1, tr2, tr3))
    return np.mean(tr_list)


def calc_adx_approx(high, low, close, period=14):
    """
    近似计算ADX趋势强度指标（基于波动率）
    返回值范围0-100
    """
    if len(close) < period * 2 + 1:
        return np.nan

    returns = close.pct_change().dropna()
    if len(returns) < period:
        return np.nan

    # ADX本质是方向性波动与总波动的比率
    up = returns.clip(lower=0).std()
    down = (-returns.clip(upper=0)).std()
    total = returns.std()

    if total == 0:
        return 0

    plus_dm = up
    minus_dm = down
    tr_val = total  # 用标准差代替TR做归一化

    plus_di = (plus_dm / tr_val) * 100 if tr_val > 0 else 0
    minus_di = (minus_dm / tr_val) * 100 if tr_val > 0 else 0

    di_sum = plus_di + minus_di
    if di_sum == 0:
        return 0

    dx = abs(plus_di - minus_di) / di_sum * 100
    # 简化：直接用dx作为ADX近似（真实ADX是dx的EMA平滑）
    return min(dx, 100)


def calc_vol_percentile(close, current_vol, window_days, kline_dur):
    """
    计算当前波动率在历史分布中的分位数
    window_days: 波动率计算的窗口天数
    kline_dur: K线周期（秒）
    """
    if len(close) < window_days * 86400 // kline_dur + 1:
        return 0.5  # 数据不足返回中性

    # 计算滚动波动率
    klines_needed = window_days * 86400 // kline_dur
    vol_series = []

    for i in range(len(close) - klines_needed):
        segment = close.iloc[i:i + klines_needed]
        if len(segment) >= klines_needed // 2:
            vol = segment.pct_change().std() * np.sqrt(252)
            if not np.isnan(vol) and vol > 0:
                vol_series.append(vol)

    if len(vol_series) < 5:
        return 0.5

    # 计算当前波动率的年化值
    current_annual_vol = current_vol * np.sqrt(252)

    # 历史波动率分位数
    sorted_vols = sorted(vol_series)
    n = len(sorted_vols)
    # 当前vol在历史序列中的位置
    rank = sum(1 for v in sorted_vols if v <= current_annual_vol)
    percentile = rank / n
    return percentile


def volatility_cone_limits(close, kline_dur, windows):
    """
    计算波动锥上轨和下轨
    返回: {window: (upper, lower), ...}
    """
    limits = {}
    for w in windows:
        klines_needed = w * 86400 // kline_dur
        if len(close) < klines_needed + 1:
            limits[w] = (np.nan, np.nan)
            continue

        # 滚动计算波动率
        vol_series = []
        for i in range(len(close) - klines_needed + 1):
            segment = close.iloc[i:i + klines_needed]
            if len(segment) >= klines_needed // 2:
                vol = segment.pct_change().std() * np.sqrt(252)
                if not np.isnan(vol) and vol > 0:
                    vol_series.append(vol)

        if len(vol_series) < 5:
            limits[w] = (np.nan, np.nan)
            continue

        vol_arr = np.array(vol_series)
        upper = np.percentile(vol_arr, UPPER_PCT)
        lower = np.percentile(vol_arr, LOWER_PCT)
        limits[w] = (upper, lower)

    return limits


def calc_adaptive_stop_loss(entry_price, current_atr, vol_percentile, direction, trailing=False, peak_price=None):
    """
    根据波动率分位数自适应计算止损位
    高波动 -> 宽止损（给趋势空间）
    低波动 -> 紧止损（防止假突破）
    direction: +1 做多, -1 做空
    trailing: 是否追踪止损
    peak_price: 做多时的最高价（用于追踪止损）
    """
    if np.isnan(vol_percentile):
        vol_percentile = 0.5

    # 动态ATR倍数
    if vol_percentile > 0.75:
        atr_mult = 3.0  # 高波动：宽止损
    elif vol_percentile > 0.25:
        atr_mult = 2.0  # 中波动
    else:
        atr_mult = 1.5  # 低波动：紧止损

    if trailing and peak_price is not None:
        # 追踪止损：从入场价逐渐上移
        if direction == 1:
            stop = peak_price - atr_mult * current_atr
        else:
            stop = peak_price + atr_mult * current_atr
    else:
        # 固定止损
        if direction == 1:
            stop = entry_price - atr_mult * current_atr
        else:
            stop = entry_price + atr_mult * current_atr

    return stop


def main():
    api = TqApi(auth=TqAuth("13556817485", "asd159753"))

    print("=" * 60)
    print("策略57：自适应波动率突破策略（基于波动锥）")
    print("=" * 60)

    # 订阅K线数据
    klines = api.get_tick_serial(SYMBOL)
    print(f"  订阅品种：{SYMBOL}")

    print("等待数据加载...")
    time.sleep(5)

    # 持仓任务
    target_task = TargetPosTask(api, SYMBOL)

    # 策略状态
    position = 0          # 当前持仓手数（正=多，负=空）
    entry_price = None    # 入场价
    entry_vol_pct = None  # 入场时波动率分位
    peak_price = None     # 持仓期间最高/最低价
    in_position = False   # 是否在持仓中
    last_vol_alert = False  # 上次波动率预警状态

    with api.register_update_notify():
        while True:
            api.wait_update()
            now = api.get_trading_time()
            if now is None:
                continue

            if len(klines) < max(VOL_CONE_WINDOWS) * 86400 // KLINE_DUR + BOLL_PERIOD * 2:
                continue

            close = klines["close"]
            high = klines["high"]
            low = klines["low"]

            # ---------- 计算核心指标 ----------
            # ATR
            atr = calc_atr(high, low, close, ATR_PERIOD)
            if np.isnan(atr):
                continue

            # ADX
            adx = calc_adx_approx(high, low, close, ADX_PERIOD)
            if np.isnan(adx):
                continue

            # 布林带
            boll_period = BOLL_PERIOD
            if len(close) < boll_period:
                continue

            ma = close.iloc[-boll_period:].mean()
            std = close.iloc[-boll_period:].std()
            upper_band = ma + BOLL_MULT * std
            lower_band = ma - BOLL_MULT * std

            # 当前价格
            current_price = close.iloc[-1]
            current_vol = atr / current_price if current_price > 0 else 0  # 日化波动率

            # ---------- 波动锥分析 ----------
            cone_limits = volatility_cone_limits(close, KLINE_DUR, VOL_CONE_WINDOWS)
            vol_pct = calc_vol_percentile(close, current_vol, VOL_CONE_WINDOWS[-1], KLINE_DUR)

            # 综合波动率分位（取三个窗口的加权平均）
            weights = [0.2, 0.3, 0.5]  # 5日/20日/60日权重
            vol_pct_weighted = 0.5
            valid_cones = 0
            for i, w in enumerate(VOL_CONE_WINDOWS):
                if w in cone_limits and not np.isnan(cone_limits[w][0]):
                    annual_vol = current_vol * np.sqrt(252)
                    upper, lower = cone_limits[w]
                    if upper > lower:
                        pct = (annual_vol - lower) / (upper - lower)
                        pct = max(0, min(1, pct))
                        vol_pct_weighted += weights[i] * pct
                        valid_cones += 1

            if valid_cones == 0:
                vol_pct_weighted = 0.5

            vol_percentile = vol_pct_weighted

            # ---------- 波动率预警 ----------
            vol_alert = vol_percentile > (VOL_ALERT_PCT / 100)

            if vol_alert != last_vol_alert:
                if vol_alert:
                    print(f"\n⚠️ 波动率预警：当前波动率处于历史{VOL_ALERT_PCT}分位以上，谨慎追涨！")
                else:
                    print(f"\n✅ 波动率恢复正常")
                last_vol_alert = vol_alert

            # ---------- 入场逻辑 ----------
            if not in_position:
                # 突破布林上轨 + ADX趋势确认
                if current_price > upper_band and adx > 25 and not vol_alert:
                    direction = 1
                    entry_price = current_price
                    entry_vol_pct = vol_percentile
                    peak_price = current_price

                    # 计算仓位（波动率越高，仓位越低）
                    current_annual_vol = current_vol * np.sqrt(252)
                    if current_annual_vol > 0:
                        vol_ratio = TARGET_VOL / current_annual_vol
                        target_lot = int(min(vol_ratio * BASE_LOT, 10))  # 最多10手
                        target_lot = max(target_lot, 1)
                    else:
                        target_lot = BASE_LOT

                    # 动态止损
                    stop_loss = calc_adaptive_stop_loss(
                        entry_price, atr, vol_percentile, direction
                    )

                    print(f"\n{'=' * 40}")
                    print(f"【做多信号】时间：{now}")
                    print(f"  价格突破布林上轨: {current_price:.2f} > {upper_band:.2f}")
                    print(f"  ADX={adx:.2f} > 25，趋势确认")
                    print(f"  波动率分位={vol_percentile:.2%}，ATR={atr:.2f}")
                    print(f"  仓位: {target_lot}手，止损位: {stop_loss:.2f}")
                    print(f"  止损模式: {'宽止损(高波动)' if vol_percentile > 0.75 else '中止损' if vol_percentile > 0.25 else '紧止损(低波动)'}")
                    print(f"{'=' * 40}")

                    position = target_lot
                    target_task.set_target_volume(position)
                    in_position = True

                # 跌破布林下轨（做空，需波动率偏高才做空）
                elif current_price < lower_band and adx > 25 and vol_percentile > 0.5:
                    direction = -1
                    entry_price = current_price
                    entry_vol_pct = vol_percentile
                    peak_price = current_price

                    current_annual_vol = current_vol * np.sqrt(252)
                    if current_annual_vol > 0:
                        vol_ratio = TARGET_VOL / current_annual_vol
                        target_lot = -int(min(vol_ratio * BASE_LOT, 10))
                        target_lot = max(target_lot, -1)
                    else:
                        target_lot = -BASE_LOT

                    stop_loss = calc_adaptive_stop_loss(
                        entry_price, atr, vol_percentile, direction
                    )

                    print(f"\n{'=' * 40}")
                    print(f"【做空信号】时间：{now}")
                    print(f"  价格跌破布林下轨: {current_price:.2f} < {lower_band:.2f}")
                    print(f"  ADX={adx:.2f} > 25，趋势确认")
                    print(f"  波动率分位={vol_percentile:.2%}，ATR={atr:.2f}")
                    print(f"  仓位: {abs(target_lot)}手，止损位: {stop_loss:.2f}")
                    print(f"{'=' * 40}")

                    position = target_lot
                    target_task.set_target_volume(position)
                    in_position = True

            # ---------- 持仓管理 ----------
            else:
                direction = 1 if position > 0 else -1

                # 更新峰值/谷值（用于追踪止损）
                if direction == 1:
                    if peak_price is None or current_price > peak_price:
                        peak_price = current_price
                else:
                    if peak_price is None or current_price < peak_price:
                        peak_price = current_price

                # 计算追踪止损位
                stop_loss = calc_adaptive_stop_loss(
                    entry_price, atr, vol_percentile, direction,
                    trailing=True, peak_price=peak_price
                )

                # 止损检查
                stop_triggered = False
                if direction == 1 and current_price < stop_loss:
                    stop_triggered = True
                elif direction == -1 and current_price > stop_loss:
                    stop_triggered = True

                # 波动率急剧扩大的减仓保护
                if vol_percentile > 0.90 and abs(position) > 1:
                    new_pos = int(abs(position) * 0.5) * (1 if direction == 1 else -1)
                    print(f"\n⚠️ 波动率爆炸式扩大，减仓50%: {position} -> {new_pos}")
                    position = new_pos
                    target_task.set_target_volume(position)

                if stop_triggered:
                    print(f"\n{'=' * 40}")
                    print(f"【止损出场】时间：{now}")
                    print(f"  方向: {'做多' if direction == 1 else '做空'}")
                    print(f"  当前价: {current_price:.2f}")
                    print(f"  止损位: {stop_loss:.2f}")
                    print(f"  持仓时长: {now}")
                    print(f"  波动率分位: {vol_percentile:.2%}")
                    print(f"{'=' * 40}")
                    position = 0
                    target_task.set_target_volume(0)
                    in_position = False
                    entry_price = None
                    peak_price = None

                # 止盈：追踪止损上移到保本价
                elif (direction == 1 and peak_price > entry_price * 1.02) or \
                     (direction == -1 and peak_price < entry_price * 0.98):
                    # 保本止损
                    breakeven = entry_price * (1.01 if direction == 1 else 0.99)
                    if (direction == 1 and current_price < breakeven) or \
                       (direction == -1 and current_price > breakeven):
                        print(f"\n【保本止损】价格回归保本价，平仓")
                        position = 0
                        target_task.set_target_volume(0)
                        in_position = False
                        entry_price = None
                        peak_price = None


if __name__ == "__main__":
    main()
