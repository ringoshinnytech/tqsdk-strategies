#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
跨品种产业链对冲轮转策略
========================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
跨品种产业链对冲轮转策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：按上游原材料、中游加工和下游成品的产业链关系，交易利润偏离较大的配对机会。
脚本默认关注 文件参数中设置的合约或品种池，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略重点观察相对强弱和价差偏离，不是单纯预测某一个品种涨跌，需要特别关注品种相关性和价差稳定性。
本策略把同一产业链中的上游、中游、下游合约放在一起观察，例如原材料价格、加工品价格和成品价格之间的利润关系。脚本会持续计算产业链内部价差或利润偏离，当偏离超过阈值时做相对价值交易，等待利润关系回到更正常的区间。运行前需要确认合约确实属于同一条产业链，价格单位、乘数和交割月份具有可比性，并留意政策、库存、运输、限产等因素带来的结构性变化。


【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
策略63：跨品种产业链对冲轮转策略
基于产业链逻辑（上游原材料→中游加工→下游成品）
动态计算产业链利润偏离，对偏离均值较大的品种配对进行对冲交易
同时结合动量因子做方向判断，提升对冲胜率
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ========== 策略参数 ==========
# 核心产业链配置
CHAINS = [
    {
        "name": "钢铁产业链",
        "upstream": "DCE.i2505",        # 铁矿石（上游）
        "midstream": "DCE.j2505",         # 焦炭（中游）
        "downstream": "SHFE.rb2505",      # 螺纹钢（下游）
        "ratio_up_mid": 1.6,              # 焦炭/铁矿石比值参考
        "ratio_mid_down": 3.5,            # 螺纹钢/焦炭比值参考
    },
    {
        "name": "油脂产业链",
        "upstream": "DCE.y2505",          # 豆油（上游）
        "midstream": "DCE.m2505",         # 豆粕（中游）
        "downstream": "CZCE.OI2505",      # 菜油（下游）
        "ratio_up_mid": 0.65,
        "ratio_mid_down": 0.55,
    },
    {
        "name": "有色金属产业链",
        "upstream": "SHFE.cu2505",        # 铜（上游）
        "midstream": "SHFE.zn2505",       # 锌（中游）
        "downstream": "SHFE.al2505",      # 铝（下游）
        "ratio_up_mid": 2.5,
        "ratio_mid_down": 1.8,
    },
]

# 交易参数
ENTRY_ZSCORE = 1.5                    # 入场Z-score阈值
EXIT_ZSCORE = 0.3                     # 平仓Z-score阈值
HISTORY_PERIOD = 30                   # 计算均值回归的历史窗口
INIT_PORTFOLIO = 2000000
CHAIN_POSITION_SIZE = 0.20           # 单产业链最大仓位

# ========== 产业链偏离计算 ==========
def calc_chain_deviation(klines_dict, chain):
    """计算产业链比值偏离度"""
    up = chain["upstream"]
    mid = chain["midstream"]
    down = chain["downstream"]

    for sym in [up, mid, down]:
        if sym not in klines_dict:
            return None, None
        kl = klines_dict[sym]
        if len(kl.close) < HISTORY_PERIOD:
            return None, None

    price_up = klines_dict[up].close[-1]
    price_mid = klines_dict[mid].close[-1]
    price_down = klines_dict[down].close[-1]

    if price_up <= 0 or price_mid <= 0 or price_down <= 0:
        return None, None

    # 计算两个比值
    ratio_up_mid = price_up / price_mid
    ratio_mid_down = price_mid / price_down

    # 理论比值
    theory_up_mid = chain["ratio_up_mid"]
    theory_mid_down = chain["ratio_mid_down"]

    # 偏离度（百分比）
    dev_up_mid = (ratio_up_mid / theory_up_mid) - 1
    dev_mid_down = (ratio_mid_down / theory_mid_down) - 1

    return dev_up_mid, dev_mid_down

def calc_zscore(current_dev, dev_history):
    """计算Z-score"""
    if len(dev_history) < HISTORY_PERIOD:
        return 0.0
    hist = dev_history[-HISTORY_PERIOD:]
    mean = np.mean(hist)
    std = np.std(hist)
    if std < 1e-8:
        return 0.0
    return (current_dev - mean) / std

