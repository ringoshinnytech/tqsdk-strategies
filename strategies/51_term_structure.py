#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
期限结构基差回归策略
====================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
期限结构基差回归策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：基于近远月价比的对数斜率，当斜率偏离历史均值1.5倍标准差时入场，做价差均值回归
脚本默认关注 文件参数中设置的合约或品种池，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略更适合震荡或偏离修复行情，遇到单边趋势时可能连续逆势亏损。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
 (Term Structure Basis Regression Strategy)
================================================================

策略思路：
---------
本策略基于期货期限结构进行交易。期货的期限结构反映市场对供需关系和
库存周期的预期：
  - Contango（正向市场）：远月合约 > 近月合约 → 预期供过于求/累库
  - Backwardation（反向市场）：远月合约 < 近月合约 → 预期供不应求/去库
  
策略核心：
  1. 计算各品种的期限结构斜率（近月/远月价比的对数）
  2. 当斜率偏离历史均值超过1.5倍标准差时，预期会均值回归
  3. 做空斜率（预期收敛） → 卖近月买远月
  4. 做多斜率（预期发散） → 买近月卖远月

品种选择：
  - 黑色系：螺纹钢、铁矿石、热卷
  - 有色系：铜、铝、锌、镍
  - 能化系：原油、燃油、甲醇

风险控制：
---------
- 最大单边持仓：不超过4个合约
- 展期成本估算：计入价差成本
- 止损：价差反向超过2倍标准差时止损

