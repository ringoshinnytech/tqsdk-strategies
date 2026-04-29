#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
宏观因子轮转截面策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
宏观因子轮转截面策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：构建经济增长、通胀和流动性等宏观因子暴露，对期货品种做横截面轮转。
脚本默认关注 文件参数中设置的合约或品种池，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略适合同时跟踪多个品种，通过横向比较选择交易对象，需要关注品种池、流动性和因子稳定性。
本策略把多个商品期货品种放在同一个池子里比较，核心不是判断单个品种的绝对涨跌，而是筛选当下综合表现更强的一组品种。脚本会计算中短期动量、低波动、流动性和近期强弱等因子，统一标准化后加权得到综合分，再定期轮转到排名靠前的品种。实际使用时应定期更新合约、剔除流动性不足品种，并观察因子权重在不同市场阶段是否过度偏向某一类行情。


【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
策略62：宏观因子轮转截面策略
基于多资产横截面数据，构建宏观因子（经济增长+通胀+流动性）
对各期货品种进行因子暴露打分，动态轮转到最强因子方向
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ========== 策略参数 ==========
# 监控品种列表（根据实际行情可调整合约代码）
ASSETS = [
    "SHFE.rb2505",    # 螺纹钢
    "DCE.i2505",      # 铁矿石
    "DCE.j2505",      # 焦炭
    "DCE.jm2505",     # 焦煤
    "SHFE.hc2505",    # 热卷
    "DCE.c2505",      # 玉米
    "DCE.cs2505",     # 玉米淀粉
    "DCE.m2505",      # 豆粕
    "CZCE.rm2505",    # 菜粕
    "CZCE.OI2505",    # 菜油
    "CZCE.P2505",     # 棕榈油
    "DCE.y2505",      # 豆油
    "SHFE.cu2505",    # 铜
    "SHFE.al2505",    # 铝
    "SHFE.zn2505",    # 锌
    "SHFE.au2506",    # 黄金
    "SHFE.ag2506",    # 白银
    "DCE.pp2505",     # PP塑料
    "DCE.l2505",      # LLDPE
    "SHFE.fu2505",    # 燃料油
]

# 因子权重（可根据市场环境动态调整）
FACTOR_WEIGHTS = {
    "momentum_20d": 0.30,     # 20日动量因子
    "momentum_60d": 0.15,     # 60日动量因子
    "volatility": 0.20,       # 低波动率因子（逆波动）
    "liquidity": 0.15,        # 流动性因子
    "strength": 0.20,        # 近日强势因子
}

# 轮动参数
TOP_N = 5                     # 持有Top N强势品种
REBALANCE_DAYS = 5            # 再平衡周期（天）
INIT_PORTFOLIO = 2000000
MAX_POS_PER_ASSET = 0.20     # 单品种最大仓位占比

# ========== 因子计算函数 ==========
def calc_momentum(price_series, period):
    """计算动量因子：period日内收益率"""
    if len(price_series) < period:
        return 0.0
    return (price_series.iloc[-1] / price_series.iloc[-period]) - 1

def calc_volatility(price_series, period=20):
    """计算波动率因子：period日收益率标准差的逆"""
    if len(price_series) < period:
        return 0.0
    returns = price_series.pct_change().dropna()
    if len(returns) < period:
        return 0.0
    vol = returns.iloc[-period:].std()
    return 1.0 / (vol + 1e-8)  # 波动率越低分越高

def calc_liquidity(quote, window=5):
    """计算流动性因子：成交量与持仓量变化"""
    try:
        volume = quote.volume if hasattr(quote, 'volume') else 0
        open_interest = quote.open_interest if hasattr(quote, 'open_interest') else 0
        # 简化为成交量/持仓量比
        if open_interest > 0:
            return volume / open_interest
        return 0.0
    except:
        return 0.0

def calc_strength(price_series, lookback=5):
    """计算近期强势因子：近N日走势强度"""
    if len(price_series) < lookback + 1:
        return 0.0
    recent = price_series.iloc[-lookback:]
    earlier = price_series.iloc[-(lookback * 2):-lookback]
    if len(earlier) == 0:
        return 0.0
    return (recent.iloc[-1] / recent.iloc[0]) / (earlier.iloc[-1] / earlier.iloc[0] + 1e-8)

