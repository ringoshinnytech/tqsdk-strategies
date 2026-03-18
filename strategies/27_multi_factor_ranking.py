#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多因子截面排名策略（Multi-Factor Cross-Sectional Ranking Strategy）
===================================================================

策略逻辑：
    对多个期货品种同时计算多个技术因子（动量、波动率、趋势强度），
    将各因子标准化后进行等权打分，综合排名最高的做多，排名最低的做空。
    每隔 N 根 K 线重新排名并换仓，形成截面多空组合。

【核心思想】
    - 截面动量：过去动量强的品种未来可能延续强势
    - 截面波动率：低波动的品种往往有更好的风险调整收益
    - 截面趋势：趋势指标强的品种趋势延续概率更高
    三者加权构建综合得分，形成截面多空对冲组合。

适用品种：
    黑色系（rb/hc/i/jm/j）、有色系（cu/zn/al/ni/sn）、能化系（sc/bu/ta/MA/PP）等
    建议品种数量 ≥ 5，以分散单品种特异性风险

风险提示：
    - 多因子模型存在因子失效风险，需定期审视因子有效性
    - 截面排名结果与品种相关性有关，相关性下降时对冲效果减弱
    - 本代码仅供学习参考，不构成任何投资建议

参数说明：
    SYMBOLS        : 交易品种列表
    FACTORS        : 因子权重字典 {因子名: 权重}
    LOOKBACK       : 因子计算回看周期（K线根数）
    REBALANCE_BARS : 换仓周期（K线根数）
    TOP_N / BOT_N  : 做多/做空品种数量
    VOLUME         : 每品种持仓手数

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from tqsdk import TqApi, TqAuth, TqSim
import numpy as np
import time

# ===================== 策略参数 =====================
SYMBOLS = [
    "SHFE.rb2501", "SHFE.hc2501", "DCE.i2501", "DCE.jm2501", "DCE.j2501"
]
KLINE_DUR = 86400           # K线周期：86400秒 = 日K
LOOKBACK = 20               # 因子回看周期（日K根数）
REBALANCE_BARS = 10         # 换仓周期（日K根数）
TOP_N = 1                   # 做多排名靠前品种数量
BOT_N = 1                   # 做空排名靠末品种数量
VOLUME = 1                  # 每品种持仓手数

# 因子权重（可调整）
FACTOR_WEIGHTS = {
    "momentum": 0.4,        # 动量因子权重（近20日收益率）
    "volatility": 0.3,      # 波动率因子权重（低波做多，高波做空）
    "trend": 0.3,           # 趋势强度因子权重（ADX类指标）
}
# ===================================================


def calc_momentum(kl, period):
    """动量因子：period日内收益率（越高越好）"""
    if len(kl) < period + 1:
        return np.nan
    ret = (kl["close"].iloc[-1] - kl["close"].iloc[-period]) / kl["close"].iloc[-period]
    return ret


def calc_volatility(kl, period):
    """波动率因子：period日内收益率标准差的倒数（越低越好，故取负）"""
    if len(kl) < period + 1:
        return np.nan
    rets = kl["close"].pct_change().dropna()
    if len(rets) < period:
        return np.nan
    vol = rets[-period:].std()
    if vol == 0:
        return np.nan
    return -1.0 / vol  # 低波动 → 得分高，故取负


def calc_trend_strength(kl, period):
    """趋势强度因子：(收盘-均线)/均线 标准差（越高趋势越强）"""
    if len(kl) < period + 1:
        return np.nan
    close = kl["close"].iloc[-period:]
    ma = close.mean()
    if ma == 0:
        return np.nan
    trend = (close - ma) / ma
    strength = trend.std()
    return strength


def normalize_factor(scores_dict):
    """将因子得分标准化到 [0, 1] 区间（Z-score归一化）"""
    values = [v for v in scores_dict.values() if v is not None and not np.isnan(v)]
    if len(values) < 2:
        return scores_dict
    mean = np.mean(values)
    std = np.std(values)
    if std == 0:
        return {k: 0.5 for k in scores_dict}
    return {k: (v - mean) / std if v is not None else 0.5 for k, v in scores_dict.items()}


