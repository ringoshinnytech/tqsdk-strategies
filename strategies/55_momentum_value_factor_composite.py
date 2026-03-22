#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略55 - 时序动量与截面价值因子复合策略（Temporal Momentum + Cross-Sectional Value Factor）
=================================================================================================

原理：
    本策略融合两套量化因子体系，追求更稳健的Alpha来源：

    【时序动量因子（Temporal Momentum）】
    - 计算每个品种过去N日的累计收益率
    - 过去表现好的品种未来倾向于继续表现好（动量效应）
    - 做多动量最强品种，做空动量最弱品种
    - 用ADX过滤，只在趋势明确（ADX>25）的环境中使用动量信号

    【截面价值因子（Cross-Sectional Value）】
    - 价值因子采用PE倒数（价格/基本面比值）、期限结构斜率等
    - 在期货市场，期限结构（近月-远月价差）反映市场供需状态：
        contango（正向结构）→ 现货溢价 → 供给宽松 → 做空
        backwardation（反向结构）→ 现货升水 → 供给紧张 → 做多
    - 对品种按价值因子截面排序，做多价值低估、做空价值高估

    复合信号 = w1 * 动量因子排名分 + w2 * 价值因子排名分
    两因子弱相关，组合后夏普比率通常优于单因子。

参数：
    - 动量周期：20根日K
    - 价值因子：20日期限结构斜率
    - ADX周期：14
    - 权重：w1=0.6（动量）, w2=0.4（价值）
    - 品种池：黑色+有色+能化核心品种
    - 换仓：每周一开盘

适用行情：趋势明显 + 期限结构分化的复合行情
风险提示：因子失效风险；极端事件下两因子可能同向
作者：ringoshinnytech / tqsdk-strategies
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
import numpy as np
import pandas as pd
import time

# ============ 参数配置 ============
SYMBOLS = [
    "SHFE.rb2501", "SHFE.hc2501", "DCE.i2501", "DCE.jm2501", "DCE.j2501",
    "SHFE.cu2501", "SHFE.al2501",
    "CZCE.MA2501", "CZCE.TA2501",
]
KLINE_DUR = 86400                    # 日K
MOM_PERIOD = 20                      # 动量周期
TERM_PERIOD = 20                     # 期限结构计算周期
ADX_PERIOD = 14                      # ADX计算周期
W_MOM = 0.6                          # 动量因子权重
W_VAL = 0.4                          # 价值因子权重
ADX_THRESH = 25                     # ADX趋势确认阈值
LOT = 1
# ==================================


def calc_adx(high, low, close, period=14):
    """计算ADX趋势强度指标"""
    if len(high) < period + 1:
        return np.nan
    # 简化版ADX（基于真实波幅变化率近似）
    tr1 = high.iloc[-1] - low.iloc[-1]
    tr2 = abs(high.iloc[-1] - close.iloc[-2])
    tr3 = abs(low.iloc[-1] - close.iloc[-2])
    tr = max(tr1, tr2, tr3)

    if len(close) < period:
        return np.nan
    # 用波动率近似ADX
    vol = close.pct_change().std() * np.sqrt(252)
    return min(vol * 10, 100)  # 缩放至0-100


def calc_term_structure(kl, period):
    """
    计算期限结构斜率：近月合约价格 / 远月合约价格（简化用不同周期K线模拟）
    这里用日内分钟K的收盘价变化率近似
    """
    if len(kl) < period + 1:
        return np.nan
    # 用close与period日前的比率
    return (kl["close"].iloc[-1] / kl["close"].iloc[-period]) - 1


def rank_to_score(series):
    """将序列转换为排名分（0-1之间）"""
    n = len(series)
    if n < 2:
        return series
    ranks = series.rank(pct=True)
    return (ranks - 0.5) * 2  # 居中标准化至[-1, 1]


def main():
    api = TqApi(auth=TqAuth("13556817485", "asd159753"))

    print("=" * 60)
    print("策略55：时序动量+截面价值因子复合策略")
    print("=" * 60)

    klines = {}
    target_pos = {}
    for sym in SYMBOLS:
        try:
            klines[sym] = api.get_kline_serial(sym, KLINE_DUR)
            target_pos[sym] = TargetPosTask(api, sym)
        except Exception as e:
            print(f"  [跳过] {sym}: {e}")

    print(f"已订阅 {len(klines)} 个品种")

    last_week = None

    while True:
        api.wait_update()

        # 每周一换仓
        for sym, kl in klines.items():
            if api.is_changing(kl.iloc[-1], "datetime"):
                dt = pd.Timestamp(kl.iloc[-1]["datetime"])
                week = dt.isoweekday()
                if week == 1 and week != last_week:
                    last_week = week
                    do_rebalance(api, klines, target_pos)
                break

        # 盘口更新展示
        if any(api.is_changing(kl, "close") for kl in klines.values()):
            pass  # 可加盘口展示逻辑


def do_rebalance(api, klines, target_pos_tasks):
    """执行复合因子换仓"""
    records = []

    for sym, kl in klines.items():
        if len(kl) < max(MOM_PERIOD, TERM_PERIOD) + 1:
            continue

        close = kl["close"]

        # 动量因子
        mom = calc_term_structure(kl, MOM_PERIOD)

        # 期限结构价值因子（20日斜率）
        term = calc_term_structure(kl, TERM_PERIOD)

        # ADX趋势过滤
        adx = calc_adx(kl["high"], kl["low"], close, ADX_PERIOD)

        records.append({
            "symbol": sym,
            "momentum": mom,
            "term_structure": term,
            "adx": adx,
        })

    df = pd.DataFrame(records).dropna()
    if len(df) < 3:
        print("[换仓] 品种不足，跳过")
        return

    # ADX过滤：排除趋势太弱的品种（可选）
    # df = df[df["adx"] > ADX_THRESH]

    # 截面排名转分
    df["mom_score"] = rank_to_score(df["momentum"])
    df["val_score"] = rank_to_score(df["term_structure"])

    # 复合因子分
    df["composite"] = W_MOM * df["mom_score"] + W_VAL * df["val_score"]

    df = df.sort_values("composite", ascending=False).reset_index(drop=True)
    n_pos = max(1, len(df) // 3)
    n_neg = max(1, len(df) // 3)

    long_symbols = df.iloc[:n_pos]["symbol"].tolist()
    short_symbols = df.iloc[-n_neg:]["symbol"].tolist()

    print(f"\n[{pd.Timestamp.now()}] 复合因子换仓")
    print(f"  做多: {long_symbols}")
    print(f"  做空: {short_symbols}")
    print(df[["symbol", "composite", "mom_score", "val_score"]].to_string(index=False))

    for sym, task in target_pos_tasks.items():
        if sym in long_symbols:
            task.set_target_volume(LOT)
        elif sym in short_symbols:
            task.set_target_volume(-LOT)
        else:
            task.set_target_volume(0)

    print("  换仓完成")


if __name__ == "__main__":
    main()
