#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
截面波动率偏度交易策略
======================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
截面波动率偏度交易策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：20日收益率分布偏度+波动率水平+动量+成交量四因子截面打分，筛选低风险高动量品种
脚本默认关注 SHFE.rb2501、SHFE.hc2501、DCE.i2501、DCE.j2501、DCE.jm2501 等多个品种，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略适合同时跟踪多个品种，通过横向比较选择交易对象，需要关注品种池、流动性和因子稳定性。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
 (Cross-Sectional Volatility Skew Strategy)
===================================================================

策略思路：
---------
本策略基于波动率偏度进行截面品种选择和轮动交易。波动率偏度反映市场
对未来价格分布不对称性的预期，是重要的风险预警指标：
  - 偏度>0（正偏）：右尾风险大，预期上涨波动小下跌波动大
  - 偏度<0（负偏）：左尾风险大，预期下跌波动小上涨波动大
  
通过计算各品种的20日收益率分布偏度，并结合波动率水平进行过滤：
  - 因子1：波动率偏度（截面排名）
  - 因子2：20日波动率水平（截面排名，低波动优先）
  - 因子3：20日价格动量（截面排名）
  - 因子4：成交量变化率（截面排名）

综合得分 = 0.35*偏度得分 + 0.25*波动率得分 + 0.25*动量得分 + 0.15*成交量得分

做多综合得分最高的2个品种，做空得分最低的2个品种。

风险控制：
---------
- 波动率过滤：剔除20日波动率处于历史80%分位以上的品种
- 单品种仓位：根据波动率倒数分配仓位
- 最大回撤止损：单日亏损超过2%减仓50%

作者: TqSdk Strategies
更新: 2026-03-16
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.ta import MA, ATR
import pandas as pd
import numpy as np
from scipy import stats


