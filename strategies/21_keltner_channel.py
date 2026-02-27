"""
================================================================================
策略21：肯特纳通道策略（Keltner Channel Strategy）
================================================================================

【策略背景与来源】
肯特纳通道（Keltner Channel）最初由Chester W. Keltner于1960年在其著作《How to
Make Money in Commodities》中提出，当时使用的是简单移动平均和价格真实范围的
简单计算。后来在1980年代，交易员Linda Bradford Raschke对其进行了改进，将中轨
改为EMA，波动带改为ATR（平均真实波幅），形成了现代版本的肯特纳通道。

肯特纳通道与布林带（Bollinger Bands）非常相似，区别在于：布林带用标准差衡量
波动率，肯特纳通道用ATR衡量波动率。ATR通常更平滑稳定，因此肯特纳通道较布林带
更加稳定、不容易被尖刺行情影响。两者可配合使用：当肯特纳通道收窄而布林带
扩张时，往往意味着即将出现大幅突破行情。

【核心逻辑】
肯特纳通道由三条线组成：
  中轨（Middle）：N周期EMA（指数移动平均）
  上轨（Upper） ：中轨 + ATR倍数 × ATR
  下轨（Lower） ：中轨 - ATR倍数 × ATR

ATR（Average True Range，平均真实波幅）衡量价格的日内波动强度：
  TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
  ATR = EMA(TR, ATR周期)

突破策略（本策略采用）：
  当价格上穿上轨 → 确认上涨趋势突破，做多
  当价格下穿下轨 → 确认下跌趋势突破，做空
  价格回到中轨附近时止盈

回归策略（反向思路）：
  价格触及上轨（超买）→ 预期回落做空
  价格触及下轨（超卖）→ 预期反弹做多

本策略采用突破做趋势方向，适合趋势行情。

【计算公式】
ATR计算（Wilder平滑）：
  TR(t) = max(High(t) - Low(t),
              |High(t) - Close(t-1)|,
              |Low(t) - Close(t-1)|)
  ATR(t) = EMA(TR, ATR_PERIOD)

通道计算：
  Middle(t) = EMA(close, EMA_PERIOD)
  Upper(t)  = Middle(t) + ATR_MULT × ATR(t)
  Lower(t)  = Middle(t) - ATR_MULT × ATR(t)

【交易信号说明】
突破上轨开多：收盘价上穿上轨（Close[-1] > Upper[-1]）且 Close[-2] <= Upper[-2]
突破下轨开空：收盘价下穿下轨（Close[-1] < Lower[-1]）且 Close[-2] >= Lower[-2]
平多仓条件：价格跌回中轨以下（set_target_volume(0)）
平空仓条件：价格涨回中轨以上（set_target_volume(0)）

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑，代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发

【适用品种和周期】
适用品种：波动性适中偏大的品种，如原油SC、铜CU、螺纹钢RB、股指IF
适用周期：15分钟~日线，周期越长信号越可靠（日线效果最佳）
最佳场景：有明显趋势突破特征的行情（单边大涨/大跌）
不适合：窄幅震荡、价格在通道内反复横跳的行情

【优缺点分析】
优点：
  1. 通道宽度自适应波动率（ATR），在高波动期自动扩大，低波动期自动收窄
  2. 突破信号清晰，操作简单
  3. 用EMA作为中轨，比SMA更贴近最新价格
  4. ATR比标准差更稳定，受极端值影响小
  5. 可与布林带配合使用，增强信号可靠性

缺点：
  1. 在震荡市场中，价格频繁触达上下轨但无法持续突破，产生假突破信号
  2. EMA_PERIOD 和 ATR_MULT 两个参数需要根据品种调优
  3. 趋势跟踪类策略，回撤可能较大
  4. 突破后进场，相比入场价格已有一定距离，滑点影响较大

【参数说明】
SYMBOL        : 交易品种，默认原油 INE.sc2406
EMA_PERIOD    : 中轨EMA周期，默认20根K线
ATR_PERIOD    : ATR计算周期，默认10根K线
ATR_MULT      : ATR乘数（通道宽度系数），默认2.0
KLINE_DURATION: K线周期（秒），默认900秒（15分钟）
VOLUME        : 每次下单手数，默认1手
DATA_LENGTH   : 历史K线数量，建议 > EMA_PERIOD × 3
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ema

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.rb2405"   # 交易品种：螺纹钢主力合约
EMA_PERIOD     = 20               # 中轨EMA周期
ATR_PERIOD     = 10               # ATR计算周期
ATR_MULT       = 2.0              # ATR倍数（通道宽度系数）
KLINE_DURATION = 15 * 60          # K线周期：15分钟（秒）
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 300              # 历史K线数量


def calc_atr(high, low, close, period):
    """
    计算ATR（平均真实波幅）
    
    TR（真实波幅）= max(当日高低差, |当日最高-昨日收盘|, |当日最低-昨日收盘|)
    ATR = EMA(TR, period)  使用Wilder平滑（ewm方式）
    
    参数：
        high:   最高价序列（pandas Series）
        low:    最低价序列（pandas Series）
        close:  收盘价序列（pandas Series）
        period: ATR计算周期
    返回：
        atr: ATR序列（pandas Series）
    """
    prev_close = close.shift(1)         # 昨日收盘价

    # 计算真实波幅TR的三个分量
    tr1 = high - low                    # 当日高低差
    tr2 = (high - prev_close).abs()    # 当日最高与昨收之差的绝对值
    tr3 = (low - prev_close).abs()     # 当日最低与昨收之差的绝对值

    # TR取三个分量的最大值
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 使用指数加权平均（Wilder方法）计算ATR
    atr = tr.ewm(alpha=1/period, adjust=False).mean()

    return atr


def calc_keltner_channel(close, high, low, ema_period, atr_period, atr_mult):
    """
    计算肯特纳通道的上轨、中轨、下轨
    
    参数：
        close:      收盘价序列
        high:       最高价序列
        low:        最低价序列
        ema_period: 中轨EMA周期
        atr_period: ATR周期
        atr_mult:   ATR倍数
    返回：
        middle: 中轨（EMA线）
        upper:  上轨
        lower:  下轨
    """
    # 中轨：EMA
    middle = ema(close, ema_period)

    # ATR波动率
    atr = calc_atr(high, low, close, atr_period)

    # 上下轨：中轨 ± ATR倍数 × ATR
    upper = middle + atr_mult * atr
    lower = middle - atr_mult * atr

    return middle, upper, lower


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[肯特纳通道策略] 启动，品种={SYMBOL}, EMA={EMA_PERIOD}, "
          f"ATR={ATR_PERIOD}×{ATR_MULT}")

    # 获取K线数据
    klines   = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)
    account  = api.get_account()

    # 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    try:
        while True:
            api.wait_update()

            # 在K线收盘时重新计算
            if api.is_changing(klines.iloc[-1], "datetime"):

                close = klines["close"]
                high  = klines["high"]
                low   = klines["low"]

                # ====== 计算肯特纳通道 ======
                middle, upper, lower = calc_keltner_channel(
                    close, high, low, EMA_PERIOD, ATR_PERIOD, ATR_MULT
                )

                # 取最新两根K线的值
                close_now  = close.iloc[-1]
                close_prev = close.iloc[-2]
                upper_now  = upper.iloc[-1]
                upper_prev = upper.iloc[-2]
                lower_now  = lower.iloc[-1]
                lower_prev = lower.iloc[-2]
                mid_now    = middle.iloc[-1]

                # ====== 检测突破信号 ======
                # 上穿上轨：前一根收盘≤上轨，当前收盘>上轨
                breakout_up   = (close_prev <= upper_prev) and (close_now > upper_now)
                # 下穿下轨：前一根收盘≥下轨，当前收盘<下轨
                breakout_down = (close_prev >= lower_prev) and (close_now < lower_now)

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"Close={close_now:.2f}, Upper={upper_now:.2f}, "
                      f"Mid={mid_now:.2f}, Lower={lower_now:.2f}")

                # ====== 交易逻辑 ======

                # --- 突破上轨做多 ---
                if breakout_up:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 开多仓 {VOLUME}手（突破上轨={upper_now:.2f}）")

                # --- 突破下轨做空 ---
                elif breakout_down:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 开空仓 {VOLUME}手（跌破下轨={lower_now:.2f}）")

                # --- 多仓止盈：价格跌回中轨以下 ---
                elif close_now < mid_now:
                    target_pos.set_target_volume(0)
                    print(f"  → 多仓止盈平仓（Close={close_now:.2f}跌破中轨={mid_now:.2f}）")

                # --- 空仓止盈：价格涨回中轨以上 ---
                elif close_now > mid_now:
                    target_pos.set_target_volume(0)
                    print(f"  → 空仓止盈平仓（Close={close_now:.2f}上穿中轨={mid_now:.2f}）")

    finally:
        api.close()
        print("[肯特纳通道策略] 已退出")


if __name__ == "__main__":
    main()