def main():
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅各品种日K线
    klines = {sym: api.get_kline_serial(sym, KLINE_DUR, data_length=LOOKBACK + 5)
              for sym in SYMBOLS}

    bar_count = 0
    long_set = set()
    short_set = set()

    print(f"[策略启动] 多因子截面排名策略 | 品种数: {len(SYMBOLS)} | 换仓周期: {REBALANCE_BARS}根日K")

    try:
        while True:
            api.wait_update()

            # 检查任意品种K线是否有更新（以日期变化为准）
            updated = any(
                api.is_changing(klines[sym].iloc[-1], "datetime")
                for sym in SYMBOLS
            )
            if not updated:
                continue

            bar_count += 1
            if bar_count % REBALANCE_BARS != 0:
                continue

            # ---- 计算各品种因子得分 ----
            factor_scores = {}
            for sym in SYMBOLS:
                kl = klines[sym]
                scores = {}
                scores["momentum"] = calc_momentum(kl, LOOKBACK)
                scores["volatility"] = calc_volatility(kl, LOOKBACK)
                scores["trend"] = calc_trend_strength(kl, LOOKBACK)
                factor_scores[sym] = scores

            # ---- 标准化各因子 ----
            norm_scores = {}
            for sym in factor_scores:
                ns = {}
                ns["momentum"] = normalize_factor({sym: factor_scores[sym]["momentum"] for sym in [sym]})
                ns["volatility"] = normalize_factor({sym: factor_scores[sym]["volatility"] for sym in [sym]})
                ns["trend"] = normalize_factor({sym: factor_scores[sym]["trend"] for sym in [sym]})
                # 简化为直接使用原始值，后续统一标准化
                norm_scores[sym] = factor_scores[sym]

            # ---- 统一标准化 ----
            momentum_vals = {s: factor_scores[s]["momentum"] for s in factor_scores}
            vol_vals = {s: factor_scores[s]["volatility"] for s in factor_scores}
            trend_vals = {s: factor_scores[s]["trend"] for s in factor_scores}

            mom_norm = normalize_factor(momentum_vals)
            vol_norm = normalize_factor(vol_vals)
            trend_norm = normalize_factor(trend_vals)

            # ---- 计算综合得分 ----
            composite = {}
            for sym in factor_scores:
                c = (
                    FACTOR_WEIGHTS["momentum"] * mom_norm.get(sym, 0) +
                    FACTOR_WEIGHTS["volatility"] * vol_norm.get(sym, 0) +
                    FACTOR_WEIGHTS["trend"] * trend_norm.get(sym, 0)
                )
                composite[sym] = c

            ranked = sorted(composite.items(), key=lambda x: x[1], reverse=True)
            new_long = set([r[0] for r in ranked[:TOP_N]])
            new_short = set([r[0] for r in ranked[-BOT_N:]])

            print(f"[换仓日] 排名: {[(s, f'{v:.3f}') for s, v in ranked]}")
            print(f"  做多: {new_long} | 做空: {new_short}")

            # ---- 平旧仓 ----
            close_long = long_set - new_long
            close_short = short_set - new_short
            for sym in close_long:
                pos = api.get_position(sym)
                if pos.pos_long > 0:
                    api.insert_order(sym, direction="SELL", offset="CLOSE", volume=pos.pos_long)
                    print(f"  平多: {sym}")
            for sym in close_short:
                pos = api.get_position(sym)
                if pos.pos_short > 0:
                    api.insert_order(sym, direction="BUY", offset="CLOSE", volume=pos.pos_short)
                    print(f"  平空: {sym}")

            api.wait_update()

            # ---- 开新仓 ----
            for sym in new_long - long_set:
                api.insert_order(sym, direction="BUY", offset="OPEN", volume=VOLUME)
                print(f"  开多: {sym}")
            for sym in new_short - short_set:
                api.insert_order(sym, direction="SELL", offset="OPEN", volume=VOLUME)
                print(f"  开空: {sym}")

            long_set = new_long
            short_set = new_short
            time.sleep(0.1)

    finally:
        api.close()


if __name__ == "__main__":
    main()
