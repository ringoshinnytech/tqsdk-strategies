"""
================================================================================
策略名称：ATR动态止损策略（均线趋势入场 + ATR追踪止损出场）
================================================================================

【策略背景与来源】
ATR（Average True Range，平均真实波幅）由著名技术分析大师 Welles Wilder 在其1978年
的著作《技术交易系统中的新概念》（New Concepts in Technical Trading Systems）中提出。
ATR并非价格方向性指标，而是纯粹度量价格波动幅度的工具，被广泛应用于止损设置、仓位管理、
突破确认等场景。

ATR追踪止损（ATR Trailing Stop）策略是将ATR与趋势判断相结合的经典策略体系：
用均线（MA）判断趋势方向决定入场，用ATR动态调整止损位置随价格移动，
在保护利润的同时给予价格足够的呼吸空间，避免被正常波动震出仓位。

该策略思想被融入了许多著名的量化策略中，如 Chandelier Exit（吊灯出场法）、
SuperTrend 指标等，是专业期货交易员最常用的止损方法之一。

【核心逻辑】
策略分为两部分：
1. 趋势判断（入场信号）：
   - 使用两条不同周期的均线（MA_FAST 和 MA_SLOW）
   - 快线在慢线之上：多头趋势，寻找做多机会
   - 快线在慢线之下：空头趋势，寻找做空机会
   - 均线金叉时开多仓，死叉时开空仓

2. 动态止损（出场信号）：
   - ATR止损线（多仓）= 当前价格 - ATR_MULTIPLIER × ATR(N)
   - ATR止损线（空仓）= 当前价格 + ATR_MULTIPLIER × ATR(N)
   - 止损线只能向有利方向移动（追踪止损的核心特征）
   - 当价格触及止损线时平仓

【计算公式】
True Range（真实波幅）：
    TR = MAX(High-Low, |High-PrevClose|, |Low-PrevClose|)

ATR（N期平均真实波幅）：
    ATR(N) = EMA(TR, N) 或 SMA(TR, N)

多仓追踪止损线（只能上移，不能下移）：
    Long_Stop = Close - ATR_MULT × ATR(N)
    Long_Stop_Final = MAX(Long_Stop, Long_Stop_prev) # 取当前与前值最大，确保只上移

空仓追踪止损线（只能下移，不能上移）：
    Short_Stop = Close + ATR_MULT × ATR(N)
    Short_Stop_Final = MIN(Short_Stop, Short_Stop_prev) # 取当前与前值最小，确保只下移

【交易信号说明】
- 开多：MA_FAST 上穿 MA_SLOW（金叉），按当前卖一价开多
- 开空：MA_FAST 下穿 MA_SLOW（死叉），按当前买一价开空
- 平多：持多仓且最新价格 < 追踪止损线（止损触发）
- 平空：持空仓且最新价格 > 追踪止损线（止损触发）
- 反手：信号反转时，先平旧仓，再开新仓

【适用品种和周期】
适用品种：波动性较大的趋势性品种，如原油（SC）、黄金（AU）、铜（CU）、橡胶（RU）
适用周期：15分钟至日线
ATR倍数参考：日线行情建议ATR×2-3，分钟线建议ATR×1.5-2.5

【优缺点分析】
优点：
1. 止损距离随市场波动自动调整，不会在高波动期设置过紧止损
2. 追踪止损可自动锁定利润，避免盈利回吐过多
3. 结合趋势判断，只在有利方向交易，提高胜率
4. ATR客观反映市场状态，无主观成分

缺点：
1. 趋势判断有滞后性，入场点不够理想
2. 强趋势行情中止损可能较宽，单次亏损较大
3. 震荡市场中均线频繁交叉，信号质量差
4. ATR倍数设置对结果影响很大，需要仔细调参

【参数说明】
- SYMBOL：交易合约，默认 SHFE.au2506（黄金）
- MA_FAST：快速均线周期，默认10
- MA_SLOW：慢速均线周期，默认30
- ATR_N：ATR计算周期，默认14
- ATR_MULTIPLIER：ATR倍数（止损距离 = ATR × 倍数），默认2.0
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期（秒），默认3600（1小时）
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma, ema, crossup, crossdown
import pandas as pd
import numpy as np

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "SHFE.au2506"          # 交易合约：黄金2506合约
MA_FAST = 10                     # 快速均线周期
MA_SLOW = 30                     # 慢速均线周期
ATR_N = 14                       # ATR计算周期
ATR_MULTIPLIER = 2.0             # ATR倍数（止损距离 = ATR × 该倍数）
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 3600            # K线周期：3600秒 = 1小时
DATA_LENGTH = 300                # 获取K线数量

# ============================================================
# 初始化 TqApi
# ============================================================
api = TqApi(
    account=TqSim(),
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")
)

# 订阅K线数据
klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)

# 订阅实时报价（用于ATR止损追踪需实时最新价）
quote = api.get_quote(SYMBOL)

print(f"[ATR止损策略] 启动成功，交易品种：{SYMBOL}")
print(f"[ATR止损策略] 参数：MA快线={MA_FAST}，MA慢线={MA_SLOW}，ATR周期={ATR_N}，ATR倍数={ATR_MULTIPLIER}")

# 追踪止损线状态（程序运行期间保持状态）
long_stop_price = 0.0    # 当前多仓追踪止损价格（只增不减）
short_stop_price = float('inf')  # 当前空仓追踪止损价格（只减不增）


def calc_atr(klines, n=14):
    """
    计算ATR（平均真实波幅）

    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    ATR = EMA(TR, N)

    参数：
        klines: K线数据DataFrame
        n: ATR计算周期

    返回：
        ATR pandas Series
    """
    high = klines["high"]
    low = klines["low"]
    close = klines["close"]

    # 计算前一收盘价（shift(1)向后移动1位）
    prev_close = close.shift(1)

    # 真实波幅TR = max(当前高低价差, 当前高与前收盘差, 当前低与前收盘差)
    tr1 = high - low                          # 当日高低价差
    tr2 = (high - prev_close).abs()           # 当日最高与前收盘差的绝对值
    tr3 = (low - prev_close).abs()            # 当日最低与前收盘差的绝对值

    # 取三者最大值作为TR
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 用EMA平滑TR得到ATR
    atr = ema(tr, n)

    return atr


# ============================================================
# 主循环：K线更新处理信号，实时行情处理止损
# ============================================================
try:
    while True:
        api.wait_update()  # 等待数据更新

        # ---- 实时止损检查（每次行情更新都检查，不只在K线完成时）----
        if api.is_changing(quote):
            position = api.get_position(SYMBOL)
            current_price = quote.last_price  # 当前最新成交价

            # 检查多仓止损（价格跌破追踪止损线）
            if position.volume_long > 0 and long_stop_price > 0:
                if current_price < long_stop_price:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=position.volume_long,
                        limit_price=quote.bid_price1  # 市价平仓
                    )
                    long_stop_price = 0.0  # 重置止损价
                    print(f"[ATR止损策略] 多仓止损触发：价格={current_price:.2f}，止损线={long_stop_price:.2f}")

            # 检查空仓止损（价格涨破追踪止损线）
            if position.volume_short > 0 and short_stop_price < float('inf'):
                if current_price > short_stop_price:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=position.volume_short,
                        limit_price=quote.ask_price1  # 市价平仓
                    )
                    short_stop_price = float('inf')  # 重置止损价
                    print(f"[ATR止损策略] 空仓止损触发：价格={current_price:.2f}，止损线={short_stop_price:.2f}")

        # ---- K线更新：计算指标并更新追踪止损线 ----
        if api.is_changing(klines):

            # 计算均线
            close = klines["close"]
            ma_fast = ma(close, MA_FAST)    # 快速均线
            ma_slow = ma(close, MA_SLOW)    # 慢速均线

            # 计算ATR
            atr = calc_atr(klines, n=ATR_N)

            # 取最新完成K线的数据（-2为最近完成K线）
            close_cur = close.iloc[-2]
            atr_cur = atr.iloc[-2]
            ma_fast_cur = ma_fast.iloc[-2]
            ma_slow_cur = ma_slow.iloc[-2]

            # 检测均线金叉/死叉
            is_golden = bool(crossup(ma_fast, ma_slow).iloc[-2])   # 金叉：快线上穿慢线
            is_death = bool(crossdown(ma_fast, ma_slow).iloc[-2])  # 死叉：快线下穿慢线

            # 计算当前ATR止损距离
            atr_stop_dist = ATR_MULTIPLIER * atr_cur  # 止损距离 = ATR倍数 × ATR值

            # ---- 更新追踪止损线（仅在持仓时更新）----
            position = api.get_position(SYMBOL)

            if position.volume_long > 0:
                # 多仓追踪止损线 = 收盘价 - ATR止损距离
                new_long_stop = close_cur - atr_stop_dist
                # 止损线只能上移（保护已有利润），取当前计算值与历史止损线的较大值
                long_stop_price = max(long_stop_price, new_long_stop)
                print(
                    f"[ATR止损策略] 多仓止损线更新：{long_stop_price:.2f}"
                    f"（ATR={atr_cur:.2f}，距离={atr_stop_dist:.2f}）"
                )

            if position.volume_short > 0:
                # 空仓追踪止损线 = 收盘价 + ATR止损距离
                new_short_stop = close_cur + atr_stop_dist
                # 止损线只能下移，取当前计算值与历史止损线的较小值
                short_stop_price = min(short_stop_price, new_short_stop)
                print(
                    f"[ATR止损策略] 空仓止损线更新：{short_stop_price:.2f}"
                    f"（ATR={atr_cur:.2f}，距离={atr_stop_dist:.2f}）"
                )

            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"MA快={ma_fast_cur:.2f}，MA慢={ma_slow_cur:.2f}，"
                f"ATR={atr_cur:.2f}，金叉={is_golden}，死叉={is_death}"
            )

            # ---- 开仓逻辑 ----

            # 【金叉开多】快线上穿慢线，趋势转多，开多仓
            if is_golden:
                if position.volume_short > 0:
                    # 先平空仓（反手）
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=position.volume_short,
                        limit_price=quote.ask_price1
                    )
                    short_stop_price = float('inf')  # 重置空仓止损价
                    print(f"[ATR止损策略] 金叉平空：{position.volume_short}手")

                if position.volume_long == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.ask_price1
                    )
                    # 初始化追踪止损线
                    long_stop_price = close_cur - atr_stop_dist
                    print(f"[ATR止损策略] 金叉开多：{VOLUME}手，初始止损={long_stop_price:.2f}")

            # 【死叉开空】快线下穿慢线，趋势转空，开空仓
            elif is_death:
                if position.volume_long > 0:
                    # 先平多仓（反手）
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=position.volume_long,
                        limit_price=quote.bid_price1
                    )
                    long_stop_price = 0.0  # 重置多仓止损价
                    print(f"[ATR止损策略] 死叉平多：{position.volume_long}手")

                if position.volume_short == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.bid_price1
                    )
                    # 初始化追踪止损线
                    short_stop_price = close_cur + atr_stop_dist
                    print(f"[ATR止损策略] 死叉开空：{VOLUME}手，初始止损={short_stop_price:.2f}")

except KeyboardInterrupt:
    print("[ATR止损策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[ATR止损策略] API连接已关闭")