def calc_all_factors(klines_dict, quotes_dict):
    """计算所有品种的因子得分，返回DataFrame"""
    records = []
    for sym in ASSETS:
        if sym not in klines_dict:
            continue
        kl = klines_dict[sym]
        if len(kl.close) < 60:
            continue

        price = pd.Series(kl.close)
        quote = quotes_dict.get(sym)

        mom_20 = calc_momentum(price, 20)
        mom_60 = calc_momentum(price, 60)
        vol_factor = calc_volatility(price, 20)
        liq = calc_liquidity(quote) if quote else 0.0
        strength = calc_strength(price, 5)

        # 标准化因子（z-score）
        records.append({
            "symbol": sym,
            "momentum_20d": mom_20,
            "momentum_60d": mom_60,
            "volatility": vol_factor,
            "liquidity": liq,
            "strength": strength,
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    # Z-score标准化
    for col in ["momentum_20d", "momentum_60d", "volatility", "liquidity", "strength"]:
        mean = df[col].mean()
        std = df[col].std()
        df[f"{col}_z"] = (df[col] - mean) / (std + 1e-8)

    # 综合因子得分
    df["composite_score"] = (
        FACTOR_WEIGHTS["momentum_20d"] * df["momentum_20d_z"] +
        FACTOR_WEIGHTS["momentum_60d"] * df["momentum_60d_z"] +
        FACTOR_WEIGHTS["volatility"] * df["volatility_z"] +
        FACTOR_WEIGHTS["liquidity"] * df["liquidity_z"] +
        FACTOR_WEIGHTS["strength"] * df["strength_z"]
    )

    return df

# ========== 策略主体 ==========
def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    target_pos = {sym: TargetPosTask(api, sym) for sym in ASSETS}

    print(f"[策略62] 宏观因子轮转截面策略启动 | 品种数: {len(ASSETS)}")
    print(f"         因子权重: {FACTOR_WEIGHTS}")

    # 初始化数据
    klines = {}
    quotes = {}
    for sym in ASSETS:
        try:
            klines[sym] = api.get_kline_serial(sym, 86400, data_length=120)
            quotes[sym] = api.get_quote(sym)
        except Exception as e:
            print(f"         跳过 {sym}: {e}")

    print("[策略62] 等待历史数据积累（需60日K线）...")

    day_count = 0
    current_positions = {}  # 当前持仓symbol -> lot

    while True:
        api.wait_update()
        day_count += 1

        # 每REBALANCE_DAYS天重新计算因子并调仓
        if day_count % REBALANCE_DAYS != 0:
            continue

        df_factors = calc_all_factors(klines, quotes)
        if df_factors.empty or len(df_factors) < 5:
            print(f"[策略62] 数据不足，跳过第{day_count}天")
            continue

        # 按综合得分排序
        df_factors = df_factors.sort_values("composite_score", ascending=False)

        # 取Top N做多（不做空，仅做多）
        top_assets = df_factors.head(TOP_N)
        long_symbols = list(top_assets["symbol"])

        print(f"\n[策略62] Day {day_count} | 因子轮转调仓")
        print(f"         Top {TOP_N} 品种: {long_symbols}")
        print(f"         得分: {dict(zip(top_assets['symbol'], top_assets['composite_score'].round(3)))}")

        # 计算目标仓位
        target_value = INIT_PORTFOLIO / TOP_N
        pos_per_lot = {}

        for sym in ASSETS:
            quote = quotes.get(sym)
            if not quote:
                continue
            price = quote.last_price
            if price <= 0 or np.isnan(price):
                continue

            margin = price * 10 * 0.12  # 期货保证金估算
            if margin <= 0:
                continue
            max_lot = int(INIT_PORTFOLIO * MAX_POS_PER_ASSET / margin)
            lot = min(max_lot, 1)

            if sym in long_symbols:
                # 分配仓位
                pos_lot = max(1, int(target_value / margin))
                pos_per_lot[sym] = min(pos_lot, max_lot)
            else:
                pos_per_lot[sym] = 0

        # 下单调仓
        for sym, lot in pos_per_lot.items():
            try:
                current_lot = current_positions.get(sym, 0)
                if lot != current_lot:
                    target_pos[sym].set_target_volume(lot)
                    current_positions[sym] = lot
                    if lot > 0:
                        print(f"         做多 {sym}: {lot}手")
                    elif lot == 0 and current_lot > 0:
                        print(f"         平仓 {sym}")
            except Exception as e:
                print(f"         下单失败 {sym}: {e}")

    api.close()

if __name__ == "__main__":
    main()