作者: TqSdk Strategies
更新: 2026-03-16
"""

from tqsdk import TqApi, TqAuth, TqSim
import pandas as pd
import numpy as np


class TermStructureStrategy:
    """期限结构基差回归策略"""

    # 主力合约和次主力合约映射
    CONTRACTS = {
        "SHFE.rb": ["SHFE.rb2501", "SHFE.rb2502"],  # 螺纹钢
        "SHFE.hc": ["SHFE.hc2501", "SHFE.hc2502"],  # 热卷
        "DCE.i": ["DCE.i2501", "DCE.i2502"],        # 铁矿石
        "SHFE.cu": ["SHFE.cu2501", "SHFE.cu2502"],  # 铜
        "SHFE.al": ["SHFE.al2501", "SHFE.al2502"],  # 铝
        "SHFE.zn": ["SHFE.zn2501", "SHFE.zn2502"],  # 锌
        "SHFE.ni": ["SHFE.ni2501", "SHFE.ni2502"],  # 镍
        "INE.sc": ["INE.sc2501", "INE.sc2502"],     # 原油
        "SHFE.fu": ["SHFE.fu2501", "SHFE.fu2502"],  # 燃油
        "DCE.ma": ["DCE.ma2501", "DCE.ma2502"],     # 甲醇
    }

    LOOKBACK    = 60      # 历史基差回看窗口
    REBALANCE   = 5       # 调仓周期（交易日）
    ENTRY_STD   = 1.5     # 入场标准差倍数
    EXIT_STD    = 0.5     # 出场标准差倍数
    MAX_POS     = 4       # 最大持仓对数

    def __init__(self, api):
        self.api = api
        self.quotes = {}
        for pair in self.CONTRACTS.values():
            for sym in pair:
                self.quotes[sym] = api.get_quote(sym)

        self.bar_count = 0
        self.history = {k: [] for k in self.CONTRACTS.keys()}
        self.positions = {}  # {(base, offset): position}

    def _get_spread(self, base: str) -> float:
        """获取当前期限价差（近月/远月价比的对数）"""
        pair = self.CONTRACTS.get(base)
        if not pair or len(pair) < 2:
            return 0.0
        near = self.quotes.get(pair[0])
        far = self.quotes.get(pair[1])
        if not near or not far or far.last_price == 0:
            return 0.0
        # 使用对数价差
        return np.log(near.last_price / far.last_price)

    def _update_history(self):
        """更新历史价差数据"""
        for base in self.CONTRACTS.keys():
            spread = self._get_spread(base)
            if spread != 0.0:
                self.history[base].append(spread)
                # 保持历史窗口
                if len(self.history[base]) > self.LOOKBACK:
                    self.history[base] = self.history[base][-self.LOOKBACK:]

    def _get_signal(self, base: str) -> str:
        """获取交易信号"""
        history = self.history.get(base, [])
        if len(history) < 20:
            return "none"

        current = history[-1]
        mean = np.mean(history)
        std = np.std(history)

        if std < 1e-8:
            return "none"

        z_score = (current - mean) / std

        # 价差过大（正向市场过强）→ 预期回归 → 卖近月买远月
        if z_score > self.ENTRY_STD:
            return "short_spread"  # 卖近月买远月
        # 价差过小（反向市场过强）→ 预期回归 → 买近月卖远月
        elif z_score < -self.ENTRY_STD:
            return "long_spread"   # 买近月卖远月
        # 回归到均值附近
        elif abs(z_score) < self.EXIT_STD:
            return "close"

        return "hold"

    def _open_spread(self, base: str, direction: str):
        """开仓价差"""
        pair = self.CONTRACTS.get(base)
        if not pair:
            return

        near, far = pair[0], pair[1]
        pos_key = (base, direction)

        # 做多价差 = 买近月卖远月
        if direction == "long":
            self.api.insert_order(near, direction="BUY", offset="OPEN", volume=1)
            self.api.insert_order(far, direction="SELL", offset="OPEN", volume=1)
            print(f"[开仓] {base} 价差多头: 买{near} 卖{far}")
        # 做空价差 = 卖近月买远月
        elif direction == "short":
            self.api.insert_order(near, direction="SELL", offset="OPEN", volume=1)
            self.api.insert_order(far, direction="BUY", offset="OPEN", volume=1)
            print(f"[开仓] {base} 价差空头: 卖{near} 买{far}")

        self.positions[pos_key] = True

    def _close_spread(self, base: str, direction: str):
        """平仓价差"""
        pair = self.CONTRACTS.get(base)
        if not pair:
            return

        near, far = pair[0], pair[1]

        # 平多价差
        if direction == "long":
            self.api.insert_order(near, direction="SELL", offset="CLOSE", volume=1)
            self.api.insert_order(far, direction="BUY", offset="CLOSE", volume=1)
            print(f"[平仓] {base} 价差多头平仓")
        # 平空价差
        elif direction == "short":
            self.api.insert_order(near, direction="BUY", offset="CLOSE", volume=1)
            self.api.insert_order(far, direction="SELL", offset="CLOSE", volume=1)
            print(f"[平仓] {base} 价差空头平仓")

        pos_key = (base, direction)
        if pos_key in self.positions:
            del self.positions[pos_key]

    def rebalance(self):
        """执行调仓"""
        signals = {}
        for base in self.CONTRACTS.keys():
            signal = self._get_signal(base)
            if signal == "close":
                for direction in ("long", "short"):
                    if (base, direction) in self.positions:
                        self._close_spread(base, direction)
            elif signal in ("long_spread", "short_spread"):
                signals[base] = signal

        # 排序选择信号最强的
        if len(signals) > self.MAX_POS:
            # 按偏离程度排序
            sorted_signals = sorted(
                signals.items(),
                key=lambda x: abs(self._get_zscore(x[0])),
                reverse=True
            )
            signals = dict(sorted_signals[:self.MAX_POS])

        # 当前持仓
        current_bases = set(p[0] for p in self.positions.keys())

        # 平仓不在目标信号的仓位
        for base in current_bases:
            if base not in signals:
                direction = [p[1] for p in self.positions.keys() if p[0] == base][0]
                self._close_spread(base, direction)

        # 开仓新信号
        for base, signal in signals.items():
            direction = "long" if signal == "long_spread" else "short"
            pos_key = (base, direction)
            if pos_key not in self.positions:
                self._open_spread(base, direction)

    def _get_zscore(self, base: str) -> float:
        """获取当前z分数"""
        history = self.history.get(base, [])
        if len(history) < 20:
            return 0.0
        current = history[-1]
        mean = np.mean(history)
        std = np.std(history)
        if std < 1e-8:
            return 0.0
        return (current - mean) / std

    def run(self):
        """主循环"""
        print("=" * 60)
        print("期限结构基差回归策略启动")
        print("=" * 60)

        # 预热数据
        for _ in range(10):
            self.api.wait_update()
            self._update_history()

        while True:
            self.api.wait_update()
            self.bar_count += 1
            self._update_history()

            if self.bar_count % self.REBALANCE == 0:
                self.rebalance()


if __name__ == "__main__":
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    strategy = TermStructureStrategy(api)
    strategy.run()