# ========== 策略主体 ==========
def main():
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))

    print(f"[策略63] 跨品种产业链对冲轮转策略启动 | 产业链: {len(CHAINS)}")

    # 初始化数据
    all_symbols = set()
    for chain in CHAINS:
        all_symbols.update([chain["upstream"], chain["midstream"], chain["downstream"]])
    target_pos = {sym: TargetPosTask(api, sym) for sym in all_symbols}

    klines = {}
    for sym in all_symbols:
        try:
            klines[sym] = api.get_kline_serial(sym, 86400, data_length=120)
        except Exception as e:
            print(f"[策略63] 跳过 {sym}: {e}")

    print("[策略63] 等待历史数据积累...")

    # 历史记录
    dev_history = {chain["name"]: {"up_mid": [], "mid_down": []} for chain in CHAINS}
    positions = {chain["name"]: 0 for chain in CHAINS}  # 0=无仓, 1=多下空上, -1=多上空下

    day_count = 0

    while True:
        api.wait_update()
        day_count += 1

        for chain in CHAINS:
            chain_name = chain["name"]
            dev_up_mid, dev_mid_down = calc_chain_deviation(klines, chain)

            if dev_up_mid is None:
                continue

            # 记录历史
            dev_history[chain_name]["up_mid"].append(dev_up_mid)
            dev_history[chain_name]["mid_down"].append(dev_mid_down)

            if len(dev_history[chain_name]["up_mid"]) < HISTORY_PERIOD:
                continue

            # 计算Z-score
            z_up_mid = calc_zscore(dev_up_mid, dev_history[chain_name]["up_mid"])
            z_mid_down = calc_zscore(dev_mid_down, dev_history[chain_name]["mid_down"])

            # 综合信号（取绝对值最大的方向）
            z_signal = z_up_mid if abs(z_up_mid) > abs(z_mid_down) else z_mid_down

            print(f"[策略63] {chain_name} | Z={z_signal:.2f} | "
                  f"上游/中游偏离={dev_up_mid:.2%} | 中游/下游偏离={dev_mid_down:.2%}")

            up_sym = chain["upstream"]
            mid_sym = chain["midstream"]
            down_sym = chain["downstream"]

            # 保证金估算
            def get_margin(sym):
                if sym in klines and len(klines[sym].close) > 0:
                    return klines[sym].close[-1] * 10 * 0.12
                return 10000

            margin_unit = max(get_margin(up_sym), get_margin(down_sym))
            chain_value = INIT_PORTFOLIO * CHAIN_POSITION_SIZE
            lot = max(1, int(chain_value / margin_unit / 2))

            # 入场逻辑
            if z_signal > ENTRY_ZSCORE and positions[chain_name] == 0:
                # 产业链比值偏高：做空上游，做多下游（利润被压缩）
                target_pos[up_sym].set_target_volume(-lot)
                target_pos[down_sym].set_target_volume(lot)
                target_pos[mid_sym].set_target_volume(0)
                positions[chain_name] = -1
                print(f"         >>> 入场: 做空{chain['upstream']}/做多{chain['downstream']} "
                      f"(Z={z_signal:.2f}, 产业链扩张)")

            elif z_signal < -ENTRY_ZSCORE and positions[chain_name] == 0:
                # 产业链比值偏低：做多上游，做空下游（利润被挤压）
                target_pos[up_sym].set_target_volume(lot)
                target_pos[down_sym].set_target_volume(-lot)
                target_pos[mid_sym].set_target_volume(0)
                positions[chain_name] = 1
                print(f"         >>> 入场: 做多{chain['upstream']}/做空{chain['downstream']} "
                      f"(Z={z_signal:.2f}, 产业链收缩)")

            # 平仓逻辑
            elif abs(z_signal) < EXIT_ZSCORE and positions[chain_name] != 0:
                target_pos[up_sym].set_target_volume(0)
                target_pos[mid_sym].set_target_volume(0)
                target_pos[down_sym].set_target_volume(0)
                print(f"         >>> 平仓: 产业链偏离修复")
                positions[chain_name] = 0

        # 每10天打印一次汇总
        if day_count % 10 == 0:
            active = [k for k, v in positions.items() if v != 0]
            print(f"\n[策略63] Day {day_count} | 持仓产业链: {active or '无'}")

    api.close()

if __name__ == "__main__":
    main()
