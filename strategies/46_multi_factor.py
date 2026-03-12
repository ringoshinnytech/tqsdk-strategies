#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多因子量化选股策略 (Multi-Factor Quantitative Strategy)
=========================================================

策略思路：
---------
本策略综合多个技术因子进行加权评分，选出强势品种进行交易。
因子包括：动量因子、趋势因子、波动率因子、成交量因子

实现逻辑：
---------
1. 动量因子：计算N日内收益率作为动量指标
2. 趋势因子：计算MA均线多头排列程度
3. 波动率因子：计算ATR与收盘价的比率
4. 成交量因子：计算成交量变化率

通过加权综合评分，选取得分最高的品种进行做多。

作者: TqSdk Strategies
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.ta import MA, ATR, ROC
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class MultiFactorStrategy:
    """多因子量化选股策略"""
    
    def __init__(self, api, symbols, params=None):
        """
        初始化策略
        
        Args:
            api: TqApi实例
            symbols: 交易品种列表
            params: 策略参数
        """
        self.api = api
        self.symbols = symbols
        self.params = params or {}
        
        # 默认参数
        self.n_ma_short = self.params.get('n_ma_short', 5)    # 短期均线周期
        self.n_ma_mid = self.params.get('n_ma_mid', 20)      # 中期均线周期
        self.n_ma_long = self.params.get('n_ma_long', 60)     # 长期均线周期
        self.n_momentum = self.params.get('n_momentum', 20)   # 动量周期
        self.n_atr = self.params.get('n_atr', 14)             # ATR周期
        self.n_vol = self.params.get('n_vol', 20)             # 成交量周期
        self.n_top = self.params.get('n_top', 3)              # 选取前N个品种
        
        # 因子权重
        self.w_momentum = self.params.get('w_momentum', 0.3)  # 动量权重
        self.w_trend = self.params.get('w_trend', 0.3)        # 趋势权重
        self.w_volatility = self.params.get('w_volatility', 0.2)  # 波动率权重
        self.w_volume = self.params.get('w_volume', 0.2)      # 成交量权重
        
        # 仓位管理
        self.positions = {}       # 当前持仓
        self.max_position = 1.0    # 单品种最大仓位比例
        
    def get_factors(self, symbol, n=60):
        """
        计算单个品种的各个因子得分
        
        Args:
            symbol: 品种代码
            n: 数据获取周期
            
        Returns:
            dict: 因子得分
        """
        try:
            # 获取K线数据
            klines = self.api.get_kline_serial(symbol, n)
            if klines is None or len(klines) < max(self.n_ma_long, self.n_momentum, self.n_vol):
                return None
                
            df = pd.DataFrame(klines)
            
            # 1. 动量因子：过去N日收益率
            momentum = (df['close'].iloc[-1] / df['close'].iloc[-self.n_momentum] - 1)
            
            # 2. 趋势因子：均线多头排列程度
            ma5 = df['close'].rolling(self.n_ma_short).mean()
            ma20 = df['close'].rolling(self.n_ma_mid).mean()
            ma60 = df['close'].rolling(self.n_ma_long).mean()
            
            # 多头排列：短期 > 中期 > 长期
            trend_score = 0
            if ma5.iloc[-1] > ma20.iloc[-1]:
                trend_score += 1
            if ma20.iloc[-1] > ma60.iloc[-1]:
                trend_score += 1
            trend_score = trend_score / 2.0  # 归一化到0-1
            
            # 3. 波动率因子：ATR/收盘价（越低越好）
            atr = ATR(df, self.n_atr)
            volatility_ratio = atr.iloc[-1] / df['close'].iloc[-1]
            # 波动率得分：越低得分越高
            volatility_score = 1 / (1 + volatility_ratio * 100)
            
            # 4. 成交量因子：成交量变化率
            vol_ma = df['volume'].rolling(self.n_vol).mean()
            volume_ratio = df['volume'].iloc[-1] / vol_ma.iloc[-1]
            volume_score = min(volume_ratio / 2, 1)  # 归一化
            
            return {
                'momentum': momentum,
                'trend': trend_score,
                'volatility': volatility_score,
                'volume': volume_score
            }
            
        except Exception as e:
            print(f"计算因子失败 {symbol}: {e}")
            return None
    
    def calculate_composite_score(self, factors):
        """
        计算综合得分
        
        Args:
            factors: 因子字典
            
        Returns:
            float: 综合得分
        """
        if factors is None:
            return -999
            
        # 标准化动量因子到0-1区间
        momentum_norm = np.clip(factors['momentum'] * 10 + 0.5, 0, 1)
        
        # 加权计算综合得分
        score = (
            momentum_norm * self.w_momentum +
            factors['trend'] * self.w_trend +
            factors['volatility'] * self.w_volatility +
            factors['volume'] * self.w_volume
        )
        
        return score
    
    def rank_symbols(self):
        """
        对所有品种进行排名
        
        Returns:
            list: 排序后的品种列表 [(symbol, score), ...]
        """
        scores = []
        
        for symbol in self.symbols:
            factors = self.get_factors(symbol)
            score = self.calculate_composite_score(factors)
            scores.append((symbol, score))
            
        # 按得分降序排列
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores
    
    def update_positions(self):
        """更新持仓状态"""
        for symbol in self.symbols:
            position = self.api.get_position(symbol)
            if position:
                self.positions[symbol] = {
                    'long': position.get('long_position', 0),
                    'short': position.get('short_position', 0)
                }
    
    def rebalance(self, top_symbols):
        """
        调仓：只持有得分最高的N个品种
        
        Args:
            top_symbols: 排名前N的品种列表
        """
        # 目标持仓
        target_symbols = set([s[0] for s in top_symbols[:self.n_top]])
        current_symbols = set(self.positions.keys())
        
        # 卖出不在目标列表中的品种
        for symbol in current_symbols - target_symbols:
            if self.positions.get(symbol, {}).get('long', 0) > 0:
                print(f"卖出平仓: {symbol}")
                self.api.insert_order(symbol=symbol, direction="SELL", offset="CLOSE", volume=1)
        
        # 买入目标品种
        current_long = set([s for s, p in self.positions.items() if p.get('long', 0) > 0])
        for symbol, score in top_symbols[:self.n_top]:
            if symbol not in current_long:
                print(f"买入开仓: {symbol}, 得分: {score:.3f}")
                self.api.insert_order(symbol=symbol, direction="BUY", offset="OPEN", volume=1)
    
    def run(self):
        """主循环"""
        print("=" * 50)
        print("多因子量化选股策略启动")
        print(f"交易品种: {self.symbols}")
        print(f"持仓品种数: {self.n_top}")
        print("=" * 50)
        
        while True:
            try:
                # 等待下一个交易日
                self.api.wait_update()
                
                # 每日开盘后进行选股
                if self.api.is_changing(self.api.get_trading_time(), "date"):
                    print(f"\n[{datetime.now()}] 执行因子选股...")
                    
                    # 更新持仓
                    self.update_positions()
                    
                    # 因子评分排名
                    ranked = self.rank_symbols()
                    
                    print("品种得分排名:")
                    for i, (symbol, score) in enumerate(ranked[:5]):
                        print(f"  {i+1}. {symbol}: {score:.3f}")
                    
                    # 调仓
                    self.rebalance(ranked)
                    
            except KeyboardInterrupt:
                print("\n策略停止")
                break
            except Exception as e:
                print(f"运行错误: {e}")


def main():
    """主函数"""
    # 使用模拟账户
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
    # 交易品种列表（期货）
    symbols = [
        "SHFE.rb2405",    # 螺纹钢
        "SHFE.hc2405",    # 热卷
        "DCE.i2405",      # 铁矿石
        "DCE.j2405",      # 焦炭
        "DCE.jm2405",     # 焦煤
        "CZCE.mo2405",    # 菜籽油
        "CZCE.rm2405",    # 菜粕
        "CZCE.cs2405",    # 玉米淀粉
        "DCE.m2405",      # 豆粕
        "DCE.a2405",      # 豆一
    ]
    
    # 策略参数
    params = {
        'n_ma_short': 5,
        'n_ma_mid': 20,
        'n_ma_long': 60,
        'n_momentum': 20,
        'n_atr': 14,
        'n_vol': 20,
        'n_top': 3,
        'w_momentum': 0.3,
        'w_trend': 0.3,
        'w_volatility': 0.2,
        'w_volume': 0.2
    }
    
    # 启动策略
    strategy = MultiFactorStrategy(api, symbols, params)
    strategy.run()


if __name__ == "__main__":
    main()
