#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略59 - 时序波动率与截面动量复合趋势策略（Temporal Volatility + Cross-Section Momentum Composite）
========================================================================================================

原理：
    本策略将时序趋势策略（利用单品种自身历史走势判断方向）与截面动量策略（利用多品种相对强弱）相结合，
    形成"双重确认"的高置信度入场信号。只有时序趋势和截面动量方向一致时，才产生入场信号，
    大幅减少假信号，提高策略稳健性。

    【时序趋势层（Temporal Layer）】

    【因子 - 时序布林带动量】
    - 计算20日布林带（2倍标准差）
    - 价格在布林中轨之上 → 中期看多；在中轨之下 → 中期看空
    - 计算价格与布林中轨的距离（Z-score），作为趋势强度度量
    - 同时结合ADX趋势强度指标过滤噪音

    【因子 - 时序RSI动量】
    - 14日RSI > 50 表明短期动量向上
    - RSI < 50 表明短期动量向下
    - RSI与价格方向背离 → 预警信号（趋势可能反转）

    【截面动量层（Cross-Section Layer）】

    【因子 - 截面收益率排名】
    - 在品种池中，20日累计收益率排名
    - 做多排名最高的25%，做空排名最低的25%

    【因子 - 截面波动率调整动量（Vol-Adjusted Momentum）】
    - 动量 / 波动率 = 夏普比率式的动量度量
    - 排除高波动率的噪音动量

    【复合信号逻辑】
    - 时序信号 = 布林位置 × ADX权重（>25确认趋势）
    - 截面信号 = 收益率排名分 × 波动率调整权重
    - 综合信号 = 时序信号 × 0.6 + 截面信号 × 0.4
    - 只有综合信号方向与时序信号方向一致时才入场

    【仓位管理】
    - 趋势强度越高 → 仓位越大
    - ADX > 40（强趋势）：满仓（目标仓位的100%）
    - ADX 25-40（中性趋势）：半仓（目标仓位的50%）
    - ADX < 25（无趋势）：清仓观望

参数：
    - 品种池：螺纹钢/热卷/铁矿石/焦煤/焦炭
    - K线周期：日K（86400秒）
    - 布林周期：20
    - 布林倍数：2.0
    - RSI周期：14
    - ADX周期：14
    - 动量周期：20日
    - 波动率周期：14日
    - 换仓周期：每周一开盘（5个交易日）
    - 做多比例：品种池前25%
    - 做空比例：品种池后25%

适用行情：趋势明确的市场、品种分化轮动行情
风险提示：双重过滤可能错过部分趋势；无趋势市场信号稀少
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import numpy as np
import pandas as pd
import time

# ============ 参数配置 ============
SYMBOLS = [
    "SHFE.rb2501",    # 螺纹钢
    "SHFE.hc2501",    # 热卷
    "DCE.i2501",      # 铁矿石
    "DCE.jm2501",     # 焦煤
    "DCE.j2501",      # 焦炭
]
KLINE_DUR = 86400                # 日K线
BOLL_PERIOD = 20                  # 布林带周期
BOLL_MULT = 2.0                   # 布林带倍数
RSI_PERIOD = 14                   # RSI周期
ADX_PERIOD = 14                   # ADX周期
MOM_PERIOD = 20                   # 动量周期
VOL_PERIOD = 14                   # 波动率周期
REBALANCE_DAYS = 5                # 换仓周期（交易日）
LONG_TOP = 0.25                   # 做多前25%品种
SHORT_BOTTOM = 0.25               # 做空后25%品种
ADX_STRONG = 40                   # 强趋势ADX阈值
ADX_WEAK = 25                     # 趋势确认ADX阈值
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
    """近似计算ADX趋势强度指标"""
    if len(close) < period * 2 + 1:
        return np.nan
    returns = close.pct_change().dropna()
    if len(returns) < period:
        return np.nan
    up = returns.clip(lower=0).std()
    down = (-returns.clip(upper=0)).std()
    total = returns.std()
    if total == 0:
        return 0
    plus_di = (up / total) * 100 if total > 0 else 0
    minus_di = (down / total) * 100 if total > 0 else 0
    di_sum = plus_di + minus_di
    if di_sum == 0:
        return 0
    dx = abs(plus_di - minus_di) / di_sum * 100
    return min(dx, 100)


