"""
================================================================================
策略22：TRIX三重指数平均策略（Triple Exponential Average Strategy）
================================================================================

【策略背景与来源】
TRIX（Triple Exponential Average，三重指数平均）指标由Jack Hutson于1983年在
Technical Analysis of Stocks & Commodities杂志上发表。TRIX的核心思想是通过
对EMA进行三次平滑处理，从而有效过滤掉价格序列中的短期随机噪音和无意义的
小幅震荡，只保留有实质意义的中长期趋势信号。

TRIX与MACD有相似之处，都基于EMA的差值来衡量价格动量，但TRIX更加平滑，
对噪音的抑制能力更强。由于进行了三次EMA处理，TRIX对于短期的价格尖刺和假
突破具有天然的过滤效果，特别适合中长期趋势追踪。

在实际应用中，TRIX常被配合其信号线（Signal Line，即TRIX的MA）一起使用，
通过两线交叉产生交易信号，这与MACD的双线交叉策略如出一辙。

【核心逻辑】
第一步：计算三重EMA
  EMA1 = EMA(close, N)          # 第一重EMA
  EMA2 = EMA(EMA1, N)           # 第二重EMA（对EMA1再做EMA）
  EMA3 = EMA(EMA2, N)           # 第三重EMA（对EMA2再做EMA）

第二步：计算TRIX值（变化率）
  TRIX(t) = (EMA3(t) - EMA3(t-1)) / EMA3(t-1) × 100
  即：三重EMA的环比变化率（百分比）

第三步：计算信号线
  Signal = MA(TRIX, M)           # TRIX的M周期简单移动平均

第四步：交叉信号
  TRIX上穿Signal → 做多
  TRIX下穿Signal → 做空

TRIX的三次平滑使其相当于一个非常平滑的动量指标，其绕零轴的振荡幅度小、
转折次数少，每次转折都代表较大级别的趋势变化。

【计算公式】
设主周期为N，信号线周期为M：

  EMA1(t) = EMA(close, N)
  EMA2(t) = EMA(EMA1, N)
  EMA3(t) = EMA(EMA2, N)
  
  TRIX(t) = (EMA3(t) - EMA3(t-1)) / EMA3(t-1) × 100
  
  Signal(t) = MA(TRIX, M)    # M周期简单移动平均

零轴上方表示上涨动量，零轴下方表示下跌动量：
  TRIX > 0 且 TRIX在增加：上涨趋势加速
  TRIX > 0 但 TRIX在减少：上涨趋势减弱
  TRIX < 0 且 TRIX在减少：下跌趋势加速
  TRIX < 0 但 TRIX在增加：下跌趋势减弱

【交易信号说明】
主信号（双线交叉）：
  开多仓：TRIX上穿Signal（crossup），且TRIX > 0（在零轴上方，确认多头趋势）
  开空仓：TRIX下穿Signal（crossdown），且TRIX < 0（在零轴下方，确认空头趋势）

辅助信号（零轴穿越，可选）：
  TRIX由负转正（上穿零轴）→ 中长期多头趋势确立
  TRIX由正转负（下穿零轴）→ 中长期空头趋势确立

平仓信号：
  平多仓：TRIX下穿Signal或TRIX下穿零轴
  平空仓：TRIX上穿Signal或TRIX上穿零轴

【适用品种和周期】
适用品种：趋势性较强的中大型合约，如黄金AU、原油SC、铜CU、螺纹钢RB
适用周期：30分钟~日线（TRIX本身三重平滑使其在短周期无实用价值）
最佳场景：单边趋势行情持仓中期（数日~数周）

【优缺点分析】
优点：
  1. 三重平滑有效过滤短期噪音，假信号比MACD更少
  2. 以变化率表示，适合跨品种横向对比趋势强度
  3. 信号频率低，持仓时间长，手续费成本低
  4. 零轴方向提供趋势方向参考，信号层次丰富

缺点：
  1. 三重平滑导致极度滞后，趋势初期信号出现很晚
  2. 不适合短线和日内交易，周期过短时信号无意义
  3. 在震荡市场中，零轴频繁穿越会产生误导信号
  4. 参数N的选择对信号频率和质量影响极大

【参数说明】
SYMBOL        : 交易品种，默认黄金期货 SHFE.au2406
TRIX_PERIOD   : 三重EMA计算周期，默认12根K线
SIGNAL_PERIOD : 信号线平均周期，默认9根K线
KLINE_DURATION: K线周期（秒），默认1800秒（30分钟）
VOLUME        : 每次下单手数，默认1手
DATA_LENGTH   : 历史K线数量，建议 > TRIX_PERIOD × 10
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ema, ma, crossup, crossdown

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.au2406"   # 交易品种：黄金主力合约
TRIX_PERIOD    = 12               # TRIX三重EMA的计算周期
SIGNAL_PERIOD  = 9                # 信号线平均周期（TRIX的MA）
KLINE_DURATION = 30 * 60          # K线周期：30分钟（秒）
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 500              # 历史K线数量（需要足够长以稳定三重EMA）


def calc_trix(close, period, signal_period):
    """
    计算TRIX三重指数平均指标及其信号线
    
    参数：
        close:         收盘价序列（pandas Series）
        period:        三重EMA的周期
        signal_period: 信号线（TRIX的MA）周期
    
    返回：
        trix:   TRIX值序列（pandas Series，单位：%）
        signal: 信号线序列（pandas Series）
    """
    # 第一重EMA
    ema1 = ema(close, period)

    # 第二重EMA（对第一重EMA再做EMA，而不是对close）
    ema2 = ema(ema1, period)

    # 第三重EMA（对第二重EMA再做EMA）
    ema3 = ema(ema2, period)

    # TRIX = (EMA3当前 - EMA3上一根) / EMA3上一根 × 100
    # 即三重EMA的环比变化率（%）
    ema3_prev = ema3.shift(1)                             # 上一根的EMA3值
    trix      = (ema3 - ema3_prev) / ema3_prev * 100     # TRIX变化率

    # 信号线：TRIX的M周期简单移动平均
    signal = ma(trix, signal_period)

    return trix, signal


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[TRIX策略] 启动，品种={SYMBOL}, TRIX周期={TRIX_PERIOD}, "
          f"信号线={SIGNAL_PERIOD}, K线={KLINE_DURATION//60}分钟")

    # 获取K线数据
    klines   = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)
    account  = api.get_account()
    position = api.get_position(SYMBOL)

    try:
        while True:
            api.wait_update()

            # 在K线收盘时重新计算
            if api.is_changing(klines.iloc[-1], "datetime"):

                close = klines["close"]

                # ====== 计算TRIX和信号线 ======
                trix, signal = calc_trix(close, TRIX_PERIOD, SIGNAL_PERIOD)

                # 取最新值
                trix_now   = trix.iloc[-1]     # 当前TRIX值
                signal_now = signal.iloc[-1]   # 当前信号线值
                trix_prev  = trix.iloc[-2]     # 上一根TRIX值

                # ====== 检测交叉信号 ======
                # TRIX上穿信号线（看多）
                cross_up_sig   = crossup(trix, signal)
                # TRIX下穿信号线（看空）
                cross_down_sig = crossdown(trix, signal)

                last_cross_up   = bool(cross_up_sig.iloc[-1])
                last_cross_down = bool(cross_down_sig.iloc[-1])

                # ====== 检测零轴穿越 ======
                trix_cross_zero_up   = (trix_prev < 0) and (trix_now >= 0)   # TRIX上穿零轴
                trix_cross_zero_down = (trix_prev > 0) and (trix_now <= 0)   # TRIX下穿零轴

                # ====== 读取持仓状态 ======
                pos_long  = position.volume_long
                pos_short = position.volume_short

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"TRIX={trix_now:.6f}%, Signal={signal_now:.6f}%, "
                      f"多={pos_long}, 空={pos_short}")

                # ====== 交易逻辑 ======

                # --- 做多信号1：TRIX上穿Signal，且TRIX在零轴上方（趋势确认） ---
                if last_cross_up and trix_now > 0:
                    if pos_short > 0:
                        # 先平空仓
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",
                            offset    = "CLOSE",
                            volume    = pos_short
                        )
                        print(f"  → 平空仓 {pos_short}手")

                    if pos_long == 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",
                            offset    = "OPEN",
                            volume    = VOLUME
                        )
                        print(f"  → 开多仓 {VOLUME}手（TRIX={trix_now:.6f}%上穿Signal，零轴上方）")

                # --- 做多信号2：TRIX上穿零轴（中期多头趋势确立） ---
                elif trix_cross_zero_up and pos_long == 0 and pos_short == 0:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "BUY",
                        offset    = "OPEN",
                        volume    = VOLUME
                    )
                    print(f"  → 开多仓 {VOLUME}手（TRIX上穿零轴，中期多头确立）")

                # --- 做空信号1：TRIX下穿Signal，且TRIX在零轴下方（趋势确认） ---
                elif last_cross_down and trix_now < 0:
                    if pos_long > 0:
                        # 先平多仓
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",
                            offset    = "CLOSE",
                            volume    = pos_long
                        )
                        print(f"  → 平多仓 {pos_long}手")

                    if pos_short == 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",
                            offset    = "OPEN",
                            volume    = VOLUME
                        )
                        print(f"  → 开空仓 {VOLUME}手（TRIX={trix_now:.6f}%下穿Signal，零轴下方）")

                # --- 做空信号2：TRIX下穿零轴（中期空头趋势确立） ---
                elif trix_cross_zero_down and pos_long == 0 and pos_short == 0:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "SELL",
                        offset    = "OPEN",
                        volume    = VOLUME
                    )
                    print(f"  → 开空仓 {VOLUME}手（TRIX下穿零轴，中期空头确立）")

                # --- 平多仓：TRIX下穿Signal（趋势减弱，止盈） ---
                elif pos_long > 0 and last_cross_down:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "SELL",
                        offset    = "CLOSE",
                        volume    = pos_long
                    )
                    print(f"  → 平多仓 {pos_long}手（TRIX下穿Signal，止盈离场）")

                # --- 平空仓：TRIX上穿Signal（趋势减弱，止盈） ---
                elif pos_short > 0 and last_cross_up:
                    api.insert_order(
                        symbol    = SYMBOL,
                        direction = "BUY",
                        offset    = "CLOSE",
                        volume    = pos_short
                    )
                    print(f"  → 平空仓 {pos_short}手（TRIX上穿Signal，止盈离场）")

    finally:
        api.close()
        print("[TRIX策略] 已退出")


if __name__ == "__main__":
    main()
