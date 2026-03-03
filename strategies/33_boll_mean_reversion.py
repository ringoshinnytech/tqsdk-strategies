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

策略名称：BOLL 布林带均值回归策略
策略编号：33
作者：TqSdk 策略库
更新日期：2026-03-03

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

布林带（Bollinger Bands，简称 BOLL）是由 John Bollinger 于 1980 年代发明的
技术分析工具。它由三条线组成：中轨为 N 日简单移动平均线（MA），上轨和下轨
分别为中轨加减 K 倍标准差。

布林带的核心理念基于统计学原理：
  1. 价格在大部分时间内（约 95%）会在 ±2 倍标准差范围内波动
  2. 当价格触及或突破布林带上下轨时，往往意味着短期超买或超卖
  3. 布林带收窄表示市场波动率降低，可能酝酿突破行情
  4. 布林带开口放大表示波动率增加，趋势可能加速

本策略采用均值回归思路：
  1. 当价格触及下轨时，做多进场（超卖反弹）
  2. 当价格触及上轨时，做空进场（超买回落）
  3. 当价格回归中轨时，平仓了结

【策略特点】

  1. 简单直观：布林带是普及度最高的技术指标之一，信号清晰易判
  2. 适应性广：适用于商品期货、金融期货、股票等多种标的
  3. 参数灵活：可通过调整周期 N 和标准差倍数 K 适应不同市场
  4. 震荡利器：在区间震荡行情中表现优异

【适用品种与时间周期】

  推荐品种：波动性适中的主力合约，如螺纹钢(rb)、甲醇(MA)、
            豆粕(m)、股指期货(IF/IC) 等。
  推荐周期：15 分钟或 30 分钟 K 线。
  不适合：长时间横盘后突破行情，可能连续止损。

【参数说明】

  SYMBOL         : 目标合约代码
  KLINE_FREQ     : K 线周期（秒），默认 900 秒（15 分钟）
  BOLL_PERIOD    : 布林带中轨周期，默认 20
  BOLL_STD       : 标准差倍数，默认 2.0
  LOT_SIZE       : 每次开仓手数
  CLOSE_HOUR     : 强制平仓小时，默认 14 时 50 分

【风险提示】

  1. 趋势行情中可能出现连续止损，建议配合趋势过滤器使用
  2. 极端行情下价格可能穿越布林带后继续运行，需设止损
  3. 隔夜持仓需关注外盘走势和跳空风险
  4. 回测结果不代表未来表现，实盘前请充分测试
"""

from tqsdk import TqApi, TqAuth, TqBacktest
from tqsdk.ta import BOLL
import pandas as pd

# ============ 策略参数 ============
SYMBOL = "SHFE.rb2405"       # 交易合约
KLINE_FREQ = 900             # K线周期: 15分钟
BOLL_PERIOD = 20             # 布林带周期
BOLL_STD = 2.0               # 标准差倍数
LOT_SIZE = 1                 # 开仓手数
CLOSE_HOUR = 14              # 强制平仓小时
CLOSE_MINUTE = 50            # 强制平仓分钟


def main():
    api = TqApi(auth=TqAuth("账号", "密码"))
    
    print(f"策略启动: BOLL 布林带均值回归策略")
    print(f"交易品种: {SYMBOL}")
    
    # 获取K线数据
    klines = api.get_kline_serial(SYMBOL, KLINE_FREQ, data_length=BOLL_PERIOD + 10)
    
    position = 0  # 持仓: 1多头, -1空头, 0空仓
    
    while True:
        # 等待K线更新
        api.wait_update(klines)
        
        if len(klines) < BOLL_PERIOD + 5:
            continue
        
        # 转换为DataFrame计算布林带
        df = pd.DataFrame(klines)
        df['close'] = df['close'].astype(float)
        
        # 计算布林带
        boll = BOLL(df['close'], period=BOLL_PERIOD, std_multiplier=BOLL_STD)
        df['boll_mid'] = boll['mid'].values
        df['boll_upp'] = boll['upp'].values
        df['boll_low'] = boll['low'].values
        
        current_price = df['close'].iloc[-1]
        boll_mid = df['boll_mid'].iloc[-1]
        boll_upp = df['boll_upp'].iloc[-1]
        boll_low = df['boll_low'].iloc[-1]
        
        # 获取当前时间
        current_time = api.get_current_datetime()
        hour = current_time.hour
        minute = current_time.minute
        
        # 尾盘强制平仓
        if hour >= CLOSE_HOUR and minute >= CLOSE_MINUTE:
            if position != 0:
                print(f"[{current_time}] 尾盘平仓")
                api.close_position()
                position = 0
            continue
        
        # 交易信号判断
        if position == 0:
            # 价格触及下轨，做多
            if current_price <= boll_low:
                print(f"[{current_time}] 价格触及下轨，做多 | 价格: {current_price:.2f} < 布林下轨: {boll_low:.2f}")
                api.insert_order(symbol=SYMBOL, direction="long", offset="open", volume=LOT_SIZE)
                position = 1
            
            # 价格触及上轨，做空
            elif current_price >= boll_upp:
                print(f"[{current_time}] 价格触及上轨，做空 | 价格: {current_price:.2f} > 布林上轨: {boll_upp:.2f}")
                api.insert_order(symbol=SYMBOL, direction="short", offset="open", volume=LOT_SIZE)
                position = -1
        
        # 持仓状态下价格回归中轨，平仓
        elif position == 1 and current_price >= boll_mid:
            print(f"[{current_time}] 价格回归中轨，平多仓 | 价格: {current_price:.2f} >= 中轨: {boll_mid:.2f}")
            api.insert_order(symbol=SYMBOL, direction="short", offset="close", volume=LOT_SIZE)
            position = 0
            
        elif position == -1 and current_price <= boll_mid:
            print(f"[{current_time}] 价格回归中轨，平空仓 | 价格: {current_price:.2f} <= 中轨: {boll_mid:.2f}")
            api.insert_order(symbol=SYMBOL, direction="long", offset="close", volume=LOT_SIZE)
            position = 0
    
    api.close()


if __name__ == "__main__":
    main()