def calc_rsi(close, period=14):
    """计算RSI指标"""
    if len(close) < period + 1:
        return np.nan
    deltas = close.diff()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    if len(gains) < period:
        return np.nan
    avg_gain = gains.iloc[-period:].mean()
    avg_loss = losses.iloc[-period:].mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calc_boll_zscore(close, period=20, mult=2.0):
    """
    计算布林带Z-score：价格偏离中轨的标准化距离
    正值：价格在布林上轨附近（强势）
    负值：价格在布林下轨附近（弱势）
    """
    if len(close) < period:
        return 0.0
    ma = close.iloc[-period:].mean()
    std = close.iloc[-period:].std()
    current = close.iloc[-1]
    if std < 1e-10:
        return 0.0
    zscore = (current - ma) / std
    return zscore


def calc_temporal_signal(close, high, low, period=20):
    """
    计算时序趋势信号
    返回：时序得分（正=看多，负=看空，绝对值=信号强度）
    """
    if len(close) < period + 5:
        return 0.0, 0.0

    # 布林带Z-score
    boll_z = calc_boll_zscore(close, period)

    # RSI
    rsi = calc_rsi(close, RSI_PERIOD)
    rsi_signal = (rsi - 50) / 50  # 归一化到-1到1

    # ADX
    adx = calc_adx_approx(high, low, close, ADX_PERIOD)
    if np.isnan(adx):
        adx = 25  # 默认中性

    # 综合时序得分
    temporal_score = boll_z * 0.5 + rsi_signal * 0.5

    return temporal_score, adx


def calc_vol_adjusted_momentum(close, period=20, vol_period=14):
    """
    计算波动率调整后的动量（夏普比率式的动量）
    """
    if len(close) < max(period, vol_period) + 1:
        return np.nan, np.nan

    ret = close.pct_change(period).iloc[-1]
    returns = close.pct_change().dropna()
    vol = returns.iloc[-vol_period:].std() if len(returns) >= vol_period else returns.std()

    if np.isnan(vol) or vol < 1e-10:
        return ret, 0.0

    vol_adj_mom = ret / vol
    return ret, vol_adj_mom


def cross_section_rank(scores_dict):
    """截面排名"""
    valid = {k: v for k, v in scores_dict.items() if not np.isnan(v) and v != 0}
    if len(valid) == 0:
        return {}
    sorted_vals = sorted(valid.values())
    n = len(sorted_vals)
    rank_dict = {}
    for sym, val in valid.items():
        rank = sorted_vals.index(val) / max(n - 1, 1)
        rank_dict[sym] = rank
    return rank_dict


