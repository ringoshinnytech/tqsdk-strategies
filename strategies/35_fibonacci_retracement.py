"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【关于 TqSdk —— 天勤量化开发包】

TqSdk 是由信易科技发起并开源的 Python 量化交易框架，专为国内期货市场设计，
是国内最主流的期货量化开发工具之一。

核心优势：
  ● 极简代码：几十行即可构建完整策略，内置 MA/MACD/BOLL/RSI/ATR 等近百个技术指标
  ● 全品种实时行情：期货、期权、股票，毫秒级推送，数据全在内存，零延迟
  ● 全流程支持：历史回测 → 模拟交易 → 实盘交易 → 运行监控，一套 API 全覆盖
  ● 广泛兼容：支持 90%+ 期货公司 CTP 直连及主流资管柜台
  ● Pandas 友好：K 线 / Tick 数据直接返回 DataFrame，与 NumPy 无缝配合

官方资源：
  📘 官方文档：https://doc.shinnytech.com/tqsdk/latest/
  🐙 GitHub  ：https://github.com/shinnytech/tqsdk-python
  🧑‍💻 账户注册：https://account.shinnytech.com/
  💬 用户社区：https://www.shinnytech.com/qa/

安装：pip install tqsdk -U
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

策略名称：波浪尺斐波那契回撤策略
策略编号：35
作者：TqSdk 策略库
更新日期：2026-03-04

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

波浪尺（Fibonacci Retracement）是基于斐波那契数列的技术分析工具，
由 Leonardo Fibonacci 在 13 世纪发现。该数列在自然界普遍存在，
金融市场中也显示出神奇的价格比例关系。

关键的斐波那契回撤位：
  1. 23.6% - 浅幅回撤，通常出现在强势趋势中
  2. 38.2% - 中等回撤，常见于标准趋势中
  3. 50.0% - 心理关口，虽非斐波那契数但具有重要支撑
  4. 61.8% - 黄金分割位，最重要的回撤支撑/阻力
  5. 78.6% - 深幅回撤，可能意味着趋势反转

本策略采用斐波那契回撤交易：
  1. 识别高低点，计算回撤位
  2. 价格触及关键回撤位时等待反转信号
  3. 结合 RSI 超买超卖确认信号

【策略特点】

  1. 科学依据：基于自然数学规律
  2. 关键价位：聚焦重要支撑阻力位
  3. 顺势交易：在回撤结束后继续原有趋势
  4. 多周期确认：结合不同周期提高准确性

【参数说明】

  symbol: 交易合约 (如 "SHFE.rb2105")
  fib_levels: 斐波那契回撤位 (默认 [0.236, 0.382, 0.5, 0.618, 0.786])
  rsi_period: RSI 周期 (默认 14)
  rsi_oversold: RSI 超卖阈值 (默认 35)
  rsi_overbought: RSI 超买阈值 (默认 65)
  atr_multi: ATR 止损倍数 (默认 2.5)

【注意事项】

  1. 斐波那契回撤在趋势行情中效果最佳
  2. 建议在 4 小时或日线上识别高低点
  3. 需结合市场环境判断趋势是否延续
"""

from tqsdk import TqApi, TqAuth, TqAccount
from tqsdk.ta import RSI, ATR
import pandas as pd
import numpy as np


class FibonacciStrategy:
    """波浪尺斐波那契回撤策略"""
    
    def __init__(self, api, symbol, fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
                 rsi_period=14, rsi_oversold=35, rsi_overbought=65, atr_multi=2.5):
        self.api = api
        self.symbol = symbol
        self.fib_levels = fib_levels
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.atr_multi = atr_multi
        
        self.position = 0
        self.entry_price = 0
        self.highest = 0
        self.lowest = 0
        self.fib_levels_dict = {}
        
    def calculate_fib_retracement(self, klines):
        """计算斐波那契回撤位"""
        if len(klines) < 20:
            return {}
            
        self.highest = klines['high'].iloc[-20:].max()
        self.lowest = klines['low'].iloc[-20:].min()
        range_val = self.highest - self.lowest
        
        levels = {}
        for level in self.fib_levels:
            levels[level] = self.highest - range_val * level
            
        self.fib_levels_dict = levels
        return levels
    
    def calculate_rsi(self, klines):
        """计算 RSI"""
        if len(klines) < self.rsi_period + 1:
            return 50
        return RSI(klines, self.rsi_period).iloc[-1]
    
    def find_nearest_fib(self, price):
        """找到最近的斐波那契回撤位"""
        if not self.fib_levels_dict:
            return None
            
        distances = {abs(price - v): k for k, v in self.fib_levels_dict.items()}
        nearest_level = distances[min(distances.keys())]
        return nearest_level, self.fib_levels_dict[nearest_level]
    
    def on_bar(self, klines):
        """K 线回调函数"""
        if len(klines) < 30:
            return
            
        fib_levels = self.calculate_fib_retracement(klines)
        current_price = klines['close'].iloc[-1]
        rsi = self.calculate_rsi(klines)
        
        if self.position == 0:
            # 寻找做多机会：价格回撤到斐波那契支撑位 + RSI 超卖
            for level, price in fib_levels.items():
                if abs(current_price - price) / price < 0.005:  # 接近回撤位
                    if rsi < self.rsi_oversold:
                        self.position = 1
                        self.entry_price = current_price
                        print(f"[买入] 价格: {current_price}, 斐波位: {level}, RSI: {rsi:.2f}")
                        break
                        
        elif self.position == 1:
            # 止损检查
            atr = ATR(klines, 14).iloc[-1]
            if current_price < self.entry_price - atr * self.atr_multi:
                print(f"[多头止损] 价格: {current_price}")
                self.position = 0
                self.entry_price = 0
            # RSI 超买时平仓
            elif rsi > self.rsi_overbought:
                print(f"[多头平仓 RSI超买] 价格: {current_price}, RSI: {rsi:.2f}")
                self.position = 0
                self.entry_price = 0


def main():
    api = TqApi()
    
    symbol = "SHFE.rb2505"
    strategy = FibonacciStrategy(
        api,
        symbol=symbol,
        fib_levels=[0.236, 0.382, 0.5, 0.618, 0.786],
        rsi_period=14,
        rsi_oversold=35,
        rsi_overbought=65,
        atr_multi=2.5
    )
    
    klines = api.get_kline_serial(symbol, 60)
    
    while True:
        api.wait_update()
        if api.is_changing(klines):
            strategy.on_bar(klines)
    
    api.close()


if __name__ == "__main__":
    main()
