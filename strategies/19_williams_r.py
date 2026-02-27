"""
================================================================================
策略19：威廉指标策略（Williams %R Strategy）
================================================================================

【策略背景与来源】
威廉指标（Williams %R，简称%R）由著名期货交易大师Larry Williams于1973年创立，
并在其著作《How I Made One Million Dollars Last Year Trading Commodities》中
详细介绍。Larry Williams本人凭借出色的短线交易技术，曾在1987年世界期货锦标赛
中将1万美元交易至114万美元，创下11340%的惊人年化收益率纪录。%R指标是他核心
工具箱的重要组成部分。威廉指标与KDJ中的K值原理相似，但方向相反，是衡量当前
价格在最近N个周期价格范围中所处位置的超买超卖振荡指标，在期货日内交易中广受
职业交易者青睐。

【核心逻辑】
%R衡量的是：当前收盘价相对于最近N周期最高价-最低价范围的位置比例。
其计算结果为负数（-100 ~ 0），与KDJ思路类似但方向相反：
- %R接近0（如 > -20）：说明价格处于N周期高位 → 超买区域 → 可能回落
- %R接近-100（如 < -80）：说明价格处于N周期低位 → 超卖区域 → 可能反弹

策略核心：
1. 等待%R进入超卖区（< -80），然后向上反弹离开超卖区 → 做多
2. 等待%R进入超买区（> -20），然后向下回落离开超买区 → 做空
3. 可以结合趋势过滤（如均线方向），避免在趋势行情中逆势做单

【计算公式】
设周期为N：
  Highest_High = HHV(high, N)   # 最近N根K线最高价的最大值
  Lowest_Low   = LLV(low, N)    # 最近N根K线最低价的最小值
  
  %R = (Highest_High - Close) / (Highest_High - Lowest_Low) × (-100)

取值范围：-100 ~ 0
  %R = 0    ：收盘价等于N周期最高价（最强超买）
  %R = -100 ：收盘价等于N周期最低价（最强超卖）
  %R = -50  ：收盘价处于N周期价格范围正中间

【交易信号说明】
做多信号：%R从超卖区（< OVERSOLD_LINE）向上突破进入中性区 → 开多仓
          即：前一根%R < OVERSOLD_LINE 且 当前%R > OVERSOLD_LINE（上穿超卖线）
          
做空信号：%R从超买区（> OVERBOUGHT_LINE）向下突破进入中性区 → 开空仓
          即：前一根%R > OVERBOUGHT_LINE 且 当前%R < OVERBOUGHT_LINE（下穿超买线）
          
平多仓：%R上升进入超买区（> OVERBOUGHT_LINE）→ 止盈平多（set_target_volume(0)）
平空仓：%R下降进入超卖区（< OVERSOLD_LINE）→ 止盈平空（set_target_volume(0)）

辅助过滤：结合MA均线方向，只在趋势方向上交易：
  均线向上时只做多，均线向下时只做空

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑，代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发

【适用品种和周期】
适用品种：有明显日内波动规律的品种，如铜CU、黄金AU、股指IF、IM
适用周期：1分钟~15分钟（日内短线），日线信号更稳但频率低
最佳场景：震荡型市场（日内区间震荡），趋势市场效果较差

【优缺点分析】
优点：
  1. 计算简单，原理直观，超买超卖概念易于理解
  2. 对短期价格极值的反应非常灵敏，信号出现早
  3. 配合趋势过滤器使用效果显著提升
  4. 适合日内高频交易，与K线形态结合可提高胜率

缺点：
  1. 在强趋势行情中，%R可长期处于超买/超卖区域，产生大量假信号
  2. 单独使用胜率不高，需要辅助条件过滤
  3. 参数N对信号频率影响较大（N小=信号多但噪音大，N大=信号少但滞后）
  4. 不提供趋势方向信息，只能判断相对强弱

【参数说明】
SYMBOL          : 交易品种，默认铜期货 SHFE.cu2405
WR_PERIOD       : 威廉指标计算周期，默认14根K线
OVERBOUGHT_LINE : 超买线，默认-20（即%R > -20时为超买）
OVERSOLD_LINE   : 超卖线，默认-80（即%R < -80时为超卖）
MA_PERIOD       : 趋势过滤均线周期，默认20，设为0则不过滤
KLINE_DURATION  : K线周期（秒），默认300秒（5分钟）
VOLUME          : 每次下单手数，默认1手
DATA_LENGTH     : 历史K线数量
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ma, hhv, llv

# ==================== 策略参数配置 ====================
SYMBOL          = "SHFE.cu2405"   # 交易品种：铜主力合约
WR_PERIOD       = 14               # 威廉指标计算周期
OVERBOUGHT_LINE = -20              # 超买线（%R > -20 为超买）
OVERSOLD_LINE   = -80              # 超卖线（%R < -80 为超卖）
MA_PERIOD       = 20               # 趋势过滤均线周期（0则不使用均线过滤）
KLINE_DURATION  = 5 * 60           # K线周期：5分钟（秒）
VOLUME          = 1                # 每次交易手数
DATA_LENGTH     = 300              # 历史K线数量


def calc_williams_r(high, low, close, period):
    """
    计算威廉指标 %R
    
    参数：
        high:   最高价序列（pandas Series）
        low:    最低价序列（pandas Series）
        close:  收盘价序列（pandas Series）
        period: 计算周期
    
    返回：
        wr: Williams %R序列（pandas Series，取值-100~0）
    """
    # 最近period根K线的最高价（滚动最大值）
    highest_high = hhv(high, period)   # 使用tafunc的hhv函数

    # 最近period根K线的最低价（滚动最小值）
    lowest_low   = llv(low, period)    # 使用tafunc的llv函数

    # 分母（价格范围），避免为0
    price_range  = highest_high - lowest_low
    price_range  = price_range.replace(0, np.nan)  # 避免除零

    # Williams %R 公式
    wr = (highest_high - close) / price_range * (-100)

    return wr


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[威廉指标策略] 启动，品种={SYMBOL}, %R周期={WR_PERIOD}, "
          f"超买={OVERBOUGHT_LINE}, 超卖={OVERSOLD_LINE}")

    # 获取K线数据
    klines   = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)
    account  = api.get_account()

    # 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    try:
        while True:
            api.wait_update()

            # 在K线更新时重新计算指标
            if api.is_changing(klines.iloc[-1], "datetime"):

                high  = klines["high"]
                low   = klines["low"]
                close = klines["close"]

                # ====== 计算威廉指标 %R ======
                wr = calc_williams_r(high, low, close, WR_PERIOD)

                # 取最新两根K线的%R值
                wr_now  = wr.iloc[-1]   # 当前%R值
                wr_prev = wr.iloc[-2]   # 上一根K线%R值

                # ====== 计算趋势过滤均线（可选） ======
                if MA_PERIOD > 0:
                    ma_line  = ma(close, MA_PERIOD)     # MA均线序列
                    ma_now   = ma_line.iloc[-1]          # 当前均线值
                    ma_prev  = ma_line.iloc[-2]          # 上一根均线值
                    trend_up = ma_now > ma_prev          # 均线向上为多头趋势
                else:
                    trend_up = True   # 不过滤时，双向均可交易

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"%R当前={wr_now:.2f}, %R前值={wr_prev:.2f}, "
                      f"均线{'↑' if trend_up else '↓'}")

                # ====== 检测超买超卖穿越信号 ======

                # 超卖上穿信号：前一根 < 超卖线，当前 > 超卖线（从超卖区向上离开）
                cross_out_oversold   = (wr_prev < OVERSOLD_LINE) and (wr_now >= OVERSOLD_LINE)

                # 超买下穿信号：前一根 > 超买线，当前 < 超买线（从超买区向下离开）
                cross_out_overbought = (wr_prev > OVERBOUGHT_LINE) and (wr_now <= OVERBOUGHT_LINE)

                # 进入超买区（止盈多仓信号）
                enter_overbought = (wr_prev <= OVERBOUGHT_LINE) and (wr_now > OVERBOUGHT_LINE)

                # 进入超卖区（止盈空仓信号）
                enter_oversold   = (wr_prev >= OVERSOLD_LINE) and (wr_now < OVERSOLD_LINE)

                # ====== 交易逻辑 ======

                # --- 做多：%R从超卖区向上离开，且均线向上（趋势过滤） ---
                if cross_out_oversold and trend_up:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 开多仓 {VOLUME}手（%R={wr_now:.2f}上穿超卖线{OVERSOLD_LINE}）")

                # --- 做空：%R从超买区向下离开，且均线向下（趋势过滤） ---
                elif cross_out_overbought and not trend_up:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 开空仓 {VOLUME}手（%R={wr_now:.2f}下穿超买线{OVERBOUGHT_LINE}）")

                # --- 止盈平多：%R进入超买区 ---
                elif enter_overbought:
                    target_pos.set_target_volume(0)
                    print(f"  → 多仓止盈平仓（%R={wr_now:.2f}进入超买区）")

                # --- 止盈平空：%R进入超卖区 ---
                elif enter_oversold:
                    target_pos.set_target_volume(0)
                    print(f"  → 空仓止盈平仓（%R={wr_now:.2f}进入超卖区）")

    finally:
        api.close()
        print("[威廉指标策略] 已退出")


if __name__ == "__main__":
    main()
