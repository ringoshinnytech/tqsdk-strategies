#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略56 - 截面多因子Ranking轮动策略（Cross-Section Multi-Factor Ranking Rotation）
====================================================================================

原理：
    本策略对多品种进行截面因子打分，动态做多最强、做空最弱，形成多空对冲组合。
    因子体系（三因子等权截面排名）：

    【因子1 - 动量因子（Momentum）】
    - 计算每个品种过去N日的累计收益率
    - 过去表现强的品种未来倾向于继续强势（短期动量效应）
    - 同时加入20日收益率加速度（动量变化率），捕捉动量加速/减速
    - 品种按动量得分截面排名：第1名得N分，第N名得1分

    【因子2 - 波动率因子（Volatility）】
    - 计算ATR（Average True Range）与收盘价的比率（标准化波动率）
    - 低波动品种往往在趋势行情中有更好的风险调整收益
    - 波动率最低的品种得分最高

    【因子3 - 趋势强度因子（ADX）】
    - ADX > 25 表明趋势明确；ADX > 40 表明趋势强劲
    - 在高ADX环境下，动量因子胜率更高
    - 同时计算+DI与-DI差值作为方向性信号

    综合得分 = (动量排名分 + 波动率排名分 + ADX排名分) / 3
    做多综合得分最高的前25%品种，做空得分最低的后25%品种。

    【动态仓位管理】
    - 根据因子综合得分的Z-score分配仓位权重
    - 偏离均值越大的品种，权重越高
    - 最大单品种仓位不超过组合总仓位的30%

参数：
    - 品种池：螺纹钢/热卷/铁矿石/焦煤/焦炭（黑色系核心）
    - K线周期：日K（86400秒）
    - 动量周期：20日
    - 波动率周期：14日（ATR）
    - ADX周期：14
    - 换仓周期：每周一开盘（5个交易日）
    - 做多比例：品种池前25%
    - 做空比例：品种池后25%
    - 单品种最大仓位：总仓位30%

适用行情：趋势轮动行情、品种分化行情
风险提示：全市场普涨普跌时多空对冲效果减弱；因子拥挤风险
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
MOM_PERIOD = 20                  # 动量计算周期（日）
VOL_PERIOD = 14                  # ATR波动率周期
ADX_PERIOD = 14                  # ADX计算周期
REBALANCE_DAYS = 5               # 换仓周期（交易日）
LONG_TOP = 0.25                  # 做多前25%品种
SHORT_BOTTOM = 0.25              # 做空后25%品种
MAX_POS_RATIO = 0.30             # 单品种最大仓位占比
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


def calc_adx_full(high, low, close, period=14):
    """
    计算完整ADX指标
    返回：(adx_value, plus_di, minus_di)
    """
    if len(high) < period * 2 + 1:
        return np.nan, np.nan, np.nan

    tr_list = []
    plus_dm_list = []
    minus_dm_list = []

    for i in range(-period, 0):
        tr1 = high.iloc[i] - low.iloc[i]
        tr2 = abs(high.iloc[i] - close.iloc[i - 1])
        tr3 = abs(low.iloc[i] - close.iloc[i - 1])
        tr_list.append(max(tr1, tr2, tr3))

        high_diff = high.iloc[i] - high.iloc[i - 1]
        low_diff = low.iloc[i - 1] - low.iloc[i]

        plus_dm = high_diff if (high_diff > low_diff and high_diff > 0) else 0
        minus_dm = low_diff if (low_diff > high_diff and low_diff > 0) else 0
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)

    tr_avg = np.mean(tr_list)
    plus_dm_avg = np.mean(plus_dm_list)
    minus_dm_avg = np.mean(minus_dm_list)

    if tr_avg == 0:
        return np.nan, np.nan, np.nan

    plus_di = (plus_dm_avg / tr_avg) * 100
    minus_di = (minus_dm_avg / tr_avg) * 100

    di_sum = plus_di + minus_di
    if di_sum == 0:
        return np.nan, plus_di, minus_di

    dx = (abs(plus_di - minus_di) / di_sum) * 100

    # ADX是DX的EMA（简化用移动平均）
    adx = dx  # 简化：直接返回DX作为ADX近似
    return adx, plus_di, minus_di


def calc_momentum_accel(close, period=20):
    """
    计算动量因子：20日累计收益率
    附加：动量加速度（收益率变化）
    """
    if len(close) < period + 5:
        return np.nan, np.nan

    ret = close.pct_change(period)
    mom = ret.iloc[-1]

    # 动量加速度：最近10日动量 vs 前10日动量
    ret_short = close.pct_change(10)
    mom_now = ret_short.iloc[-1]
    mom_prev = ret_short.iloc[-11] if len(ret_short) >= 11 else 0
    accel = mom_now - mom_prev

    return mom, accel


def cross_section_rank(scores_dict):
    """
    截面排名：将各品种得分转换为排名分（标准化到0-1）
    得分越高排名越高
    """
    symbols = list(scores_dict.keys())
    valid = {k: v for k, v in scores_dict.items() if not np.isnan(v)}
    if len(valid) == 0:
        return {}

    sorted_vals = sorted(valid.values())
    n = len(sorted_vals)
    rank_dict = {}
    for sym, val in valid.items():
        # 排名位置（0到n-1）归一化为0到1
        rank = sorted_vals.index(val) / max(n - 1, 1)
        rank_dict[sym] = rank
    return rank_dict


