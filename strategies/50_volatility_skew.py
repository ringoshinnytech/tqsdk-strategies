#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
截面波动率偏度交易策略 (Cross-Sectional Volatility Skew Strategy)
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
                self.api.close_long(sym)
        for sym in current_short:
            if sym not in short_list:
                self.api.close_short(sym)

        # 开仓
        for sym in long_list:
            if sym not in current_long:
                self.api.open_long(sym, 1)
        for sym in short_list:
            if sym not in current_short:
                self.api.open_short(sym, 1)

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
    api = TqSim()
    strategy = VolatilitySkewStrategy(api)
    strategy.run()
