"""
================================================================================
策略17：随机RSI策略（Stochastic RSI Strategy）
================================================================================

【策略背景与来源】
随机RSI（StochRSI）由Tushar Chande和Stanley Kroll于1994年在其著作《The New
Technical Trader》中提出。它将两个经典技术指标有机结合：RSI（相对强弱指数）
和Stochastic（随机指标KDJ的前身）。其核心思想是：RSI本身是一个价格的动量指标，
那么对RSI再做随机化处理，可以得到一个在[0,1]区间震荡的、更为灵敏的超买超卖信号。
StochRSI在加密货币、股指期货、商品期货的短线交易中极为流行，是量化交易者常用的
复合指标之一。

【核心逻辑】
第一步：计算RSI
  RSI基于N周期的涨跌幅来衡量价格的强弱，取值0-100。
  RSI > 70：超买区域；RSI < 30：超卖区域。

第二步：对RSI值再做随机化处理
  将最近M个RSI值视为一个时间序列，对其应用Stochastic公式，得到StochRSI。
  StochRSI = (当前RSI - 最近M周期RSI最低值) / (最近M周期RSI最高值 - RSI最低值)
  取值范围：0 ~ 1（或0~100）

第三步：对StochRSI做K、D平滑
  StochK = StochRSI的3周期移动平均（平滑随机值）
  StochD = StochK的3周期移动平均（信号线）

第四步：交叉信号
  K线从下方上穿D线（且在超卖区域附近）→ 做多
  K线从上方下穿D线（且在超买区域附近）→ 做空

StochRSI的优势在于它比RSI更加灵敏，能更早发现超买超卖状态，但也因此产生更多
噪音信号，实战中需要配合趋势过滤或价格确认。

【计算公式】
设RSI周期=N，StochRSI周期=M，平滑周期=3：

  RSI = 100 - 100 / (1 + RS)
  其中 RS = N周期平均涨幅 / N周期平均跌幅
  
  StochRSI_raw = (RSI - LLV(RSI, M)) / (HHV(RSI, M) - LLV(RSI, M))
  
  StochK = MA(StochRSI_raw, 3)    # 3周期简单平均
  StochD = MA(StochK, 3)          # 信号线

【交易信号说明】
开多信号：StochK 从下方上穿 StochD（crossup），且 StochK < 超卖线（默认0.2）
开空信号：StochK 从上方下穿 StochD（crossdown），且 StochK > 超买线（默认0.8）
平多信号：StochK 上穿 超买线（0.8），或StochK下穿StochD（反向交叉）
平空信号：StochK 下穿 超卖线（0.2），或StochK上穿StochD（反向交叉）

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑，代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发

【适用品种和周期】
适用品种：波动较活跃的期货，如黄金AU、白银AG、铜CU、原油SC、股指IF
适用周期：1分钟~15分钟K线（该指标适合短线反转交易）
注意：日线周期信号质量更高，但频率极低

【优缺点分析】
优点：
  1. 比RSI更灵敏，超买超卖状态持续时间更短，信号更早
  2. 结合了RSI的动量特性与随机指标的区间归一化特性
  3. K/D双线交叉减少了单线误判的概率
  4. 取值在[0,1]，阈值判断直观清晰

缺点：
  1. 信号频率高，虚假信号多，容易在趋势市场中逆势做单
  2. 对参数敏感，N和M的选择对结果影响较大
  3. 本质是二阶振荡器，在强趋势时会长期处于超买/超卖状态
  4. 计算复杂，需要足够多的历史数据（至少N+M+K+D个周期）

【参数说明】
SYMBOL        : 交易品种，默认黄金期货 SHFE.au2406
RSI_PERIOD    : RSI计算周期，默认14
STOCH_PERIOD  : 对RSI再做随机化处理的周期，默认14
SMOOTH_K      : StochK平滑周期，默认3
SMOOTH_D      : StochD平滑周期，默认3
OVERBOUGHT    : 超买阈值，默认0.8
OVERSOLD      : 超卖阈值，默认0.2
KLINE_DURATION: K线周期（秒），默认300秒（5分钟）
VOLUME        : 每次下单手数，默认1手
DATA_LENGTH   : 历史K线数量，建议 > (RSI_PERIOD + STOCH_PERIOD) × 3
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ma, crossup, crossdown

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.au2406"   # 交易品种：黄金主力合约
RSI_PERIOD     = 14               # RSI计算周期
STOCH_PERIOD   = 14               # 对RSI做随机化处理的周期
SMOOTH_K       = 3                # StochK平滑周期
SMOOTH_D       = 3                # StochD平滑周期（信号线）
OVERBOUGHT     = 0.8              # 超买阈值（0~1）
OVERSOLD       = 0.2              # 超卖阈值（0~1）
KLINE_DURATION = 5 * 60           # K线周期：5分钟（秒）
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 300              # 历史K线数量（需足够长）


def calc_rsi(close_series, period):
    """
    计算RSI相对强弱指数
    
    使用Wilder平滑方法（指数平均）
    
    参数：
        close_series: 收盘价序列（pandas Series）
        period: RSI周期
    返回：
        rsi: RSI值序列（pandas Series，取值0-100）
    """
    delta  = close_series.diff()                   # 计算每根K线的价格变化量
    gain   = delta.clip(lower=0)                   # 只保留上涨幅度（跌则为0）
    loss   = (-delta).clip(lower=0)                # 只保留下跌幅度（涨则为0）

    # 使用指数加权移动平均（Wilder方法，alpha=1/period）
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()

    rs  = avg_gain / (avg_loss + 1e-10)            # 避免除零
    rsi = 100 - (100 / (1 + rs))                   # RSI公式
    return rsi


def calc_stoch_rsi(rsi_series, stoch_period, smooth_k, smooth_d):
    """
    对RSI序列做随机化处理，计算StochRSI的K线和D线
    
    参数：
        rsi_series:   RSI值序列（pandas Series）
        stoch_period: 随机化处理周期（取RSI的最高/最低值的窗口）
        smooth_k:     K线平滑周期
        smooth_d:     D线平滑周期（信号线）
    返回：
        stoch_k: K线序列（pandas Series，取值0~1）
        stoch_d: D线序列（pandas Series，取值0~1）
    """
    # 滚动窗口内的RSI最高值和最低值
    rsi_max = rsi_series.rolling(window=stoch_period).max()
    rsi_min = rsi_series.rolling(window=stoch_period).min()

    # StochRSI原始值：归一化到[0,1]
    denom       = rsi_max - rsi_min
    stoch_raw   = (rsi_series - rsi_min) / (denom.replace(0, np.nan))  # 避免分母为0

    # 对StochRSI进行平滑得到K线
    stoch_k = stoch_raw.rolling(window=smooth_k).mean()

    # 对K线再平滑得到D线（信号线）
    stoch_d = stoch_k.rolling(window=smooth_d).mean()

    return stoch_k, stoch_d


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[随机RSI策略] 启动，品种={SYMBOL}, RSI周期={RSI_PERIOD}, Stoch周期={STOCH_PERIOD}")

    # 获取K线数据
    klines   = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)
    account  = api.get_account()

    # 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
    target_pos = TargetPosTask(api, SYMBOL)

    try:
        while True:
            api.wait_update()

            # 仅在K线更新时重新计算（提升运行效率）
            if api.is_changing(klines.iloc[-1], "datetime"):

                close = klines["close"]  # 提取收盘价序列

                # ====== 第一步：计算RSI ======
                rsi = calc_rsi(close, RSI_PERIOD)

                # ====== 第二步：对RSI做随机化处理，得到StochK和StochD ======
                stoch_k, stoch_d = calc_stoch_rsi(rsi, STOCH_PERIOD, SMOOTH_K, SMOOTH_D)

                # 取最新值用于信号判断
                k_now   = stoch_k.iloc[-1]   # 当前K值
                d_now   = stoch_d.iloc[-1]   # 当前D值
                rsi_now = rsi.iloc[-1]       # 当前RSI值

                # ====== 第三步：检测K/D交叉信号 ======
                cross_up_sig   = crossup(stoch_k, stoch_d)    # K上穿D（做多）
                cross_down_sig = crossdown(stoch_k, stoch_d)  # K下穿D（做空）

                last_cross_up   = bool(cross_up_sig.iloc[-1])   # 最新K线是否发生上穿
                last_cross_down = bool(cross_down_sig.iloc[-1]) # 最新K线是否发生下穿

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"RSI={rsi_now:.2f}, K={k_now:.3f}, D={d_now:.3f}")

                # ====== 交易逻辑 ======

                # --- 做多信号：K上穿D 且 K处于超卖区（< OVERSOLD） ---
                if last_cross_up and k_now < OVERSOLD:
                    target_pos.set_target_volume(VOLUME)
                    print(f"  → 开多仓 {VOLUME}手（StochK={k_now:.3f}上穿StochD，超卖反转）")

                # --- 做空信号：K下穿D 且 K处于超买区（> OVERBOUGHT） ---
                elif last_cross_down and k_now > OVERBOUGHT:
                    target_pos.set_target_volume(-VOLUME)
                    print(f"  → 开空仓 {VOLUME}手（StochK={k_now:.3f}下穿StochD，超买回落）")

                # --- 持仓期间的止损/平仓逻辑 ---
                # 多仓平仓：K值进入超买区（趋势可能反转）
                elif k_now > OVERBOUGHT:
                    target_pos.set_target_volume(0)
                    print(f"  → 多仓止盈平仓（K={k_now:.3f}进入超买区）")

                # 空仓平仓：K值进入超卖区（趋势可能反转）
                elif k_now < OVERSOLD:
                    target_pos.set_target_volume(0)
                    print(f"  → 空仓止盈平仓（K={k_now:.3f}进入超卖区）")

    finally:
        api.close()
        print("[随机RSI策略] 已退出")


if __name__ == "__main__":
    main()
