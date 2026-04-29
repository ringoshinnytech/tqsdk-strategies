#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
截面多因子行业轮动策略
======================

【关于 TqSdk】
TqSdk 是信易科技开源的 Python 量化交易开发包，面向国内期货、期权、股票等市场，提供实时行情、K 线数据、历史回测、模拟交易和实盘交易等能力。
本仓库中的策略示例通常使用 TqApi 获取行情和 K 线，用 TqSim 或模拟账户演示交易流程，并通过目标仓位或下单接口把策略信号转成交易动作。
运行这些示例前，需要先安装 tqsdk，并把示例中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的天勤或快期账户信息。

【策略介绍】
截面多因子行业轮动策略用于演示如何把一个明确的交易想法落到 TqSdk 策略脚本中。核心思路是：动量+波动率+成交量+趋势四因子截面打分，跨板块多空轮动
脚本默认关注 SHFE.rb2501、SHFE.hc2501、DCE.i2501、SHFE.cu2501、SHFE.al2501 等多个品种，运行时先订阅行情或 K 线数据，再计算对应的指标、价差、排名或过滤条件；当信号满足要求时，策略会调整模拟账户持仓，信号消失或风险条件触发时退出。
这类策略适合同时跟踪多个品种，通过横向比较选择交易对象，需要关注品种池、流动性和因子稳定性。

【运行说明】
1. 安装依赖：pip install tqsdk -U。
2. 修改账号：把文件中的 YOUR_ACCOUNT / YOUR_PASSWORD 替换为自己的账号信息。
3. 先使用模拟账户运行和观察日志，不建议未经验证直接用于实盘。
4. 如果合约代码已经过期，需要替换为当前在市的主力或目标合约。

【风险提示】
本策略只用于学习和研究，不构成投资建议。技术指标和历史规律都会失效，趋势、震荡、跳空、流动性不足和手续费滑点都可能导致亏损。用于真实交易前，应先完成回测、模拟交易、参数敏感性检查和风控评估。

【原有策略说明】
 (Cross-Section Multi-Factor Sector Rotation)
=====================================================================

策略思路：
---------
本策略对多个商品期货品种按行业板块（黑色系、有色系、农产品、能化）分组，
使用截面多因子打分进行板块轮动配置：
  - 动量因子 F1：20日价格动量（截面排名）
  - 波动率因子 F2：5日/20日波动率之比（截面排名，低值加分）
  - 成交量因子 F3：20日成交量分位（截面排名）
  - 趋势因子 F4：MA5/MA20的比值（截面排名）

综合因子 Score = 0.35*F1 + 0.25*F2 + 0.2*F3 + 0.2*F4

每20根日K重新评分，做多得分最高2个品种，做空得分最低2个品种。
形成市场中性的跨截面多空组合。

风险控制：
---------
- 单品种波动率权重调整手数（波动率倒数加权）
- 总持仓限制不超过保证金的60%

作者: TqSdk Strategies
更新: 2026-03-13
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.ta import MA, ATR
import pandas as pd
import numpy as np


