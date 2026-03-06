#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VWAP均值回归策略 (VWAP Mean Reversion Strategy)
================================================

策略逻辑：
    - 计算成交量加权平均价（VWAP）作为基准线
    - 当价格偏离VWAP超过一定幅度时，进行均值回归交易
    - 价格高于VWAP时做空，低于VWAP时做多
    - 使用 TargetPosTask 管理持仓

适用品种：
    日内交易活跃的品种，如股指期货、金属期货等

风险提示：
    - 趋势行情中可能出现较大亏损
    - 建议设置止损保护
    - 本代码仅供学习参考，不构成任何投资建议

参数说明：
    SYMBOL      : 交易合约代码
    VWAP_PERIOD : VWAP计算周期
    DEVIATION   : 偏离VWAP的开仓阈值（百分比）
    KLINE_DUR   : K线周期（秒）
    VOLUME      : 持仓手数

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
日期：2026-03-06
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import std, mean

# ===================== 策略参数 =====================
SYMBOL = "SHFE.rb2505"      # 交易合约
VWAP_PERIOD = 20            # VWAP计算周期
DEVIATION = 0.5             # 偏离阈值（百分比）
KLINE_DUR = 300             # 5分钟K线
VOLUME = 5                  # 持仓手数
# ====================================================

def calculate_vwap(close_list, vol_list, period):
    """计算成交量加权平均价"""
    if len(close_list) < period:
        return None
    recent_close = close_list[-period:]
    recent_vol = vol_list[-period:]
    vwap = sum(c * v for c, v in zip(recent_close, recent_vol)) / sum(recent_vol)
    return vwap

def main():
    api = TqApi(auth=TqAuth("13556817485", "asd159753"))
    
    kline = api.get_kline_serial(SYMBOL, KLINE_DUR)
    target_pos = TargetPosTask(api, SYMBOL)
    
    print(f"启动VWAP均值回归策略: {SYMBOL}")
    print(f"参数: VWAP周期={VWAP_PERIOD}, 偏离阈值={DEVIATION}%")
    
    while True:
        api.wait_update()
        
        if len(kline) < VWAP_PERIOD + 1:
            continue
        
        close_list = list(kline["close"])
        vol_list = list(kline["volume"])
        
        vwap = calculate_vwap(close_list, vol_list, VWAP_PERIOD)
        if vwap is None:
            continue
        
        current_price = close_list[-1]
        deviation_pct = (current_price - vwap) / vwap * 100
        
        if deviation_pct > DEVIATION:
            # 价格高于VWAP，做空
            target_pos.set_target_volume(-VOLUME)
            print(f"[卖出] 价格:{current_price:.2f} VWAP:{vwap:.2f} 偏离:{deviation_pct:.2f}%")
        elif deviation_pct < -DEVIATION:
            # 价格低于VWAP，做多
            target_pos.set_target_volume(VOLUME)
            print(f"[买入] 价格:{current_price:.2f} VWAP:{vwap:.2f} 偏离:{deviation_pct:.2f}%")
        elif abs(deviation_pct) < DEVIATION / 2:
            # 回归原点，平仓
            target_pos.set_target_volume(0)
            print(f"[平仓] 价格:{current_price:.2f} VWAP:{vwap:.2f} 偏离:{deviation_pct:.2f}%")

if __name__ == "__main__":
    main()
