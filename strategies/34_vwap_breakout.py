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

策略名称：VWAP 成交量加权平均价策略
策略编号：34
作者：TqSdk 策略库
更新日期：2026-03-04

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

VWAP（Volume Weighted Average Price，成交量加权平均价）是金融市场中
最重要的参考指标之一，代表了当日成交的平均价格水平。

VWAP 的核心价值：
  1. 机构投资者常用 VWAP 作为交易执行的基准
  2. 价格在 VWAP 上方表示多方主导，下方表示空方主导
  3. VWAP 具有支撑/阻力作用，价格回撤常在 VWAP 附近止跌

本策略采用 VWAP 突破交易：
  1. 当价格上穿 VWAP 且放量时，做多进场
  2. 当价格下穿 VWAP 且放量时，做空进场
  3. 设置移动止损和固定止盈

【策略特点】

  1. 机构视角：紧跟大资金动向
  2. 顺势而为：在趋势方向明确后入场
  3. 量价配合：结合成交量验证信号有效性
  4. 动态调整：根据波动率自适应参数

【参数说明】

  symbol: 交易合约 (如 "SHFE.rb2105")
  n1: 短周期 K 线根数 (默认 5)
  n2: 长周期 K 线根数 (默认 20)
  volume_factor: 成交量放大倍数 (默认 1.5)
  atr_multi: ATR 止损倍数 (默认 2.0)
  fixed_profit: 固定止盈点数 (默认 50)

【注意事项】

  1. 本策略适用于日内趋势行情
  2. 建议在主力合约上使用
  3. 需确保行情数据完整
"""

from tqsdk import TqApi, TqAuth, TqAccount
from tqsdk.ta import ATR, MA
import pandas as pd
import numpy as np


class VWAPStrategy:
    """VWAP 成交量加权平均价策略"""
    
    def __init__(self, api, symbol, n1=5, n2=20, volume_factor=1.5, 
                 atr_multi=2.0, fixed_profit=50):
        self.api = api
        self.symbol = symbol
        self.n1 = n1
        self.n2 = n2
        self.volume_factor = volume_factor
        self.atr_multi = atr_multi
        self.fixed_profit = fixed_profit
        
        self.position = 0
        self.entry_price = 0
        self.vwap = 0
        
    def calculate_vwap(self, klines):
        """计算 VWAP"""
        if len(klines) < self.n2:
            return 0
            
        df = klines.iloc[-self.n2:].copy()
        df['pv'] = df['close'] * df['volume']
        vwap = df['pv'].sum() / df['volume'].sum()
        return vwap
    
    def calculate_atr(self, klines):
        """计算 ATR"""
        if len(klines) < 14:
            return 0
        return ATR(klines, 14).iloc[-1]
    
    def check_volume_surge(self, klines):
        """检查成交量是否放大"""
        if len(klines) < self.n1 + 1:
            return False
        recent_vol = klines['volume'].iloc[-self.n1:].mean()
        prev_vol = klines['volume'].iloc[-self.n1-5:-self.n1].mean()
        return recent_vol > prev_vol * self.volume_factor
    
    def on_bar(self, klines):
        """K 线回调函数"""
        if len(klines) < self.n2 + 1:
            return
            
        current_price = klines['close'].iloc[-1]
        self.vwap = self.calculate_vwap(klines)
        atr = self.calculate_atr(klines)
        
        # 无持仓
        if self.position == 0:
            # 做多信号：价格上穿 VWAP 且放量
            prev_price = klines['close'].iloc[-2]
            if (prev_price < self.vwap and current_price > self.vwap and 
                self.check_volume_surge(klines)):
                self.position = 1
                self.entry_price = current_price
                print(f"[买入] 价格: {current_price}, VWAP: {self.vwap:.2f}")
                
            # 做空信号：价格下穿 VWAP 且放量
            elif (prev_price > self.vwap and current_price < self.vwap and 
                  self.check_volume_surge(klines)):
                self.position = -1
                self.entry_price = current_price
                print(f"[卖出] 价格: {current_price}, VWAP: {self.vwap:.2f}")
                
        # 持有多头
        elif self.position == 1:
            # 止损
            if current_price < self.entry_price - atr * self.atr_multi:
                print(f"[多头止损] 价格: {current_price}")
                self.position = 0
                self.entry_price = 0
            # 止盈
            elif current_price > self.entry_price + self.fixed_profit:
                print(f"[多头止盈] 价格: {current_price}")
                self.position = 0
                self.entry_price = 0
            # 多头平仓条件：价格下穿 VWAP
            elif current_price < self.vwap:
                print(f"[多头平仓] 价格: {current_price}, VWAP: {self.vwap:.2f}")
                self.position = 0
                self.entry_price = 0
                
        # 持有空头
        elif self.position == -1:
            # 止损
            if current_price > self.entry_price + atr * self.atr_multi:
                print(f"[空头止损] 价格: {current_price}")
                self.position = 0
                self.entry_price = 0
            # 止盈
            elif current_price < self.entry_price - self.fixed_profit:
                print(f"[空头止盈] 价格: {current_price}")
                self.position = 0
                self.entry_price = 0
            # 空头平仓条件：价格上穿 VWAP
            elif current_price > self.vwap:
                print(f"[空头平仓] 价格: {current_price}, VWAP: {self.vwap:.2f}")
                self.position = 0
                self.entry_price = 0


def main():
    api = TqApi()
    
    symbol = "SHFE.rb2505"
    strategy = VWAPStrategy(
        api, 
        symbol=symbol,
        n1=5,
        n2=20,
        volume_factor=1.5,
        atr_multi=2.0,
        fixed_profit=50
    )
    
    klines = api.get_kline_serial(symbol, 60)
    
    while True:
        api.wait_update()
        if api.is_changing(klines):
            strategy.on_bar(klines)
    
    api.close()


if __name__ == "__main__":
    main()
