"""
================================================================================
策略名称：CCI顺势指标策略（突破±100做反向，突破±200做顺势）
================================================================================

【策略背景与来源】
CCI（Commodity Channel Index，商品通道指数）由 Donald Lambert 于1980年发表在
《商品》杂志上，最初专为商品期货设计，现已广泛应用于股票、外汇、期货等各类市场。
该指标衡量价格与其统计平均值的偏离程度，用于识别周期性转折点，既可用于趋势跟踪，
也可用于超买超卖判断，是少数同时具备双向功能的技术指标之一。

CCI的名字中"通道"指的是：价格在正常情况下约有70%-80%的时间落在 ±100 区间内，
突破这个区间被认为是异常行情的开始。

【核心逻辑】
本策略实现两种不同的CCI交易模式，根据突破程度做出不同方向的交易：

模式A：±100 突破反转（均值回归思路）
当CCI突破+100时，价格处于超买区，预期将回落，做空
当CCI突破-100时，价格处于超卖区，预期将反弹，做多
信号：CCI突破±100区间后回归，以回归信号入场

模式B：±200 突破顺势（动量趋势思路）
当CCI突破+200时，价格处于极度超买，动能强劲，顺势做多
当CCI突破-200时，价格处于极度超卖，动能强劲，顺势做空
信号：CCI突破±200极值区，顺势方向入场

【计算公式】
Typical Price（典型价格）：
    TP = (High + Low + Close) / 3

N周期TP均值：
    TP_MA = MA(TP, N)

N周期平均偏差（Mean Deviation）：
    MD = SUM(|TP_i - TP_MA|, N) / N

CCI值：
    CCI = (TP - TP_MA) / (0.015 × MD)

其中 0.015 是常数，用于将约70-80%的CCI值标准化到 ±100 区间内

【交易信号说明】
本策略采用模式B（±200顺势突破）为主要信号：
- CCI从下向上突破+200：强势多头动能，开多仓
- CCI从上向下跌破-200：强势空头动能，开空仓
- 平仓信号：CCI回到±100以内时平仓（动能衰减，止盈离场）
- 止损：持多仓时CCI跌破-100；持空仓时CCI突破+100

【适用品种和周期】
适用品种：趋势性和波动性较强的品种，如原油（SC）、铜（CU）、天然橡胶（RU）
适用周期：15分钟至日线，CCI在日线级别信号质量较高
不适用：流动性差的品种（计算结果不稳定）

【优缺点分析】
优点：
1. 同时具备趋势跟踪和均值回归两种功能，适应性强
2. 计算方法考虑了价格波动的统计特性
3. 对突破信号反应较为灵敏
4. 参数简单，调整容易

缺点：
1. 在震荡市场中，±200突破信号较少，可能长时间空仓
2. 均值回归模式在强趋势中容易止损
3. 指标本身不考虑成交量，缺少成交量验证
4. 极端行情下CCI可能长时间处于极值区

【参数说明】
- SYMBOL：交易合约，默认 SHFE.ru2506（天然橡胶）
- CCI_N：CCI计算周期，默认14（标准参数）
- LEVEL1：第一级阈值，默认±100（超买超卖临界）
- LEVEL2：第二级阈值，默认±200（极度超买超卖，顺势做方向）
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期（秒），默认3600（1小时）
- DATA_LENGTH：K线数量，默认200
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma
import pandas as pd
import numpy as np

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "SHFE.ru2506"          # 交易合约：沪胶（天然橡胶）2506合约
CCI_N = 14                       # CCI计算周期（常用14或20）
LEVEL1 = 100                     # 一级阈值：超买/超卖临界线
LEVEL2 = 200                     # 二级阈值：极度超买/超卖，顺势入场线
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 3600            # K线周期：3600秒 = 1小时
DATA_LENGTH = 200                # 获取K线数量（需大于CCI_N）

# ============================================================
# 初始化 TqApi
# ============================================================
api = TqApi(
    account=TqSim(),
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")
)

# 订阅K线数据
klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)

# 订阅实时报价
quote = api.get_quote(SYMBOL)

print(f"[CCI策略] 启动成功，交易品种：{SYMBOL}，K线周期：{KLINE_DURATION}秒")
print(f"[CCI策略] 参数：N={CCI_N}，一级阈值=±{LEVEL1}，二级阈值=±{LEVEL2}")


def calc_cci(klines, n=14):
    """
    计算CCI（商品通道指数）

    计算步骤：
    1. 典型价格 TP = (High + Low + Close) / 3
    2. TP的N期简单均线 TP_MA = MA(TP, N)
    3. N期平均偏差 MD = mean(|TP - TP_MA|)
    4. CCI = (TP - TP_MA) / (0.015 × MD)

    参数：
        klines: K线数据DataFrame
        n: CCI计算周期

    返回：
        CCI指标 pandas Series
    """
    high = klines["high"]    # 最高价
    low = klines["low"]      # 最低价
    close = klines["close"]  # 收盘价

    # 第一步：计算典型价格（Typical Price）
    tp = (high + low + close) / 3.0

    # 第二步：计算TP的N期简单移动均线
    tp_ma = ma(tp, n)

    # 第三步：计算N期平均偏差（Mean Deviation）
    # 使用rolling计算每个窗口内 |TP - TP_MA| 的均值
    md = tp.rolling(window=n).apply(
        lambda x: np.mean(np.abs(x - x.mean())),
        raw=True
    )

    # 第四步：计算CCI值，0.015是Lambert定义的常数
    # 避免除以零（当md为0时，价格没有波动，CCI设为0）
    cci = (tp - tp_ma) / (0.015 * md.replace(0, np.nan))
    cci = cci.fillna(0)  # 将NaN填充为0

    return cci


# ============================================================
# 主循环：等待K线更新并计算CCI信号
# ============================================================
try:
    while True:
        api.wait_update()  # 等待行情更新

        if api.is_changing(klines):

            # ---- 计算CCI指标 ----
            cci = calc_cci(klines, n=CCI_N)

            # 取最近两根完成K线的CCI值（-2为当前完成K，-3为前一完成K）
            cci_cur = cci.iloc[-2]   # 当前CCI值
            cci_prev = cci.iloc[-3]  # 前一CCI值（用于判断穿越方向）

            # 打印指标状态
            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"CCI={cci_cur:.2f}（前值={cci_prev:.2f}）"
            )

            # ---- 信号判断 ----
            # 【顺势突破+200】CCI从下方突破+200，极强多头动能，做多
            cross_up_200 = (cci_prev <= LEVEL2) and (cci_cur > LEVEL2)
            # 【顺势突破-200】CCI从上方跌破-200，极强空头动能，做空
            cross_down_200 = (cci_prev >= -LEVEL2) and (cci_cur < -LEVEL2)

            # 【平多信号】CCI从+200以上回落至+100以下，动能衰减，平多仓
            long_exit = (cci_prev >= LEVEL1) and (cci_cur < LEVEL1)
            # 【平空信号】CCI从-200以下回升至-100以上，动能衰减，平空仓
            short_exit = (cci_prev <= -LEVEL1) and (cci_cur > -LEVEL1)

            # ---- 查询当前持仓 ----
            position = api.get_position(SYMBOL)
            volume_long = position.volume_long    # 当前多仓数量
            volume_short = position.volume_short  # 当前空仓数量

            # ---- 执行平仓逻辑（优先平仓）----

            # CCI回落到+100以下，多仓止盈平仓
            if long_exit and volume_long > 0:
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",
                    offset="CLOSE",
                    volume=volume_long,
                    limit_price=quote.bid_price1
                )
                print(f"[CCI策略] CCI回落平多：CCI={cci_cur:.2f}，平多{volume_long}手")

            # CCI回升到-100以上，空仓止盈平仓
            if short_exit and volume_short > 0:
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",
                    offset="CLOSE",
                    volume=volume_short,
                    limit_price=quote.ask_price1
                )
                print(f"[CCI策略] CCI回升平空：CCI={cci_cur:.2f}，平空{volume_short}手")

            # ---- 执行开仓逻辑 ----

            # 【极强多头动能】CCI突破+200，顺势开多
            if cross_up_200:
                # 先平空仓（如有）
                if volume_short > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=volume_short,
                        limit_price=quote.ask_price1
                    )
                    print(f"[CCI策略] CCI突破+{LEVEL2}，先平空：{volume_short}手")

                # 开多仓
                if volume_long == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.ask_price1
                    )
                    print(f"[CCI策略] CCI突破+{LEVEL2}开多：CCI={cci_cur:.2f}，开多{VOLUME}手")

            # 【极强空头动能】CCI跌破-200，顺势开空
            if cross_down_200:
                # 先平多仓（如有）
                if volume_long > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=volume_long,
                        limit_price=quote.bid_price1
                    )
                    print(f"[CCI策略] CCI跌破-{LEVEL2}，先平多：{volume_long}手")

                # 开空仓
                if volume_short == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.bid_price1
                    )
                    print(f"[CCI策略] CCI跌破-{LEVEL2}开空：CCI={cci_cur:.2f}，开空{VOLUME}手")

except KeyboardInterrupt:
    print("[CCI策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[CCI策略] API连接已关闭")
