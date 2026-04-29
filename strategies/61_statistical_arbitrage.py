#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统计套利跨品种对冲策略
======================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
统计套利跨品种对冲策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：围绕跨品种价差的均值回归特征，用 Z-score 识别偏离并做配对对冲。
脚本默认关注 文件参数中设置的合约或品种池，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略重点观察相对强弱和价差偏离，不是单纯预测某一个品种涨跌，需要特别关注品种相关性和价差稳定性。
本策略内置多组产业或基本面联系较强的配对，例如螺纹钢与热卷、焦煤与焦炭、豆粕与豆油等。脚本会先用历史价格估算两个品种之间的对冲比例，再计算当前价差相对历史均值的偏离程度。价差明显偏高时做空价差，价差明显偏低时做多价差；当偏离收敛到较小区间时，策略平掉两边仓位。实际运行前应检查配对关系是否仍然有效、合约月份是否匹配、两边流动性是否足够，以及手续费和保证金是否会吞掉价差回归收益。


【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
策略61：统计套利跨品种对冲策略
基于协整检验的跨品种统计套利，使用z-score均值回归交易
适用于：黑色系、化工系、农产品系等具有产业链关系的品种
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ========== 策略参数 ==========
# 配对品种列表（可扩展）
PAIRS = [
    ("SHFE.rb205", "SHFE.hc205"),    # 螺纹钢-热卷
    ("DCE.j205", "DCE.jm205"),       # 焦煤-焦炭
    ("DCE.m205", "DCE.y205"),        # 豆粕-豆油
    ("CZCE.SR205", "CZCE.RM205"),    # 白糖-菜粕
    ("CZCE.JD205", "DCE.cs205"),     # 鸡蛋-玉米淀粉
]
ENTRY_ZSCORE = 1.5                   # 入场Z-score阈值
EXIT_ZSCORE = 0.3                   # 平仓Z-score阈值
LOOKBACK = 60                       # 计算均值与标准差的窗口
HEDGE_RATIOS = {}                   # 对冲比率（动态计算）
INIT_PORTFOLIO = 1000000

def calculate_hedge_ratio(series1, series2, window=20):
    """使用滚动协方差/方差计算动态对冲比率"""
    if len(series1) < window or len(series2) < window:
        return 1.0
    cov = series1.diff().rolling(window).cov(series2.diff())
    var = series1.diff().rolling(window).var()
    hr = (cov / var).iloc[-1]
    return float(hr) if not np.isnan(hr) else 1.0

def calculate_zscore(spread, window=60):
    """计算价差的Z-score"""
    if len(spread) < window:
        return 0.0
    mean = spread.iloc[-window:].mean()
    std = spread.iloc[-window:].std()
    current = spread.iloc[-1]
    if std == 0:
        return 0.0
    return (current - mean) / std

def get_spread(series1, series2, hedge_ratio):
    """计算价差序列"""
    return series1 - hedge_ratio * series2

# ========== 策略主体 ==========
def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    target_pos = {sym: TargetPosTask(api, sym) for pair in PAIRS for sym in pair}

    print(f"[策略61] 统计套利跨品种对冲策略启动 | 配对数: {len(PAIRS)}")

    klines = {}
    quotes = {}
    spread_history = {pair: pd.Series(dtype=float) for pair in PAIRS}
    positions = {pair: 0 for pair in PAIRS}

    for pair in PAIRS:
        sym1, sym2 = pair
        klines[sym1] = api.get_kline_serial(sym1, 86400, data_length=LOOKBACK + 20)
        klines[sym2] = api.get_kline_serial(sym2, 86400, data_length=LOOKBACK + 20)
        quotes[sym1] = api.get_quote(sym1)
        quotes[sym2] = api.get_quote(sym2)

    print("[策略61] 等待历史数据积累...")

    while True:
        api.wait_update()

        for pair in PAIRS:
            sym1, sym2 = pair
            kl1 = klines[sym1]
            kl2 = klines[sym2]

            if len(kl1.close) < LOOKBACK or len(kl2.close) < LOOKBACK:
                continue

            s1 = pd.Series(kl1.close)
            s2 = pd.Series(kl2.close)

            # 更新对冲比率
            hr = calculate_hedge_ratio(s1, s2, window=20)
            HEDGE_RATIOS[pair] = hr

            # 计算价差
            spread = get_spread(s1, s2, hr)
            zscore = calculate_zscore(spread, window=LOOKBACK)

            price1 = quotes[sym1].last_price
            price2 = quotes[sym2].last_price

            # ========== 交易逻辑 ==========
            # zscore > ENTRY_ZSCORE: 价差偏高，做空价差（空sym1多sym2）
            # zscore < -ENTRY_ZSCORE: 价差偏低，做多价差（多sym1空sym2）
            # |zscore| < EXIT_ZSCORE: 平仓

            position_value = INIT_PORTFOLIO / len(PAIRS)
            margin1 = price1 * 10 * 0.12
            margin2 = price2 * 10 * 0.12
            lot1 = max(1, int(position_value / margin1)) if margin1 > 0 else 1
            lot2 = max(1, int(position_value * hr / margin2)) if margin2 > 0 else 1

            if zscore > ENTRY_ZSCORE and positions[pair] == 0:
                # 价差高估：空sym1多sym2
                target_pos[sym1].set_target_volume(-lot1)
                target_pos[sym2].set_target_volume(lot2)
                positions[pair] = -1
                print(f"[策略61] {pair} | Z={zscore:.2f} | 做空价差 | HR={hr:.3f}")

            elif zscore < -ENTRY_ZSCORE and positions[pair] == 0:
                # 价差低估：多sym1空sym2
                target_pos[sym1].set_target_volume(lot1)
                target_pos[sym2].set_target_volume(-lot2)
                positions[pair] = 1
                print(f"[策略61] {pair} | Z={zscore:.2f} | 做多价差 | HR={hr:.3f}")

            elif abs(zscore) < EXIT_ZSCORE and positions[pair] != 0:
                # 回归均值：平仓
                target_pos[sym1].set_target_volume(0)
                target_pos[sym2].set_target_volume(0)
                print(f"[策略61] {pair} | Z={zscore:.2f} | 平仓 | 收益锁定")
                positions[pair] = 0

    api.close()

if __name__ == "__main__":
    main()