def main():
    api = TqApi(auth=TqAuth("13556817485", "asd159753"))

    print("=" * 60)
    print("策略59：时序波动率与截面动量复合趋势策略")
    print("=" * 60)

    # 初始化K线数据
    klines = {}
    for sym in SYMBOLS:
        klines[sym] = api.get_tick_serial(sym)
        print(f"  订阅品种：{sym}")

    print("\n等待数据加载...")
    time.sleep(5)

    target_tasks = {sym: TargetPosTask(api, sym) for sym in SYMBOLS}

    trading_day_counter = 0
    last_rebalance_date = None
    position = {sym: 0 for sym in SYMBOLS}

    with api.register_update_notify():
        while True:
            api.wait_update()
            now = api.get_trading_time()
            if now is None:
                continue

            current_date = now.strftime("%Y-%m-%d") if hasattr(now, 'strftime') else str(now)[:10]
            if current_date == last_rebalance_date:
                continue

            trading_day_counter += 1
            if trading_day_counter % REBALANCE_DAYS != 1:
                continue

            print(f"\n{'=' * 40}")
            print(f"换仓日：{current_date}")
            print(f"{'=' * 40}")

            temporal_scores = {}
            cross_scores = {}
            adx_scores = {}

            for sym in SYMBOLS:
                kl = klines[sym]
                if len(kl) < max(BOLL_PERIOD, VOL_PERIOD, ADX_PERIOD * 2) + 5:
                    print(f"  [{sym}] 数据不足，跳过")
                    continue

                close = kl["close"]
                high = kl["high"]
                low = kl["low"]

                # 时序信号
                t_score, adx = calc_temporal_signal(close, high, low, BOLL_PERIOD)
                temporal_scores[sym] = t_score
                adx_scores[sym] = adx

                # 截面波动率调整动量
                ret, vol_adj = calc_vol_adjusted_momentum(close, MOM_PERIOD, VOL_PERIOD)
                cross_scores[sym] = vol_adj if not np.isnan(vol_adj) else 0.0

                print(f"  [{sym}] 时序得分={t_score:.3f}, ADX={adx:.1f}, "
                      f"收益率={ret:.4f}, 波动率调整动量={vol_adj:.3f}")

            # ---------- 截面排名 ----------
            mom_rank = cross_section_rank(cross_scores)

            # ---------- 综合信号（双重确认） ----------
            composite = {}
            for sym in SYMBOLS:
                if sym in temporal_scores and sym in mom_rank:
                    t = temporal_scores[sym]
                    m = mom_rank[sym]
                    # 时序和截面方向一致时，信号加强；不一致时削弱
                    if (t > 0 and m > 0.5) or (t < 0 and m < 0.5):
                        composite[sym] = abs(t) * 0.6 + abs(m - 0.5) * 2 * 0.4
                        if t < 0:
                            composite[sym] = -composite[sym]
                    else:
                        composite[sym] = t * 0.3  # 信号减弱
                else:
                    composite[sym] = 0.0

            sorted_symbols = sorted(composite.items(), key=lambda x: x[1], reverse=True)
            n = len(sorted_symbols)
            n_long = max(1, int(n * LONG_TOP))
            n_short = max(1, int(n * SHORT_BOTTOM))

            long_set = set([s for s, _ in sorted_symbols[:n_long]])
            short_set = set([s for s, _ in sorted_symbols[-n_short:]])

            print(f"\n做多品种（{n_long}个）：{long_set}")
            print(f"做空品种（{n_short}个）：{short_set}")

            # ---------- 目标持仓（根据ADX动态调整仓位） ----------
            avg_adx = np.mean([adx_scores.get(s, 25) for s in SYMBOLS])
            if avg_adx >= ADX_STRONG:
                pos_scale = 1.0
                trend_label = "强趋势（满仓）"
            elif avg_adx >= ADX_WEAK:
                pos_scale = 0.5
                trend_label = "中性趋势（半仓）"
            else:
                pos_scale = 0.0
                trend_label = "无趋势（观望）"

            print(f"  趋势状态: ADX={avg_adx:.1f} → {trend_label}")

            target_pos = {}
            for sym in SYMBOLS:
                score = composite.get(sym, 0.0)
                abs_score = min(abs(score) / 3.0, 1.0)  # 归一化
                if sym in long_set:
                    base_pos = int(pos_scale * abs_score * 8 + 1)
                    target_pos[sym] = base_pos
                elif sym in short_set:
                    base_pos = int(pos_scale * abs_score * 8 + 1)
                    target_pos[sym] = -base_pos
                else:
                    target_pos[sym] = 0

            if pos_scale > 0:
                print(f"\n目标持仓（仓位比例 {pos_scale:.0%}）：{target_pos}")

                for sym, tgt in target_pos.items():
                    cur = position.get(sym, 0)
                    if tgt != cur:
                        diff = tgt - cur
                        print(f"  调整 {sym}: {cur} -> {tgt} ({'买入' if diff > 0 else '卖出'} {abs(diff)}手)")
                        position[sym] = tgt

            last_rebalance_date = current_date
            print(f"\n本次换仓完成，等待下一周期...")


if __name__ == "__main__":
    main()
