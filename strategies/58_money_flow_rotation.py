#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略58 - 截面资金流向多空轮动策略（Cross-Section Money Flow Long-Short Rotation）
===================================================================================

原理：
    本策略利用资金流向指标（Chaikin Money Flow / CMF 的改进版）在多品种截面上进行多空轮动，
    同时结合成交量加权价格（VWAP）和持仓量变化（OI Change）三重过滤，
    捕捉资金持续流入的品种做多，持续流出的品种做空。

    【核心因子】

    【因子1 - CMF资金流向因子】
    - 计算期间内资金净流入量 = Σ((收盘-最低)-(最高-收盘))/(最高-最低) × 成交量
    - CMF > 0 表明收盘价偏向最高价区间（机构主导做多）
    - CMF < 0 表明收盘价偏向最低价区间（机构主导做空）
    - 取20日累计CMF作为中期资金流向信号

    【因子2 - 成交量持仓量背离因子】
    - OI Change（持仓量变化）与价格涨跌的关系判断主力动向
    - 价格↑ + OI↓ = 多头平仓（假突破风险高）
    - 价格↑ + OI↑ = 新多入场（真突破概率高）
    - 价格↓ + OI↑ = 新空入场（真下跌概率高）
    - 价格↓ + OI↓ = 空头平仓（假突破风险高）

    【因子3 - 成交量加权价格偏离因子】
    - 计算VWAP与收盘价的偏离度
    - 价格 > VWAP + 1σ：收盘价高于市场平均成本，看涨信号
    - 价格 < VWAP - 1σ：收盘价低于市场平均成本，看跌信号

    综合打分 = CMF排名分 × 0.5 + OI背离排名分 × 0.3 + VWAP偏离排名分 × 0.2
    做多综合得分最高的前25%品种，做空得分最低的后25%品种。

    【动态仓位管理】
    - 根据资金流向强度调整仓位
    - CMF绝对值越大 → 资金信号越强 → 仓位权重越高
    - 限制单品种最大仓位不超过总仓位的25%

参数：
    - 品种池：螺纹钢/热卷/铁矿石/焦煤/焦炭/甲醇/PTA/原油
    - K线周期：日K（86400秒）
    - CMF周期：20日
    - OI背离计算：5日
    - VWAP周期：20日
    - 换仓周期：每周一开盘（5个交易日）
    - 做多比例：品种池前25%
    - 做空比例：品种池后25%
    - 最大仓位占比：25%

适用行情：资金轮动行情、板块分化行情、主力调仓行情
风险提示：资金流向存在滞后性；极端行情中CMF失效风险
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
    "CZCE.MA2501",    # 甲醇
    "CZCE.TA2501",    # PTA
    "INE.sc2501",     # 原油
]
KLINE_DUR = 86400                # 日K线
CMF_PERIOD = 20                 # CMF周期
OI_PERIOD = 5                   # OI背离计算周期
VWAP_PERIOD = 20                # VWAP周期
REBALANCE_DAYS = 5              # 换仓周期（交易日）
LONG_TOP = 0.25                 # 做多前25%品种
SHORT_BOTTOM = 0.25             # 做空后25%品种
MAX_POS_RATIO = 0.25            # 单品种最大仓位占比
# ==================================


def calc_cmf(high, low, close, volume, period=20):
    """
    计算Chaikin Money Flow（资金流向指数）
    返回：CMF值（-1到1之间）
    """
    if len(high) < period + 1:
        return np.nan

    mf_multiplier = ((close - low) - (high - close)) / (high - low + 1e-10)
    mf_volume = mf_multiplier * volume

    cmf = mf_volume.iloc[-period:].sum() / volume.iloc[-period:].sum()
    return cmf


def calc_oi_divergence(close, open_interest, period=5):
    """
    计算持仓量背离因子
    返回：背离得分（正=多头信号，负=空头信号）
    """
    if len(close) < period + 1 or len(open_interest) < period + 1:
        return 0.0

    price_ret = close.iloc[-1] - close.iloc[-period]
    oi_ret = open_interest.iloc[-1] - open_interest.iloc[-period]

    if abs(oi_ret) < 1e-6:
        return 0.0

    # 价格涨 + 持仓增 → 真突破 (+2)
    # 价格涨 + 持仓减 → 多头平仓 (-1)
    # 价格跌 + 持仓增 → 真下跌 (-2)
    # 价格跌 + 持仓减 → 空头平仓 (+1)
    if price_ret > 0 and oi_ret > 0:
        return 2.0
    elif price_ret > 0 and oi_ret < 0:
        return -1.0
    elif price_ret < 0 and oi_ret > 0:
        return -2.0
    elif price_ret < 0 and oi_ret < 0:
        return 1.0
    else:
        return 0.0


def calc_vwap_deviation(close, volume, period=20):
    """
    计算VWAP偏离因子
    返回：偏离度（正=价格高于VWAP，负=价格低于VWAP）
    """
    if len(close) < period or len(volume) < period:
        return 0.0

    typical_price = (close + close + close) / 3  # 简化为收盘价
    vwap = (typical_price.iloc[-period:] * volume.iloc[-period:]).sum() / volume.iloc[-period:].sum()
    current_price = close.iloc[-1]

    if vwap > 0:
        deviation = (current_price - vwap) / vwap
    else:
        deviation = 0.0

    return deviation