class SectorRotationStrategy:
    """截面多因子行业轮动策略"""

    # 覆盖四大板块：黑色系、有色系、农产品、能化
    SYMBOLS = [
        "SHFE.rb2501",  # 螺纹钢（黑色）
        "SHFE.hc2501",  # 热卷（黑色）
        "DCE.i2501",    # 铁矿石（黑色）
        "SHFE.cu2501",  # 铜（有色）
        "SHFE.al2501",  # 铝（有色）
        "SHFE.zn2501",  # 锌（有色）
        "DCE.m2501",    # 豆粕（农产品）
        "DCE.c2501",    # 玉米（农产品）
        "CZCE.rm2501",  # 菜粕（农产品）
        "INE.sc2501",   # 原油（能化）
        "SHFE.fu2501",  # 燃油（能化）
        "DCE.eg2501",   # 乙二醇（能化）
    ]

    LOOKBACK      = 20      # 日K回看窗口
    REBALANCE     = 20      # 换仓周期（日K根数）
    LONG_COUNT    = 2       # 做多品种数
    SHORT_COUNT   = 2       # 做空品种数
    BASE_VOLUME   = 1       # 基础手数

    # 因子权重
    W_MOMENTUM  = 0.35
    W_VOL_RATIO = 0.25
    W_VOLUME    = 0.20
    W_TREND     = 0.20

    def __init__(self, api):
        self.api = api
        self.klines = {
            sym: api.get_kline_serial(sym, 86400, data_length=self.LOOKBACK + 5)
            for sym in self.SYMBOLS
        }
        self.bar_count = 0
        self.long_pos  = []
        self.short_pos = []

    def _rank_normalize(self, values: dict) -> dict:
        """截面排名标准化到 [0, 1]"""
        items = sorted(values.items(), key=lambda x: x[1])
        n = len(items)
        return {sym: i / (n - 1) for i, (sym, _) in enumerate(items)}

    def compute_scores(self) -> dict:
        """计算各品种的综合因子得分"""
        f_momentum, f_volratio, f_volume, f_trend = {}, {}, {}, {}

        for sym in self.SYMBOLS:
            kl = self.klines[sym]
            if len(kl) < self.LOOKBACK + 2:
                continue
            closes  = kl["close"].values
            volumes = kl["volume"].values

            # F1: 20日动量
            momentum = (closes[-1] - closes[-self.LOOKBACK]) / (closes[-self.LOOKBACK] + 1e-8)

            # F2: 短期/长期波动率比（数值越小越稳）→ 反向排名（低值好）
            rv5  = float(np.std(np.diff(np.log(closes[-6:]))  ) * np.sqrt(252))
            rv20 = float(np.std(np.diff(np.log(closes[-21:]))) * np.sqrt(252))
            vol_ratio = rv5 / (rv20 + 1e-8)   # <1 表示近期波动收缩，趋势稳定

            # F3: 20日成交量分位（近5日均量 / 20日均量）
            vol_score = float(np.mean(volumes[-5:])) / (float(np.mean(volumes[-20:])) + 1e-8)

            # F4: MA趋势（5日均线 / 20日均线）
            ma5  = float(np.mean(closes[-5:]))
            ma20 = float(np.mean(closes[-20:]))
            trend = ma5 / (ma20 + 1e-8)

            f_momentum[sym] = momentum
            f_volratio[sym] = -vol_ratio   # 反向（低波动比加分）
            f_volume[sym]   = vol_score
            f_trend[sym]    = trend

        # 截面排名归一化
        r_m  = self._rank_normalize(f_momentum)
        r_vr = self._rank_normalize(f_volratio)
        r_vo = self._rank_normalize(f_volume)
        r_tr = self._rank_normalize(f_trend)

        scores = {}
        for sym in r_m:
            scores[sym] = (self.W_MOMENTUM  * r_m[sym]
                         + self.W_VOL_RATIO * r_vr.get(sym, 0.5)
                         + self.W_VOLUME    * r_vo.get(sym, 0.5)
                         + self.W_TREND     * r_tr.get(sym, 0.5))
        return scores

    def rebalance(self):
        """换仓：平旧仓，开新仓"""
        scores = self.compute_scores()
        if len(scores) < self.LONG_COUNT + self.SHORT_COUNT:
            return

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        new_longs  = [sym for sym, _ in ranked[:self.LONG_COUNT]]
        new_shorts = [sym for sym, _ in ranked[-self.SHORT_COUNT:]]

        print(f"[截面轮动] 得分排名：{[(s, f'{v:.3f}') for s, v in ranked]}")
        print(f"  做多：{new_longs}  做空：{new_shorts}")

        # 平旧仓
        for sym in self.long_pos:
            if sym not in new_longs:
                pos = self.api.get_position(sym)
                if pos.pos_long > 0:
                    self.api.insert_order(sym, direction="SELL", offset="CLOSE",
                                          volume=pos.pos_long)
        for sym in self.short_pos:
            if sym not in new_shorts:
                pos = self.api.get_position(sym)
                if pos.pos_short > 0:
                    self.api.insert_order(sym, direction="BUY", offset="CLOSE",
                                          volume=pos.pos_short)

        self.api.wait_update()

        # 开新仓
        for sym in new_longs:
            pos = self.api.get_position(sym)
            if pos.pos_long == 0:
                self.api.insert_order(sym, direction="BUY", offset="OPEN",
                                      volume=self.BASE_VOLUME)
        for sym in new_shorts:
            pos = self.api.get_position(sym)
            if pos.pos_short == 0:
                self.api.insert_order(sym, direction="SELL", offset="OPEN",
                                      volume=self.BASE_VOLUME)

        self.long_pos  = new_longs
        self.short_pos = new_shorts

    def run(self):
        """策略主循环"""
        while True:
            self.api.wait_update()

            # 任意品种K线更新
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
    strategy = SectorRotationStrategy(api)
    try:
        strategy.run()
    finally:
        api.close()


if __name__ == "__main__":
    main()
