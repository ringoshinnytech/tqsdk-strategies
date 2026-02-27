"""
================================================================================
策略20：Hull移动平均线策略（Hull Moving Average Strategy）
================================================================================

【策略背景与来源】
Hull移动平均线（HMA，Hull Moving Average）由澳大利亚著名交易员Alan Hull于2005年
发明，并发表在其文章《Better Moving Average》中。Alan Hull的核心目标是：既减少
传统均线的滞后性（Lag），又保持均线的平滑性，避免出现过多噪音信号。

传统SMA/EMA都存在滞后问题：SMA权重均等导致滞后大，EMA虽有所改善但仍不理想。
WMA（加权移动平均）更注重最近的数据，滞后比SMA小，但平滑度较差。Alan Hull
通过一个巧妙的数学技巧，用两个不同周期的WMA差值再做平滑，从根本上减少了
均线的滞后，使均线几乎与价格同步运动，被认为是目前最好的趋势均线之一。

【核心逻辑】
Hull MA的核心思想：
1. 计算短期WMA（n/2周期）：WMA_half = WMA(close, n//2)
2. 计算长期WMA（n周期）：WMA_full = WMA(close, n)
3. 计算差值序列：Raw = 2 × WMA_half - WMA_full（这一步抵消了大部分滞后）
4. 对Raw做sqrt(n)周期WMA平滑：HMA = WMA(Raw, sqrt(n))

这个过程类似于"误差修正"——用2倍短期均线减去长期均线，得到的序列向前"超前"
了一段距离，再对其做平滑，结果是一条几乎无滞后的平滑均线。

交易策略：
- HMA斜率向上（当前HMA > 上一根HMA）→ 做多
- HMA斜率向下（当前HMA < 上一根HMA）→ 做空
- 可加入HMA斜率变化的交叉点作为更精确的入场信号

【计算公式】
设周期为n：
  WMA(series, period) = Σ(i × close[n-i]) / Σ(i)  其中i从1到period

  Step 1: WMA_half = WMA(close, floor(n/2))
  Step 2: WMA_full = WMA(close, n)
  Step 3: Raw      = 2 × WMA_half - WMA_full
  Step 4: HMA      = WMA(Raw, floor(sqrt(n)))

例：n=20
  WMA(close, 10) → WMA_half
  WMA(close, 20) → WMA_full
  Raw = 2 × WMA_half - WMA_full
  HMA = WMA(Raw, 4)   # floor(sqrt(20)) = 4

【交易信号说明】
做多信号：HMA斜率由负转正（HMA当前 > HMA上一根，且上上根时HMA曾 <= 上一根）
          简化：HMA当前 > HMA上一根（当前在上升中）
做空信号：HMA斜率由正转负（HMA当前 < HMA上一根）
平多仓：HMA开始下降时平仓（set_target_volume(0)）
平空仓：HMA开始上升时平仓（set_target_volume(0)）

进阶版：检测HMA斜率的二阶变化（拐点），即斜率从正到负或从负到正的精确时刻入场

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑，代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发

【适用品种和周期】
适用品种：几乎所有期货品种，趋势性强的品种效果更好（如原油SC、螺纹钢RB、铜CU）
适用周期：15分钟 ~ 日线（周期越长信号越稳定，日线信号质量最佳）
最佳场景：单边趋势行情，震荡市场仍会产生频繁的方向切换信号

【优缺点分析】
优点：
  1. 滞后极小，几乎与价格同步，是现有均线类指标中响应最快的之一
  2. 同时保持了较好的平滑度，减少了噪音干扰
  3. 计算原理优雅，不依赖复杂的统计模型
  4. 可替代所有场景中的SMA/EMA使用，直接升级版

缺点：
  1. 在震荡市场中，快速响应会导致频繁反转，产生"锯齿"形态
  2. 需要较多历史数据（至少n根K线）才能稳定
  3. WMA计算相对SMA/EMA更复杂，但现代计算机无性能问题
  4. 单独使用需要配合止损策略，否则在震荡期容易被连续止损

【参数说明】
SYMBOL        : 交易品种，默认螺纹钢 SHFE.rb2405
HMA_PERIOD    : Hull MA主周期，默认20根K线
KLINE_DURATION: K线周期（秒），默认900秒（15分钟）
VOLUME        : 每次下单手数，默认1手
DATA_LENGTH   : 历史K线数量，建议 > HMA_PERIOD × 3
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.rb2405"   # 交易品种：螺纹钢主力合约
HMA_PERIOD     = 20               # Hull MA计算周期
KLINE_DURATION = 15 * 60          # K线周期：15分钟（秒）
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 300              # 历史K线数量


def calc_wma(series, period):
    """
    计算加权移动平均线（WMA，Weighted Moving Average）
    
    WMA给予近期数据更高的权重，权重线性递增：
    最近1根权重=period，最近2根权重=period-1，...，最远1根权重=1
    
    参数：
        series: 价格序列（pandas Series）
        period: 计算周期
    返回：
        wma: WMA序列（pandas Series）
    """
    weights = np.arange(1, period + 1, dtype=float)  # 权重数组：[1, 2, ..., period]
    wma     = series.rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )
    return wma


def calc_hma(close, period):
    """
    计算Hull移动平均线（HMA）
    
    公式：HMA = WMA(2 × WMA(close, n/2) - WMA(close, n), sqrt(n))
    
    参数：
        close:  收盘价序列（pandas Series）
        period: HMA主周期
    返回：
        hma: HMA序列（pandas Series）
    """
    half_period = max(int(period // 2), 2)        # 半周期，至少为2
    sqrt_period = max(int(np.sqrt(period)), 2)     # 平方根周期，至少为2

    # 步骤1：计算半周期WMA
    wma_half = calc_wma(close, half_period)

    # 步骤2：计算全周期WMA
    wma_full = calc_wma(close, period)

    # 步骤3：计算差值（误差修正，减少滞后）
    raw = 2.0 * wma_half - wma_full

    # 步骤4：对差值序列做sqrt(n)周期WMA平滑
    hma = calc_wma(raw, sqrt_period)

    return hma


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[Hull MA策略] 启动，品种={SYMBOL}, HMA周期={HMA_PERIOD}, "
          f"K线={KLINE_DURATION//60}分钟")

    # 获取K线数据
    klines   = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)
    account  = api.get_account()

    # 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    try:
        while True:
            api.wait_update()

            # 仅在K线收盘时更新（检测K线时间戳变化）
            if api.is_changing(klines.iloc[-1], "datetime"):

                close = klines["close"]   # 收盘价序列

                # ====== 计算Hull移动平均线 ======
                hma = calc_hma(close, HMA_PERIOD)

                # 取最新几根K线的HMA值
                hma_now  = hma.iloc[-1]   # 当前HMA
                hma_prev = hma.iloc[-2]   # 上一根HMA
                hma_pp   = hma.iloc[-3]   # 上上根HMA（用于判断斜率拐点）

                # 当前HMA方向（向上=True，向下=False）
                hma_rising      = hma_now > hma_prev    # 当前HMA在上升
                hma_was_falling = hma_prev < hma_pp     # 上一根HMA在下降（已反转到上升）

                # HMA斜率刚由负变正（拐点）→ 做多信号
                signal_long  = hma_rising and hma_was_falling

                # HMA斜率刚由正变负（拐点）→ 做空信号
                signal_short = (not hma_rising) and (hma_prev > hma_pp)

                curr_close = close.iloc[-1]

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"Close={curr_close:.2f}, HMA={hma_now:.2f}, "
                      f"方向={'↑上升' if hma_rising else '↓下降'}")

                # ====== 交易逻辑 ======

                # --- 做多信号：HMA斜率由负转正（上升拐点） ---
                if signal_long:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 开多仓 {VOLUME}手（HMA斜率拐点：{hma_prev:.2f}→{hma_now:.2f}↑）")

                # --- 做空信号：HMA斜率由正转负（下降拐点） ---
                elif signal_short:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 开空仓 {VOLUME}手（HMA斜率拐点：{hma_prev:.2f}→{hma_now:.2f}↓）")

                # --- 趋势跟随止损：若HMA方向与持仓方向相反，平仓 ---
                elif not hma_rising:
                    # HMA在下降，不支持多头
                    target_pos.set_target_volume(0)
                    print(f"  → 平多仓（HMA持续下降，止损）")

                elif hma_rising:
                    # HMA在上升，不支持空头
                    target_pos.set_target_volume(0)
                    print(f"  → 平空仓（HMA持续上升，止损）")

    finally:
        api.close()
        print("[Hull MA策略] 已退出")


if __name__ == "__main__":
    main()