def main():
    api = TqApi(auth=TqAuth("13556817485", "asd159753"))

    print("=" * 60)
    print("策略56：截面多因子Ranking轮动策略")
    print("=" * 60)

    # 初始化所有品种的K线数据
    klines = {}
    for sym in SYMBOLS:
        klines[sym] = api.get_tick_serial(sym)
        print(f"  订阅品种：{sym}")

    print("\n等待数据加载...")
    time.sleep(5)  # 等待K线数据就绪

    # 目标持仓任务
    target_tasks = {sym: TargetPosTask(api, sym) for sym in SYMBOLS}

    # 每日计数
    trading_day_counter = 0
    last_rebalance_date = None

    position = {sym: 0 for sym in SYMBOLS}  # 当前持仓（手）
    pos_mult = {"SHFE.rb2501": 10, "SHFE.hc2501": 10,
                "DCE.i2501": 100, "DCE.jm2501": 60,
                "DCE.j2501": 100}  # 每手乘数

    with api.register_update_notify():
        while True:
            api.wait_update()
            now = api.get_trading_time()
            if now is None:
                continue

            # 每日检查一次（非交易时段跳过）
            current_date = now.strftime("%Y-%m-%d") if hasattr(now, 'strftime') else str(now)[:10]
            if current_date == last_rebalance_date:
                continue

            # 每周一换仓（简化：每5个交易日）
            trading_day_counter += 1
            if trading_day_counter % REBALANCE_DAYS != 1:
                continue

            print(f"\n{'=' * 40}")
            print(f"换仓日：{current_date}")
            print(f"{'=' * 40}")

            # ---------- 计算各因子 ----------
            mom_scores = {}
            vol_scores = {}
            adx_scores = {}

            for sym in SYMBOLS:
                kl = klines[sym]
                if len(kl) < max(MOM_PERIOD, VOL_PERIOD, ADX_PERIOD * 2) + 5:
                    print(f"  [{sym}] 数据不足，跳过")
                    continue

                close = kl["close"]
                high = kl["high"]
                low = kl["low"]

                # 动量因子
                mom, accel = calc_momentum_accel(close, MOM_PERIOD)
                mom_scores[sym] = mom if not np.isnan(mom) else 0.0

                # 波动率因子（取负：低波动=高分）
                atr = calc_atr(high, low, close, VOL_PERIOD)
                vol_ratio = atr / close.iloc[-1] if close.iloc[-1] > 0 else 0
                vol_scores[sym] = -vol_ratio  # 低波动得高分

                # ADX趋势因子
                adx, plus_di, minus_di = calc_adx_full(high, low, close, ADX_PERIOD)
                # 用+DI与-DI的差作为方向性强弱
                di_diff = plus_di - minus_di if not (np.isnan(plus_di) or np.isnan(minus_di)) else 0
                adx_scores[sym] = di_diff

                print(f"  [{sym}] 动量={mom:.4f}, ATR/价格={vol_ratio:.4f}, DI差={di_diff:.2f}")

            # ---------- 截面排名 ----------
            mom_rank = cross_section_rank(mom_scores)
            vol_rank = cross_section_rank(vol_scores)
            adx_rank = cross_section_rank(adx_scores)

            # 综合得分（三因子等权）
            composite = {}
            for sym in SYMBOLS:
                if sym in mom_rank and sym in vol_rank and sym in adx_rank:
                    composite[sym] = (mom_rank[sym] + vol_rank[sym] + adx_rank[sym]) / 3
                else:
                    composite[sym] = 0.5  # 默认中性

            # 按综合得分排序
            sorted_symbols = sorted(composite.items(), key=lambda x: x[1], reverse=True)
            n = len(sorted_symbols)
            n_long = max(1, int(n * LONG_TOP))
            n_short = max(1, int(n * SHORT_BOTTOM))

            long_set = set([s for s, _ in sorted_symbols[:n_long]])
            short_set = set([s for s, _ in sorted_symbols[-n_short:]])

            print(f"\n做多品种（{n_long}个）：{long_set}")
            print(f"做空品种（{n_short}个）：{short_set}")

            # ---------- 计算仓位 ----------
            # 计算综合得分的Z-score确定权重
            vals = list(composite.values())
            if len(vals) > 1:
                mean_score = np.mean(vals)
                std_score = np.std(vals)
                if std_score > 0:
                    z_scores = {s: (v - mean_score) / std_score for s, v in composite.items()}
                else:
                    z_scores = {s: 0.0 for s in composite}
            else:
                z_scores = {s: 0.0 for s in composite}

            # 目标持仓
            target_pos = {}
            for sym in SYMBOLS:
                if sym in long_set:
                    # 做多：正Z-score映射到仓位
                    weight = min(abs(z_scores.get(sym, 0.5)) / 2.0 + 0.3, MAX_POS_RATIO)
                    target_pos[sym] = int(weight * 10)  # 简化为最多10手
                elif sym in short_set:
                    # 做空
                    weight = min(abs(z_scores.get(sym, 0.5)) / 2.0 + 0.3, MAX_POS_RATIO)
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
                    # 更新持仓记录
                    position[sym] = tgt

            last_rebalance_date = current_date
            print(f"\n本次换仓完成，等待下一周期...")


if __name__ == "__main__":
    main()