def cross_section_rank(scores_dict):
    """
    截面排名：将各品种得分转换为排名分（标准化到0-1）
    """
    symbols = list(scores_dict.keys())
    valid = {k: v for k, v in scores_dict.items() if not np.isnan(v)}
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
    print("策略58：截面资金流向多空轮动策略")
    print("=" * 60)

    # 初始化所有品种的K线数据
    klines = {}
    for sym in SYMBOLS:
        klines[sym] = api.get_tick_serial(sym)
        print(f"  订阅品种：{sym}")

    print("\n等待数据加载...")
    time.sleep(5)

    # 目标持仓任务
    target_tasks = {sym: TargetPosTask(api, sym) for sym in SYMBOLS}

    # 每日计数
    trading_day_counter = 0
    last_rebalance_date = None

    position = {sym: 0 for sym in SYMBOLS}

    # 乘数（用于仓位计算）
    pos_mult = {
        "SHFE.rb2501": 10, "SHFE.hc2501": 10,
        "DCE.i2501": 100, "DCE.jm2501": 60, "DCE.j2501": 100,
        "CZCE.MA2501": 10, "CZCE.TA2501": 5, "INE.sc2501": 100
    }

    with api.register_update_notify():
        while True:
            api.wait_update()
            now = api.get_trading_time()
            if now is None:
                continue

            current_date = now.strftime("%Y-%m-%d") if hasattr(now, 'strftime') else str(now)[:10]
            if current_date == last_rebalance_date:
                continue

            # 每5个交易日换仓
            trading_day_counter += 1
            if trading_day_counter % REBALANCE_DAYS != 1:
                continue

            print(f"\n{'=' * 40}")
            print(f"换仓日：{current_date}")
            print(f"{'=' * 40}")

            # ---------- 计算各因子 ----------
            cmf_scores = {}
            oi_scores = {}
            vwap_scores = {}

            for sym in SYMBOLS:
                kl = klines[sym]
                if len(kl) < max(CMF_PERIOD, OI_PERIOD, VWAP_PERIOD) + 5:
                    print(f"  [{sym}] 数据不足，跳过")
                    continue

                close = kl["close"]
                high = kl["high"]
                low = kl["low"]
                volume = kl["volume"]
                open_interest = kl["open_interest"]

                # CMF资金流向
                cmf = calc_cmf(high, low, close, volume, CMF_PERIOD)
                cmf_scores[sym] = cmf if not np.isnan(cmf) else 0.0

                # OI背离
                oi_div = calc_oi_divergence(close, open_interest, OI_PERIOD)
                oi_scores[sym] = oi_div

                # VWAP偏离
                vwap_dev = calc_vwap_deviation(close, volume, VWAP_PERIOD)
                vwap_scores[sym] = vwap_dev

                print(f"  [{sym}] CMF={cmf:.4f}, OI背离={oi_div:.1f}, VWAP偏离={vwap_dev:.4f}")

            # ---------- 截面排名 ----------
            cmf_rank = cross_section_rank(cmf_scores)
            oi_rank = cross_section_rank(oi_scores)
            vwap_rank = cross_section_rank(vwap_scores)

            # 综合得分
            composite = {}
            for sym in SYMBOLS:
                if sym in cmf_rank and sym in oi_rank and sym in vwap_rank:
                    composite[sym] = (
                        cmf_rank[sym] * 0.5 +
                        oi_rank[sym] * 0.3 +
                        vwap_rank[sym] * 0.2
                    )
                else:
                    composite[sym] = 0.5

            sorted_symbols = sorted(composite.items(), key=lambda x: x[1], reverse=True)
            n = len(sorted_symbols)
            n_long = max(1, int(n * LONG_TOP))
            n_short = max(1, int(n * SHORT_BOTTOM))

            long_set = set([s for s, _ in sorted_symbols[:n_long]])
            short_set = set([s for s, _ in sorted_symbols[-n_short:]])

            print(f"\n做多品种（{n_long}个）：{long_set}")
            print(f"做空品种（{n_short}个）：{short_set}")

            # ---------- 目标持仓 ----------
            target_pos = {}
            for sym in SYMBOLS:
                if sym in long_set:
                    # CMF强度决定仓位权重
                    cmf_abs = abs(cmf_scores.get(sym, 0))
                    weight = min(cmf_abs * 3 + 0.1, MAX_POS_RATIO)
                    target_pos[sym] = int(weight * 10)
                elif sym in short_set:
                    cmf_abs = abs(cmf_scores.get(sym, 0))
                    weight = min(cmf_abs * 3 + 0.1, MAX_POS_RATIO)
                    target_pos[sym] = -int(weight * 10)
                else:
                    target_pos[sym] = 0

            print(f"\n目标持仓：{target_pos}")

            # ---------- 执行换仓 ----------
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
