"""
================================================================================
策略名称：KDJ随机指标策略（K、D、J线超买超卖）
================================================================================

【策略背景与来源】
KDJ指标（随机指标，Stochastic Oscillator）最早由 George C. Lane 在1950年代提出，
后经技术分析师改良，在K、D线基础上增加了J线（通过K、D线推算的超前信号线）。
KDJ指标综合考虑了价格的最高价、最低价和收盘价，能够反映价格的动量变化，特别适合
在趋势末期识别超买超卖区域，是期货市场中常用的反转和趋势跟踪工具之一。

该指标在A股市场（尤其是台湾、香港）和商品期货市场中均被广泛应用，由于其J线的超前
敏感性，在短中期交易中具有较好的实用价值。

【核心逻辑】
KDJ指标分三步计算：
第一步：计算RSV（Raw Stochastic Value，未成熟随机值）
RSV 衡量当前收盘价在最近N个周期高低价范围中的相对位置，取值 0-100。

第二步：用RSV迭代计算K值，K值对RSV进行平滑处理
K值采用指数平滑：当前K = (2/3) × 前K + (1/3) × 当前RSV

第三步：用K值迭代计算D值（比K值更平滑），D值是K的信号线
D值：当前D = (2/3) × 前D + (1/3) × 当前K

第四步：J线 = 3×K - 2×D，J线灵敏度最高，常用于超前判断

【计算公式】
RSV(N)  = (Close - LLV(Low, N)) / (HHV(High, N) - LLV(Low, N)) × 100
K       = EMA方式：K_prev × (2/3) + RSV × (1/3)，初始值=50
D       = EMA方式：D_prev × (2/3) + K × (1/3)，初始值=50
J       = 3 × K - 2 × D

【交易信号说明】
超买超卖策略：
- KDJ进入超卖区（K<20, D<20, J<0），等待J线从低位上穿K线或D线，做多反弹
- KDJ进入超买区（K>80, D>80, J>100），等待J线从高位下穿K线或D线，做空回落

金叉死叉策略（本策略采用）：
- K线上穿D线（金叉）且处于低位（K<50），开多仓
- K线下穿D线（死叉）且处于高位（K>50），开空仓
- 止损：K进入超买区（>80）时平多；K进入超卖区（<20）时平空

【适用品种和周期】
适用品种：波动性适中的品种，如股指期货（IF/IC）、农产品期货（豆粕、棉花）
适用周期：5分钟至日线，日线效果最佳
不适用：单边趋势极强的行情（KDJ会长期保持超买/超卖而不回调）

【优缺点分析】
优点：
1. 能较好地识别超买超卖区域，适合震荡行情交易
2. J线超前敏感，能提前捕捉趋势反转信号
3. 指标值被限制在0-100区间，便于设置明确阈值
4. 结合价格形态使用效果更佳

缺点：
1. 在强趋势行情中，KDJ可能长期处于超买/超卖，导致过早平仓亏损
2. 参数（N=9）对不同品种适应性不同，需要调优
3. 单独使用容易产生假信号，建议配合趋势指标（如MA）过滤

【参数说明】
- SYMBOL：交易合约，默认 DCE.m2506（豆粕期货）
- KDJ_N：RSV计算周期，默认9（标准参数）
- KDJ_M1：K值平滑系数倒数，默认3（即平滑权重=1/3）
- KDJ_M2：D值平滑系数倒数，默认3
- OVERBUY：超买阈值，默认80（K、D值超过此值视为超买）
- OVERSELL：超卖阈值，默认20（K、D值低于此值视为超卖）
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期（秒），默认1800（30分钟）
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import hhv, llv, ma
import numpy as np

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "DCE.m2506"             # 交易合约：大商所豆粕2506合约
KDJ_N = 9                        # RSV计算周期（标准KDJ周期）
KDJ_M1 = 3                       # K值平滑参数（平滑权重 = 1/KDJ_M1）
KDJ_M2 = 3                       # D值平滑参数（平滑权重 = 1/KDJ_M2）
OVERBUY = 80                     # 超买阈值：K/D超过此值为超买区
OVERSELL = 20                    # 超卖阈值：K/D低于此值为超卖区
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 1800            # K线周期：1800秒 = 30分钟
DATA_LENGTH = 300                # 获取K线数量

# ============================================================
# 初始化 TqApi，使用模拟账户
# ============================================================
api = TqApi(
    account=TqSim(),                                    # 模拟账户
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")       # 替换为真实账号
)

# 订阅K线数据
klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)

# 订阅实时报价
quote = api.get_quote(SYMBOL)

print(f"[KDJ策略] 启动成功，交易品种：{SYMBOL}，K线周期：{KLINE_DURATION}秒")
print(f"[KDJ策略] 参数：N={KDJ_N}，超买={OVERBUY}，超卖={OVERSELL}")


def calc_kdj(klines, n=9, m1=3, m2=3):
    """
    手动计算KDJ指标
    
    由于tafunc没有直接提供KDJ函数，需要自行实现
    采用指数平滑迭代法计算K、D、J值
    
    参数：
        klines: K线数据DataFrame
        n: RSV计算周期
        m1: K值平滑参数
        m2: D值平滑参数
    
    返回：
        K, D, J 三个pandas Series
    """
    high = klines["high"]    # 最高价序列
    low = klines["low"]      # 最低价序列
    close = klines["close"]  # 收盘价序列

    # 计算N周期最高价和最低价
    hh = hhv(high, n)   # N周期最高价（rolling max）
    ll = llv(low, n)    # N周期最低价（rolling min）

    # 计算RSV（原始随机值），避免除以零
    denominator = hh - ll
    denominator = denominator.replace(0, 1)  # 分母为0时替换为1，防止除零错误
    rsv = (close - ll) / denominator * 100   # RSV值在0-100之间

    # 使用指数平滑迭代计算K值
    # K_n = (1 - 1/m1) * K_{n-1} + (1/m1) * RSV_n
    # 等价于：K_n = K_{n-1} * (2/3) + RSV_n * (1/3)（当m1=3时）
    k_values = []
    k_prev = 50.0  # K值初始值设为50（中性值）
    
    for rsv_val in rsv:
        if np.isnan(rsv_val):
            k_values.append(np.nan)
        else:
            k_cur = k_prev * (1 - 1.0/m1) + rsv_val * (1.0/m1)
            k_values.append(k_cur)
            k_prev = k_cur

    import pandas as pd
    k_series = pd.Series(k_values, index=close.index)

    # 使用指数平滑迭代计算D值
    # D_n = (1 - 1/m2) * D_{n-1} + (1/m2) * K_n
    d_values = []
    d_prev = 50.0  # D值初始值设为50
    
    for k_val in k_series:
        if np.isnan(k_val):
            d_values.append(np.nan)
        else:
            d_cur = d_prev * (1 - 1.0/m2) + k_val * (1.0/m2)
            d_values.append(d_cur)
            d_prev = d_cur

    d_series = pd.Series(d_values, index=close.index)

    # J线 = 3 * K - 2 * D（J线波动幅度大于K、D，超前性强）
    j_series = 3 * k_series - 2 * d_series

    return k_series, d_series, j_series


# ============================================================
# 主循环：等待K线更新并计算KDJ信号
# ============================================================
try:
    while True:
        api.wait_update()  # 阻塞等待行情更新

        # 仅在K线数据更新时处理
        if api.is_changing(klines):

            # ---- 计算KDJ指标 ----
            k, d, j = calc_kdj(klines, n=KDJ_N, m1=KDJ_M1, m2=KDJ_M2)

            # 取最近两根已完成的K线的KDJ值（-2为最近完成K线，-3为再前一根）
            k_cur = k.iloc[-2]     # 当前K值
            d_cur = d.iloc[-2]     # 当前D值
            j_cur = j.iloc[-2]     # 当前J值
            k_prev = k.iloc[-3]    # 前一K值（用于检测金叉死叉）
            d_prev = d.iloc[-3]    # 前一D值

            # 打印指标状态（调试用）
            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"K={k_cur:.2f}, D={d_cur:.2f}, J={j_cur:.2f}"
            )

            # ---- 检测金叉/死叉信号 ----
            # 金叉：前一K < 前一D，当前K > 当前D（K线从下穿越D线）
            golden_cross = (k_prev < d_prev) and (k_cur > d_cur)
            # 死叉：前一K > 前一D，当前K < 当前D（K线从上穿越D线）
            death_cross = (k_prev > d_prev) and (k_cur < d_cur)

            # ---- 查询当前持仓 ----
            position = api.get_position(SYMBOL)
            volume_long = position.volume_long    # 多仓手数
            volume_short = position.volume_short  # 空仓手数

            # ---- 执行交易逻辑 ----

            # 【开多条件】金叉信号 + KDJ处于中低位（K<50，避免追高）
            if golden_cross and k_cur < 50:
                # 如有空仓先平空
                if volume_short > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=volume_short,
                        limit_price=quote.ask_price1
                    )
                    print(f"[KDJ策略] 金叉平空：{volume_short}手")

                # 开多仓
                if volume_long == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.ask_price1
                    )
                    print(f"[KDJ策略] 金叉开多：{VOLUME}手，K={k_cur:.2f}")

            # 【开空条件】死叉信号 + KDJ处于中高位（K>50，避免追空低位）
            elif death_cross and k_cur > 50:
                # 如有多仓先平多
                if volume_long > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=volume_long,
                        limit_price=quote.bid_price1
                    )
                    print(f"[KDJ策略] 死叉平多：{volume_long}手")

                # 开空仓
                if volume_short == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.bid_price1
                    )
                    print(f"[KDJ策略] 死叉开空：{VOLUME}手，K={k_cur:.2f}")

            # 【止损：超买区平多仓】K进入超买区（>80），趋势可能反转，平多仓保护利润
            if volume_long > 0 and k_cur > OVERBUY:
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",
                    offset="CLOSE",
                    volume=volume_long,
                    limit_price=quote.bid_price1
                )
                print(f"[KDJ策略] 超买止盈平多：K={k_cur:.2f}>{OVERBUY}")

            # 【止损：超卖区平空仓】K进入超卖区（<20），趋势可能反转，平空仓保护利润
            if volume_short > 0 and k_cur < OVERSELL:
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",
                    offset="CLOSE",
                    volume=volume_short,
                    limit_price=quote.ask_price1
                )
                print(f"[KDJ策略] 超卖止盈平空：K={k_cur:.2f}<{OVERSELL}")

except KeyboardInterrupt:
    print("[KDJ策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[KDJ策略] API连接已关闭")
