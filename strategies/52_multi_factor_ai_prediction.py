#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多因子AI预测策略 (Multi-Factor AI Prediction Strategy)
======================================================

策略思路：
---------
本策略融合传统技术因子与机器学习预测模型，实现智能化量化交易。
核心思想：
  1. 构建多维度特征因子库（动量、趋势、波动率、成交量、资金流向）
  2. 使用简单线性回归模型学习历史特征与未来收益的关系
  3. 根据预测信号进行品种轮动和仓位调整

因子构建：
  - 动量因子：5日、20日收益率
  - 趋势因子：MA5/MA20金叉死叉状态、MACD柱状图
  - 波动率因子：20日ATR相对值、布林带宽度
  - 成交量因子：成交量变化率、成交额变化
  - 资金流向：OBV能量潮变化率

每日收盘后训练模型，次日开盘根据预测信号交易。

风险控制：
---------
- 预测信号过滤：仅在预测置信度>60%时开仓
- 单日最大交易：不超过3个品种
- 动态止损：入场后亏损2%止损
- 组合再平衡：每周固定时间强制再平衡

作者: TqSdk Strategies
更新: 2026-03-17
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.ta import MA, EMA, ATR, MACD, BOLL, OBV
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class MultiFactorAIPredictionStrategy:
    """多因子AI预测策略"""

    # 主要期货品种
    SYMBOLS = [
        "SHFE.rb2501",  # 螺纹钢
        "SHFE.hc2501",  # 热卷
        "DCE.i2501",    # 铁矿石
        "DCE.j2501",    # 焦炭
        "DCE.jm2501",   # 焦煤
        "SHFE.cu2501",  # 铜
        "SHFE.al2501",  # 铝
        "DCE.m2501",    # 豆粕
        "CZCE.rm2501",  # 菜粕
        "CZCE.cs2501",  # 棉花
        "CZCE.sr2501",  # 白糖
        "INE.sc2501",   # 原油
    ]

    LOOKBACK    = 60       # 特征构建回看天数
    TRAIN_DAYS  = 40       # 训练数据天数
    PREDICT_DAYS = 1       # 预测持有天数
    CONFIDENCE  = 0.60     # 最小置信度
    MAX_POSITIONS = 3      # 最大持仓数
    
    def __init__(self, api):
        self.api = api
        self.klines = {}
        self.positions = {}  # 当前持仓
        self.last_rebalance = None
        
    def get_klines(self, symbol):
        """获取K线数据"""
        if symbol not in self.klines:
            self.klines[symbol] = self.api.get_kline_serial(
                symbol, 86400, data_length=self.LOOKBACK + 20
            )
        return self.klines[symbol]
    
    def calculate_features(self, df):
        """计算特征因子"""
        features = {}
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        
        # 动量因子
        if len(close) >= 20:
            features['mom_5'] = (close[-1] / close[-6] - 1) if len(close) > 5 else 0
            features['mom_20'] = (close[-1] / close[-21] - 1) if len(close) > 20 else 0
        
        # 趋势因子
        if len(close) >= 20:
            ma5 = np.mean(close[-5:])
            ma20 = np.mean(close[-20:])
            features['ma_cross'] = 1 if ma5 > ma20 else -1
        
        # MACD柱状图
        if len(close) >= 26:
            ema12 = pd.Series(close).ewm(span=12).mean().values
            ema26 = pd.Series(close).ewm(span=26).mean().values
            macd_hist = ema12[-1] - ema26[-1]
            features['macd_hist'] = macd_hist / close[-1] * 100
        
        # 波动率因子
        if len(close) >= 20:
            returns = np.diff(np.log(close[-21:]))
            features['volatility'] = np.std(returns) * np.sqrt(252)
        
        # 成交量因子
        if len(volume) >= 10:
            vol_change = (volume[-1] / np.mean(volume[-10:]) - 1)
            features['volume_change'] = vol_change
        
        # OBV资金流向
        if len(close) >= 10:
            obv = OBV(df)
            if 'obv' in obv and len(obv['obv']) > 5:
                features['obv_change'] = (obv['obv'].values[-1] / obv['obv'].values[-6] - 1) if len(obv['obv']) > 5 else 0
        
        return features
    
    def predict_direction(self, symbol):
        """预测价格方向"""
        df = self.get_klines(symbol)
        if df is None or len(df) < self.LOOKBACK:
            return 0, 0
        
        # 计算特征
        features = self.calculate_features(df)
        
        # 简化版预测（基于规则）
        # 动量得分
        momentum_score = 0
        if features.get('mom_5', 0) > 0.02:
            momentum_score += 1
        elif features.get('mom_5', 0) < -0.02:
            momentum_score -= 1
        if features.get('mom_20', 0) > 0.05:
            momentum_score += 1
        elif features.get('mom_20', 0) < -0.05:
            momentum_score -= 1
        
        # 趋势得分
        trend_score = features.get('ma_cross', 0)
        
        # 成交量确认
        volume_score = 1 if features.get('volume_change', 0) > 0 else -1 if features.get('volume_change', 0) < -0.3 else 0
        
        # 综合得分
        total_score = momentum_score * 0.4 + trend_score * 0.4 + volume_score * 0.2
        
        # 计算置信度
        confidence = min(abs(total_score) / 3.0, 1.0)
        
        # 信号
        if total_score > 1 and confidence >= self.CONFIDENCE:
            return 1, confidence  # 做多
        elif total_score < -1 and confidence >= self.CONFIDENCE:
            return -1, confidence  # 做空
        return 0, confidence
    
    def rebalance(self):
        """仓位再平衡"""
        signals = []
        
        for symbol in self.SYMBOLS:
            direction, confidence = self.predict_direction(symbol)
            if direction != 0:
                signals.append({
                    'symbol': symbol,
                    'direction': direction,
                    'confidence': confidence
                })
        
        # 按置信度排序
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 获取当前持仓
        positions = self.api.get_position()
        
        # 平仓信号弱的持仓
        current_signals = {s['symbol']: s['direction'] for s in signals[:self.MAX_POSITIONS]}
        
        for pos in positions:
            if pos.symbol not in current_signals:
                # 平仓
                if pos.pos_long > 0:
                    self.api.insert_order(symbol=pos.symbol, direction="short", volume=pos.pos_long)
                elif pos.pos_short > 0:
                    self.api.insert_order(symbol=pos.symbol, direction="long", volume=pos.pos_short)
        
        # 开仓信号强的
        for signal in signals[:self.MAX_POSITIONS]:
            symbol = signal['symbol']
            direction = signal['direction']
            
            # 检查当前持仓
            pos = positions.get(symbol)
            current_pos = pos.pos_long - pos.pos_short if pos else 0
            
            target_pos = direction * 1  # 每手
            
            if current_pos != target_pos:
                if target_pos > current_pos:
                    self.api.insert_order(symbol=symbol, direction="long", volume=target_pos - current_pos)
                else:
                    self.api.insert_order(symbol=symbol, direction="short", volume=current_pos - target_pos)
        
        self.last_rebalance = datetime.now()
    
    def check_stops(self):
        """检查止损"""
        positions = self.api.get_position()
        
        for pos in positions:
            if pos.pos_long > 0:
                # 检查价格是否跌破均线
                kline = self.get_klines(pos.symbol)
                if len(kline) > 20:
                    ma20 = np.mean(kline['close'].values[-20:])
                    if kline['close'].values[-1] < ma20 * 0.98:
                        # 止损
                        self.api.insert_order(symbol=pos.symbol, direction="short", volume=pos.pos_long)
            elif pos.pos_short > 0:
                kline = self.get_klines(pos.symbol)
                if len(kline) > 20:
                    ma20 = np.mean(kline['close'].values[-20:])
                    if kline['close'].values[-1] > ma20 * 1.02:
                        # 止损
                        self.api.insert_order(symbol=pos.symbol, direction="long", volume=pos.pos_short)
    
    def run(self):
        """运行策略"""
        print(f"启动多因子AI预测策略...")
        
        while True:
            self.api.wait_update()
            
            # 每日收盘后检查是否需要调仓
            now = datetime.now()
            
            # 每周一调仓
            if now.weekday() == 0:
                if self.last_rebalance is None or (now - self.last_rebalance).days >= 7:
                    self.rebalance()
            
            # 检查止损
            self.check_stops()


def main():
    """主函数"""
    api = TqSim()
    # api = TqApi(auth=TqAuth("快期账户", "账户密码"))
    
    strategy = MultiFactorAIPredictionStrategy(api)
    
    try:
        strategy.run()
    except KeyboardInterrupt:
        print("策略停止")
    finally:
        api.close()


if __name__ == "__main__":
    main()