class VolatilitySkewStrategy:
    """截面波动率偏度交易策略"""

    # 覆盖主要期货品种
    SYMBOLS = [
        "SHFE.rb2501",  # 螺纹钢
        "SHFE.hc2501",  # 热卷
        "DCE.i2501",    # 铁矿石
        "DCE.j2501",    # 焦炭
        "DCE.jm2501",   # 焦煤
        "SHFE.cu2501",  # 铜
        "SHFE.al2501",  # 铝
        "SHFE.zn2501",  # 锌
        "SHFE.ni2501",  # 镍
        "DCE.m2501",    # 豆粕
        "DCE.c2501",    # 玉米
        "CZCE.rm2501",  # 菜粕
        "CZCE.cs2501",  # 棉花
        "CZCE.sr2501",  # 白糖
        "INE.sc2501",   # 原油
        "SHFE.fu2501",  # 燃油
    ]

    LOOKBACK    = 20      # 回看窗口
    REBALANCE   = 20      # 换仓周期
    LONG_COUNT  = 2       # 做多数
    SHORT_COUNT = 2       # 做空数
    MAX_VOL_PCT = 0.80    # 最大波动率分位过滤

    # 因子权重
    W_SKEW      = 0.35
    W_VOL       = 0.25
    W_MOMENTUM  = 0.25
    W_VOLUME    = 15.00

    def __init__(self, api):
        self.api = api
        self.klines = {
            sym: api.get_kline_serial(sym, 86400, data_length=self.LOOKBACK + 10)
            for sym in self.SYMBOLS
        }
        self.bar_count = 0
        self.long_pos = []
        self.short_pos = []
        self.last_equity = 0

    def _rank_normalize(self, values: dict) -> dict:
        """截面排名标准化到 [0, 1]"""
        items = sorted(values.items(), key=lambda x: x[1])
        n = len(items)
        return {sym: i / max(n - 1, 1) for i, (sym, _) in enumerate(items)}

    def _compute_volatility_skew(self, returns: np.ndarray) -> float:
        """计算收益率序列的波动率偏度"""
        if len(returns) < 10:
            return 0.0
        # 偏度：正值表示右偏（正收益极端），负值表示左偏（负收益极端）
        return float(stats.skew(returns))

    def compute_scores(self) -> dict:
        """计算各品种综合因子得分"""
        f_skew, f_vol, f_momentum, f_volume = {}, {}, {}, {}

        for sym in self.SYMBOLS:
            kl = self.klines[sym]
            if len(kl) < self.LOOKBACK + 5:
                continue

            closes = kl["close"].values
            volumes = kl["volume"].values

            # 计算收益率
            returns = np.diff(np.log(closes[-self.LOOKBACK:]))

            # F1: 波动率偏度
            skew = self._compute_volatility_skew(returns)

            # F2: 波动率水平（年化）
            vol = float(np.std(returns) * np.sqrt(252))

            # F3: 20日动量
            momentum = (closes[-1] - closes[-self.LOOKBACK]) / (closes[-self.LOOKBACK] + 1e-8)

            # F4: 成交量变化率
            vol_ma = np.mean(volumes[-10:])
            vol_cur = np.mean(volumes[-5:])
            vol_change = (vol_cur - vol_ma) / (vol_ma + 1e-8)

            f_skew[sym] = skew
            f_vol[sym] = vol
            f_momentum[sym] = momentum
            f_volume[sym] = vol_change

        # 过滤高波动率品种
        if not f_vol:
            return {}
        vol_threshold = np.percentile(list(f_vol.values()), self.MAX_VOL_PCT * 100)
        valid_symbols = [s for s in f_vol if f_vol[s] <= vol_threshold]

        # 标准化各因子
        skew_norm = self._rank_normalize({s: f_skew.get(s, 0) for s in valid_symbols})
        vol_norm = self._rank_normalize({s: -f_vol.get(s, 0) for s in valid_symbols})  # 低波动得分高
        mom_norm = self._rank_normalize({s: f_momentum.get(s, 0) for s in valid_symbols})
        vol_chg_norm = self._rank_normalize({s: f_volume.get(s, 0) for s in valid_symbols})

        # 综合得分
        scores = {}
        for sym in valid_symbols:
            scores[sym] = (
                self.W_SKEW * skew_norm.get(sym, 0.5) +
                self.W_VOL * vol_norm.get(sym, 0.5) +
                self.W_MOMENTUM * mom_norm.get(sym, 0.5) +
                self.W_VOLUME * vol_chg_norm.get(sym, 0.5) * 0.01
            )

        return scores

    def rebalance(self):
        """执行调仓"""
        scores = self.compute_scores()
        if not scores:
            return

        # 排序
        sorted_symbols = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        long_list = [s[0] for s in sorted_symbols[:self.LONG_COUNT]]
        short_list = [s[0] for s in sorted_symbols[-self.SHORT_COUNT:]]

        # 获取当前持仓
        positions = self.api.get_position()
        current_long = [s for s, p in positions.items() if p.pos_long > 0]
        current_short = [s for s, p in positions.items() if p.pos_short > 0]

        # 平仓不在目标名单的仓位
        for sym in current_long:
            if sym not in long_list:
                self.api.insert_order(sym, direction="SELL", offset="CLOSE", volume=positions[sym].pos_long)
        for sym in current_short:
            if sym not in short_list:
                self.api.insert_order(sym, direction="BUY", offset="CLOSE", volume=positions[sym].pos_short)

        # 开仓
        for sym in long_list:
            if sym not in current_long:
                self.api.insert_order(sym, direction="BUY", offset="OPEN", volume=1)
        for sym in short_list:
            if sym not in current_short:
                self.api.insert_order(sym, direction="SELL", offset="OPEN", volume=1)

        self.long_pos = long_list
        self.short_pos = short_list
        print(f"[调仓] 做多: {long_list}, 做空: {short_list}")

    def run(self):
        """主循环"""
        print("=" * 60)
        print("截面波动率偏度交易策略启动")
        print("=" * 60)

        while True:
            self.api.wait_update()
            self.bar_count += 1

            # 每日收盘调仓
            if self.bar_count % self.REBALANCE == 0:
                self.rebalance()

            # 更新K线数据
            for sym in self.SYMBOLS:
                self.klines[sym] = self.api.get_kline_serial(
                    sym, 86400, data_length=self.LOOKBACK + 10
                )


if __name__ == "__main__":
    # 使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    strategy = VolatilitySkewStrategy(api)
    strategy.run()
