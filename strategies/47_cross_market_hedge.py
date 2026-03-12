#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
跨市场对冲策略 (Cross-Market Hedging Strategy)
================================================

策略思路：
---------
本策略利用不同市场之间的相关性进行对冲交易。
当两个高度相关的市场出现显著背离时，做多被低估的市场，做空被高估的市场。
当价差回归时平仓获利。

实现逻辑：
---------
1. 选择高度相关的市场对（如螺纹钢与热卷、黄金与白银）
2. 计算标准化价差（Z-Score）
3. 当Z-Score超过阈值时进行对冲交易
4. 当Z-Score回归均值时平仓

作者: TqSdk Strategies
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.ta import ZSCORE, SMA
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class CrossMarketHedgeStrategy:
    """跨市场对冲策略"""
    
    def __init__(self, api, pairs, params=None):
        """
        初始化策略
        
        Args:
            api: TqApi实例
            pairs: 交易对列表 [(symbol_a, symbol_b, ratio), ...]
                   ratio: 合约乘数调整比例
            params: 策略参数
        """
        self.api = api
        self.pairs = pairs
        self.params = params or {}
        
        # 默认参数
        self.z_threshold = self.params.get('z_threshold', 2.0)    # Z-Score阈值
        self.z_exit = self.params.get('z_exit', 0.3)               # 平仓阈值
        self.n_lookback = self.params.get('n_lookback', 60)       # 回看周期
        self.n_sma = self.params.get('n_sma', 20)                  # 均线平滑周期
        self.atr_multiplier = self.params.get('atr_multiplier', 2) # ATR止损倍数
        
        # 持仓
        self.positions = {}  # {(symbol_a, symbol_b): {'a_long': x, 'b_long': y, 'entry_z': z}}
        
    def get_spread_data(self, symbol_a, symbol_b, ratio, n=100):
        """
        获取两个品种的价差数据
        
        Args:
            symbol_a: 品种A代码
            symbol_b: 品种B代码
            ratio: 配比比例
            n: 数据获取周期
            
        Returns:
            pd.DataFrame: 包含价格和价差的数据
        """
        try:
            # 获取K线数据
            kline_a = self.api.get_kline_serial(symbol_a, n)
            kline_b = self.api.get_kline_serial(symbol_b, n)
            
            if kline_a is None or kline_b is None:
                return None
                
            df_a = pd.DataFrame(kline_a)
            df_b = pd.DataFrame(kline_b)
            
            # 确保长度一致
            min_len = min(len(df_a), len(df_b))
            df_a = df_a.iloc[-min_len:]
            df_b = df_b.iloc[-min_len:]
            
            # 计算价差（标准化）
            # 使用价格比率来消除合约大小差异
            spread = df_a['close'] - ratio * df_b['close']
            
            # 计算Z-Score
            mean = SMA(spread, self.n_sma)
            std = spread.rolling(self.n_lookback).std()
            zscore = (spread - mean) / std
            
            result = pd.DataFrame({
                'close_a': df_a['close'].values,
                'close_b': df_b['close'].values,
                'spread': spread.values,
                'zscore': zscore.values,
                'atr_a': (df_a['high'] - df_a['low']).rolling(14).mean().values,
                'atr_b': (df_b['high'] - df_b['low']).rolling(14).mean().values
            })
            
            return result
            
        except Exception as e:
            print(f"获取价差数据失败: {symbol_a} vs {symbol_b}: {e}")
            return None
    
    def check_pair_status(self, symbol_a, symbol_b, ratio):
        """
        检查交易对状态
        
        Args:
            symbol_a: 品种A
            symbol_b: 品种B
            ratio: 配比
            
        Returns:
            dict: 状态信息
        """
        key = (symbol_a, symbol_b)
        
        if key in self.positions:
            # 已有持仓
            return {
                'has_position': True,
                'entry_z': self.positions[key]['entry_z'],
                'direction': self.positions[key].get('direction')
            }
        else:
            return {'has_position': False}
    
    def open_hedge(self, symbol_a, symbol_b, ratio, direction, zscore):
        """
        开仓对冲
        
        Args:
            symbol_a: 品种A
            symbol_b: 品种B  
            ratio: 配比
            direction: 方向 ('A_up_B_down' 或 'A_down_B_up')
            zscore: 当前Z-Score
        """
        key = (symbol_a, symbol_b)
        
        if direction == 'A_up_B_down':
            # A被高估，B被低估：做空A，做多B
            print(f"[开仓] 做空{symbol_a}, 做多{symbol_b}, Z-Score: {zscore:.2f}")
            self.api.insert_order(symbol=symbol_a, direction="SELL", offset="OPEN", volume=1)
            self.api.insert_order(symbol=symbol_b, direction="BUY", offset="OPEN", volume=ratio)
            
            self.positions[key] = {
                'a_long': 0,
                'b_long': ratio,
                'a_short': 1,
                'b_short': 0,
                'entry_z': zscore,
                'direction': 'A_up_B_down'
            }
            
        else:  # A_down_B_up
            # A被低估，B被高估：做多A，做空B
            print(f"[开仓] 做多{symbol_a}, 做空{symbol_b}, Z-Score: {zscore:.2f}")
            self.api.insert_order(symbol=symbol_a, direction="BUY", offset="OPEN", volume=1)
            self.api.insert_order(symbol=symbol_b, direction="SELL", offset="OPEN", volume=ratio)
            
            self.positions[key] = {
                'a_long': 1,
                'b_long': 0,
                'a_short': 0,
                'b_short': ratio,
                'entry_z': zscore,
                'direction': 'A_down_B_up'
            }
    
    def close_hedge(self, symbol_a, symbol_b):
        """
        平仓对冲
        
        Args:
            symbol_a: 品种A
            symbol_b: 品种B
        """
        key = (symbol_a, symbol_b)
        
        if key not in self.positions:
            return
            
        pos = self.positions[key]
        
        print(f"[平仓] {symbol_a} vs {symbol_b}, 进场Z: {pos['entry_z']:.2f}")
        
        # 平掉所有仓位
        if pos['a_long'] > 0:
            self.api.insert_order(symbol=symbol_a, direction="SELL", offset="CLOSE", volume=1)
        if pos['a_short'] > 0:
            self.api.insert_order(symbol=symbol_a, direction="BUY", offset="CLOSE", volume=1)
        if pos['b_long'] > 0:
            self.api.insert_order(symbol=symbol_b, direction="SELL", offset="CLOSE", volume=pos['b_long'])
        if pos['b_short'] > 0:
            self.api.insert_order(symbol=symbol_b, direction="BUY", offset="CLOSE", volume=pos['b_short'])
        
        del self.positions[key]
    
    def update_positions(self):
        """更新持仓状态"""
        all_positions = self.api.get_position()
        for symbol in all_positions:
            pos = all_positions[symbol]
            self.positions[symbol] = pos
    
    def check_and_trade(self):
        """检查所有交易对并执行交易"""
        for symbol_a, symbol_b, ratio in self.pairs:
            # 获取价差数据
            data = self.get_spread_data(symbol_a, symbol_b, ratio)
            if data is None or len(data) < self.n_lookback:
                continue
                
            latest = data.iloc[-1]
            zscore = latest['zscore']
            
            # 跳过无效Z值
            if pd.isna(zscore) or abs(zscore) > 10:
                continue
            
            status = self.check_pair_status(symbol_a, symbol_b, ratio)
            
            print(f"[{symbol_a} vs {symbol_b}] Z-Score: {zscore:.2f}")
            
            if status['has_position']:
                # 已有持仓，检查是否需要平仓
                entry_z = status['entry_z']
                
                # Z-Score回归到阈值以内时平仓
                if abs(zscore) < self.z_exit:
                    print(f"  -> 价差回归，平仓")
                    self.close_hedge(symbol_a, symbol_b)
                    
                # 止损：如果Z-Score向不利方向移动超过2个标准差
                elif (status['direction'] == 'A_up_B_down' and zscore > entry_z + 1.5) or \
                     (status['direction'] == 'A_down_B_up' and zscore < entry_z - 1.5):
                    print(f"  -> 止损平仓")
                    self.close_hedge(symbol_a, symbol_b)
            else:
                # 无持仓，检查是否需要开仓
                if zscore > self.z_threshold:
                    # A被高估，B被低估
                    self.open_hedge(symbol_a, symbol_b, ratio, 'A_up_B_down', zscore)
                elif zscore < -self.z_threshold:
                    # A被低估，B被高估
                    self.open_hedge(symbol_a, symbol_b, ratio, 'A_down_B_up', zscore)
    
    def run(self):
        """主循环"""
        print("=" * 60)
        print("跨市场对冲策略启动")
        print(f"交易对: {self.pairs}")
        print(f"Z-Score阈值: ±{self.z_threshold}")
        print("=" * 60)
        
        while True:
            try:
                # 等待行情更新
                self.api.wait_update()
                
                # 每日开盘后检查交易信号
                trading_time = self.api.get_trading_time()
                if self.api.is_changing(trading_time, "date"):
                    print(f"\n[{datetime.now()}] 检查交易信号...")
                    self.check_and_trade()
                    
            except KeyboardInterrupt:
                print("\n策略停止")
                break
            except Exception as e:
                print(f"运行错误: {e}")


def main():
    """主函数"""
    # 使用模拟账户
    api = TqApi(auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    
    # 定义交易对 (品种A, 品种B, 配比)
    # 配比需要根据合约乘数调整
    pairs = [
        ("SHFE.rb2405", "SHFE.hc2405", 1.0),      # 螺纹钢 vs 热卷
        ("SHFE.au2406", "SHFE.ag2406", 0.1),     # 黄金 vs 白银 (金/银比约10:1)
        ("DCE.j2405", "DCE.jm2405", 1.0),        # 焦炭 vs 焦煤
        ("DCE.m2405", "DCE.a2405", 1.0),         # 豆粕 vs 豆一
    ]
    
    # 策略参数
    params = {
        'z_threshold': 2.0,      # Z-Score超过2个标准差时开仓
        'z_exit': 0.3,           # Z-Score回归到0.3以内时平仓
        'n_lookback': 60,       # 计算Z-Score的回看周期
        'n_sma': 20,            # 均线平滑周期
        'atr_multiplier': 2     # ATR止损倍数
    启动策略
    strategy = Cross }
    
    #MarketHedgeStrategy(api, pairs, params)
    strategy.run()


if __name__ == "__main__":
    main()
