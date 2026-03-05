#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
策略19：ATR通道突破策略（ATR Channel Breakout）
================================================================================

【策略背景与来源】
ATR（Average True Range，平均真实波幅）由Welles Wilder于1978年提出，是
衡量市场波动性的重要指标。ATR通道突破策略利用ATR来构建动态的交易通道，
当价格突破通道上轨时做多，突破下轨时做空。这种策略特别适合捕捉趋势行情，
在波动率较高的市场环境中表现较好。

【核心逻辑】
1. 计算ATR（平均真实波幅）
2. 计算通道中轨（价格移动平均）
3. 上轨 = 中轨 + ATR × 倍数
4. 下轨 = 中轨 - ATR × 倍数
5. 价格突破上轨时做多，突破下轨时做空
6. 价格回归到中轨时平仓

【参数说明】
SYMBOL        : 交易品种
ATR_PERIOD    : ATR计算周期，默认14
ATR_MULTI     : ATR倍数，默认2.5
MA_PERIOD     : 通道中轨周期，默认20
KLINE_DURATION: K线周期（秒），默认300
VOLUME        : 每次交易手数，默认1
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ma

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.rb2505"    # 交易品种：螺纹钢主力合约
ATR_PERIOD     = 14               # ATR计算周期
ATR_MULTI      = 2.5              # ATR倍数
MA_PERIOD      = 20               # 通道中轨周期
KLINE_DURATION = 5 * 60           # K线周期：5分钟
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 200              # 历史K线数量


def calc_atr(high, low, close, period):
    """计算ATR（平均真实波幅）"""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr


def main():
    api = TqApi(account=TqSim(), auth=TqAuth("账号", "密码"))
    print(f"[ATR通道突破] 启动，品种={SYMBOL}")

    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, DATA_LENGTH)
    target_pos = TargetPosTask(api, SYMBOL)

    try:
        while True:
            api.wait_update()
            if api.is_changing(klines.iloc[-1], "datetime"):
                high = klines["high"]
                low = klines["low"]
                close = klines["close"]
                
                atr = calc_atr(high, low, close, ATR_PERIOD)
                middle = ma(close, MA_PERIOD)
                
                upper = middle + atr * ATR_MULTI
                lower = middle - atr * ATR_MULTI
                
                price = close.iloc[-1]
                middle_val = middle.iloc[-1]
                upper_val = upper.iloc[-1]
                lower_val = lower.iloc[-1]
                atr_val = atr.iloc[-1]
                
                print(f"[{klines.iloc[-1]['datetime']}] 价格={price:.2f}, "
                      f"通道={lower_val:.2f}~{middle_val:.2f}~{upper_val:.2f}, ATR={atr_val:.2f}")
                
                # 做多：价格突破上轨
                if price > upper_val:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 开多仓（突破上轨）")
                
                # 做空：价格突破下轨
                elif price < lower_val:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 开空仓（突破下轨）")
                
                # 平多：价格回到中轨下方
                elif price < middle_val and target_pos.get_target_volume() > 0:
                    target_pos.set_target_volume(0)
                    print(f"  → 平多仓（回归中轨）")
                
                # 平空：价格回到中轨上方
                elif price > middle_val and target_pos.get_target_volume() < 0:
                    target_pos.set_target_volume(0)
                    print(f"  → 平空仓（回归中轨）")
    
    finally:
        api.close()
        print("[ATR通道突破策略] 已退出")


if __name__ == "__main__":
    main()
