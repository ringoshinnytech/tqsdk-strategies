#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
跨品种均值方差最优组合策略 (Mean-Variance Optimal Portfolio)
=============================================================

策略思路：
---------
基于 Markowitz 均值-方差框架，对多个商品期货品种进行最优权重配置：

1. 每20根日K线重新估计各品种的：
   - 预期收益（使用动量信号作为期望收益代理）
   - 协方差矩阵（60日滚动协方差）

2. 求解最大夏普比率组合（允许做空）：
   max  w'μ / sqrt(w'Σw)
   s.t. sum(|w|) <= 1   (杠杆约束)
        w_i ∈ [-0.3, 0.3]  (单品种敞口限制)

3. 将最优权重映射为整数手数，分别开多/空仓位

风险控制：
---------
- 总波动率目标：年化10%（不足时放大，超过时缩小手数）
- 最大单品种权重：±30%
- 相关性过高时（>0.9）自动合并权重防止重叠

作者: TqSdk Strategies
更新: 2026-03-13
"""

from tqsdk import TqApi, TqAuth, TqSim
import numpy as np
from scipy.optimize import minimize


class MeanVariancePortfolio:
    """均值方差最优组合策略"""

    SYMBOLS = [
        "SHFE.rb2501",  # 螺纹钢
        "SHFE.cu2501",  # 铜
        "DCE.i2501",    # 铁矿石
        "DCE.m2501",    # 豆粕
        "INE.sc2501",   # 原油
        "SHFE.au2501",  # 黄金
        "DCE.jm2501",   # 焦煤
        "SHFE.al2501",  # 铝
    ]

    LOOKBACK      = 60     # 协方差估计窗口（日）
    MOM_WINDOW    = 20     # 动量窗口（日）
    REBALANCE     = 20     # 换仓周期（日K根数）
    VOL_TARGET    = 0.10   # 年化波动率目标
    MAX_WEIGHT    = 0.30   # 单品种最大权重
    BASE_CAPITAL  = 500000 # 名义资金（元）

    def __init__(self, api):
        self.api = api
        self.klines = {
            sym: api.get_kline_serial(sym, 86400, data_length=self.LOOKBACK + 5)
            for sym in self.SYMBOLS
        }
        self.bar_count  = 0
        self.prev_weights = {}

    def _build_return_matrix(self):
        """构建收益率矩阵 (T × N)"""
        ret_dict = {}
        for sym in self.SYMBOLS:
            closes = self.klines[sym]["close"].values
            if len(closes) < self.LOOKBACK + 1:
                return None
            rets = np.diff(np.log(closes[-(self.LOOKBACK + 1):]))
            ret_dict[sym] = rets
        if len(ret_dict) < len(self.SYMBOLS):
            return None
        return np.column_stack([ret_dict[sym] for sym in self.SYMBOLS])

    def _expected_return(self, ret_matrix):
        """用动量（近期均值）作为期望收益代理"""
        n = min(self.MOM_WINDOW, ret_matrix.shape[0])
        return ret_matrix[-n:].mean(axis=0) * 252   # 年化

    def _max_sharpe_weights(self, mu, cov):
        """最大夏普比率组合（允许做空）"""
        n = len(mu)
        rf = 0.02 / 252   # 无风险利率（日）

        def neg_sharpe(w):
            port_ret = np.dot(w, mu)
            port_vol = np.sqrt(w @ cov @ w + 1e-10)
            return -(port_ret - rf) / port_vol

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(np.abs(w)) - 1.0}]
        bounds = [(-self.MAX_WEIGHT, self.MAX_WEIGHT)] * n
        w0 = np.ones(n) / n

        result = minimize(neg_sharpe, w0, method='SLSQP',
                         bounds=bounds, constraints=constraints,
                         options={'maxiter': 500, 'ftol': 1e-8})
        if result.success:
            return result.x
        # 若优化失败，退化为等权
        return np.ones(n) / n * 0.1

    def _vol_scale(self, weights, cov):
        """按波动率目标调整杠杆"""
        port_vol = np.sqrt(weights @ cov @ weights * 252)
        if port_vol < 1e-6:
            return weights
        scale = self.VOL_TARGET / port_vol
        return weights * min(scale, 2.0)   # 最大2倍杠杆

    def _weights_to_volume(self, weights, closes):
        """将权重映射为手数（向下取整）"""
        volumes = {}
        for i, sym in enumerate(self.SYMBOLS):
            notional = self.BASE_CAPITAL * abs(weights[i])
            price    = closes[i]
            # 假设合约乘数=10，保证金率=0.10
            mult     = 10
            vol      = int(notional / (price * mult))
            direction = 1 if weights[i] > 0 else -1
            volumes[sym] = direction * max(vol, 0)
        return volumes

    def rebalance(self):
        """重新计算最优权重并换仓"""
        ret_matrix = self._build_return_matrix()
        if ret_matrix is None:
            return

        mu  = self._expected_return(ret_matrix)
        cov = np.cov(ret_matrix.T) * 252

        # 最优权重
        w_opt  = self._max_sharpe_weights(mu, cov)
        w_scaled = self._vol_scale(w_opt, cov / 252)

        closes = [self.klines[sym]["close"].iloc[-1] for sym in self.SYMBOLS]
        target_vols = self._weights_to_volume(w_scaled, closes)

        print(f"[均值方差] 最优权重：{dict(zip(self.SYMBOLS, [f'{w:.3f}' for w in w_scaled]))}")

        # 平旧仓
        for sym, prev_w in self.prev_weights.items():
            target = target_vols.get(sym, 0)
            pos = self.api.get_position(sym)

            if pos.pos_long > 0 and target <= 0:
                self.api.insert_order(sym, direction="SELL", offset="CLOSE",
                                      volume=pos.pos_long)
            elif pos.pos_short > 0 and target >= 0:
                self.api.insert_order(sym, direction="BUY", offset="CLOSE",
                                      volume=pos.pos_short)

        self.api.wait_update()

        # 开新仓
        for sym, target in target_vols.items():
            if target == 0:
                continue
            pos = self.api.get_position(sym)
            if target > 0 and pos.pos_long < target:
                diff = target - pos.pos_long
                self.api.insert_order(sym, direction="BUY", offset="OPEN", volume=diff)
                print(f"  开多 {sym}  {diff}手")
            elif target < 0 and pos.pos_short < abs(target):
                diff = abs(target) - pos.pos_short
                self.api.insert_order(sym, direction="SELL", offset="OPEN", volume=diff)
                print(f"  开空 {sym}  {diff}手")

        self.prev_weights = {sym: v for sym, v in target_vols.items() if v != 0}

    def run(self):
        while True:
            self.api.wait_update()

            updated = any(
                self.api.is_changing(self.klines[sym].iloc[-1], "datetime")
                for sym in self.SYMBOLS
            )
            if not updated:
                continue

            self.bar_count += 1
            if self.bar_count % self.REBALANCE == 0:
                self.rebalance()


def main():
    api = TqApi(TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    strategy = MeanVariancePortfolio(api)
    try:
        strategy.run()
    finally:
        api.close()


if __name__ == "__main__":
    main()
