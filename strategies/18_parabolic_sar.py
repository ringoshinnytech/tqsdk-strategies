"""
================================================================================
策略18：抛物线转向策略（Parabolic SAR Strategy）
================================================================================

【策略背景与来源】
抛物线SAR（Stop And Reverse，停止并转向）由技术分析大师J. Welles Wilder Jr.于
1978年在其著作《New Concepts in Technical Trading Systems》中提出，与RSI、ATR、
ADX等经典指标同出一书。SAR是一种跟踪型止损指标，其核心理念是"让利润奔跑，严格
止损"。SAR点位始终跟随价格运行，在上涨趋势中位于价格下方作为保护性止损，在下跌
趋势中位于价格上方作为参考压力线。当价格穿越SAR点位时，系统自动反转仓位方向。
这种机制使得策略永远保持有仓状态（多仓或空仓之一），是典型的趋势跟踪策略。

【核心逻辑】
SAR计算基于两个概念：
1. 极值点（EP，Extreme Point）：在上涨趋势中为最近的最高价，下跌趋势中为最近的最低价
2. 加速因子（AF，Acceleration Factor）：初始值为初始AF，每当创出新高/新低时增加step，
   最大不超过max_af

上涨趋势中：
  SAR(t) = SAR(t-1) + AF × (EP - SAR(t-1))
  如果价格下穿SAR，趋势反转，切换为下跌模式

下跌趋势中：
  SAR(t) = SAR(t-1) + AF × (EP - SAR(t-1))
  如果价格上穿SAR，趋势反转，切换为上涨模式

SAR随着趋势延续而加速收紧，形成"抛物线"形状，因此得名。

【计算公式】
初始化：
  初始AF = 0.02（initial_af）
  AF增量 = 0.02（step）
  最大AF = 0.20（max_af）

上涨趋势更新：
  EP = max(EP, 当前最高价)         # 更新极值点
  AF = min(AF + step, max_af)      # 若创新高则AF增加
  SAR = SAR + AF × (EP - SAR)      # 抛物线加速靠近

下跌趋势更新：
  EP = min(EP, 当前最低价)
  AF = min(AF + step, max_af)
  SAR = SAR + AF × (EP - SAR)

约束条件（确保SAR的合理性）：
  上涨趋势中：SAR不能高于前两根K线的最低价
  下跌趋势中：SAR不能低于前两根K线的最高价

【交易信号说明】
做多信号：价格由下方上穿SAR（即价格 > SAR 且 前一根 价格 < 前一根 SAR）
做空信号：价格由上方下穿SAR（即价格 < SAR 且 前一根 价格 > 前一根 SAR）
平仓逻辑：发生反转时，先平对方向的仓位，再开新仓（止损并反向）

【适用品种和周期】
适用品种：趋势性强的品种，如原油SC、螺纹钢RB、铜CU、玉米C
适用周期：15分钟、30分钟、日线（趋势周期，越短则噪音越多）
不适合：震荡型市场（SAR会频繁反转，导致连续亏损）

【优缺点分析】
优点：
  1. 提供明确的止损跟踪线，风险管理直观
  2. 在趋势市场中持仓时间长，能充分捕获趋势利润
  3. 自适应性强，AF加速因子使SAR在强趋势中加速收紧
  4. 信号明确，价格穿越SAR即为明确的交易信号

缺点：
  1. 在震荡市场中频繁止损反转，导致大量连续亏损
  2. 初始参数（init_af, step, max_af）对策略表现影响很大
  3. 永远持有仓位（多或空），不支持空仓等待
  4. 趋势初期SAR收紧较慢，进场时机相对滞后

【参数说明】
SYMBOL        : 交易品种，默认原油期货 INE.sc2405
INIT_AF       : 加速因子初始值，默认0.02
STEP          : 加速因子每次增加量，默认0.02
MAX_AF        : 加速因子最大值，默认0.20
KLINE_DURATION: K线周期（秒），默认900秒（15分钟）
VOLUME        : 每次下单手数，默认1手
DATA_LENGTH   : 历史K线数量，建议 > 100
================================================================================
"""

import numpy as np
import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.rb2405"   # 交易品种：螺纹钢主力合约（原油可改为INE.sc2406）
INIT_AF        = 0.02             # 加速因子初始值（Wilder原始建议值）
STEP           = 0.02             # 加速因子每次增加量
MAX_AF         = 0.20             # 加速因子最大值（Wilder原始建议值）
KLINE_DURATION = 15 * 60          # K线周期：15分钟（秒）
VOLUME         = 1                # 每次交易手数
DATA_LENGTH    = 300              # 历史K线数量


def calc_parabolic_sar(high, low, close, init_af=0.02, step=0.02, max_af=0.20):
    """
    计算抛物线SAR（Parabolic SAR）
    
    参数：
        high:    最高价序列（pandas Series）
        low:     最低价序列（pandas Series）
        close:   收盘价序列（pandas Series）
        init_af: 加速因子初始值
        step:    加速因子步长
        max_af:  加速因子上限
    
    返回：
        sar:    SAR值序列（numpy array）
        trend:  趋势方向序列（1=上涨，-1=下跌）
    """
    n     = len(close)
    sar   = np.zeros(n)      # SAR数组
    trend = np.zeros(n)      # 趋势方向：1=上涨，-1=下跌

    high_arr  = high.values
    low_arr   = low.values
    close_arr = close.values

    # ====== 初始化第一根K线 ======
    # 简单起见，用收盘价趋势决定初始方向
    if close_arr[1] > close_arr[0]:
        trend[0] = 1           # 初始为上涨趋势
        sar[0]   = low_arr[0]  # SAR从最低价开始
        ep       = high_arr[0] # 极值点为最高价
    else:
        trend[0] = -1          # 初始为下跌趋势
        sar[0]   = high_arr[0] # SAR从最高价开始
        ep       = low_arr[0]  # 极值点为最低价

    af = init_af  # 初始加速因子

    for i in range(1, n):
        prev_trend = trend[i - 1]   # 上一根K线的趋势方向
        prev_sar   = sar[i - 1]     # 上一根K线的SAR值

        if prev_trend == 1:
            # ====== 上涨趋势 ======
            # 计算新SAR
            new_sar = prev_sar + af * (ep - prev_sar)

            # 约束：SAR不能高于前两根K线的最低价
            if i >= 2:
                new_sar = min(new_sar, low_arr[i - 1], low_arr[i - 2])
            else:
                new_sar = min(new_sar, low_arr[i - 1])

            if low_arr[i] < new_sar:
                # ====== 趋势反转：上涨→下跌 ======
                trend[i] = -1
                sar[i]   = ep          # SAR反转为之前的极高值
                ep       = low_arr[i]  # 新极值点为当前最低价
                af       = init_af     # 加速因子重置
            else:
                # 上涨趋势继续
                trend[i] = 1
                sar[i]   = new_sar

                # 更新极值点和加速因子
                if high_arr[i] > ep:
                    ep = high_arr[i]           # 创新高，更新极值点
                    af = min(af + step, max_af) # 加速因子增加

        else:
            # ====== 下跌趋势 ======
            # 计算新SAR
            new_sar = prev_sar + af * (ep - prev_sar)

            # 约束：SAR不能低于前两根K线的最高价
            if i >= 2:
                new_sar = max(new_sar, high_arr[i - 1], high_arr[i - 2])
            else:
                new_sar = max(new_sar, high_arr[i - 1])

            if high_arr[i] > new_sar:
                # ====== 趋势反转：下跌→上涨 ======
                trend[i] = 1
                sar[i]   = ep           # SAR反转为之前的极低值
                ep       = high_arr[i]  # 新极值点为当前最高价
                af       = init_af      # 加速因子重置
            else:
                # 下跌趋势继续
                trend[i] = -1
                sar[i]   = new_sar

                # 更新极值点和加速因子
                if low_arr[i] < ep:
                    ep = low_arr[i]            # 创新低，更新极值点
                    af = min(af + step, max_af) # 加速因子增加

    return sar, trend


def main():
    # 初始化API，使用模拟账户
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[抛物线SAR策略] 启动，品种={SYMBOL}, AF_init={INIT_AF}, step={STEP}, max={MAX_AF}")

    # 获取K线数据
    klines   = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)
    account  = api.get_account()
    position = api.get_position(SYMBOL)

    # 记录上一根K线的SAR方向，用于检测反转
    last_trend = None

    try:
        while True:
            api.wait_update()

            # 仅在K线收盘更新时处理（K线时间戳变化代表新K线）
            if api.is_changing(klines.iloc[-1], "datetime"):

                high  = klines["high"]
                low   = klines["low"]
                close = klines["close"]

                # ====== 计算抛物线SAR ======
                sar, trend = calc_parabolic_sar(high, low, close, INIT_AF, STEP, MAX_AF)

                # 取最新K线的值
                curr_sar   = sar[-1]         # 当前SAR值
                curr_trend = trend[-1]       # 当前趋势（1=多，-1=空）
                prev_trend = trend[-2]       # 上一根K线趋势

                curr_close = close.iloc[-1]  # 当前收盘价

                # ====== 读取持仓状态 ======
                pos_long  = position.volume_long
                pos_short = position.volume_short

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"Close={curr_close:.2f}, SAR={curr_sar:.2f}, "
                      f"趋势={'↑多' if curr_trend == 1 else '↓空'}, "
                      f"多仓={pos_long}, 空仓={pos_short}")

                # ====== 检测趋势反转 ======
                # 从下跌反转为上涨（价格上穿SAR）→ 做多
                if curr_trend == 1 and prev_trend == -1:
                    print(f"  → SAR信号：上涨趋势（价格上穿SAR={curr_sar:.2f}）")

                    # 先平空仓
                    if pos_short > 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",
                            offset    = "CLOSE",
                            volume    = pos_short
                        )
                        print(f"  → 平空仓 {pos_short}手")

                    # 开多仓
                    if pos_long == 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",
                            offset    = "OPEN",
                            volume    = VOLUME
                        )
                        print(f"  → 开多仓 {VOLUME}手（SAR反转做多）")

                # 从上涨反转为下跌（价格下穿SAR）→ 做空
                elif curr_trend == -1 and prev_trend == 1:
                    print(f"  → SAR信号：下跌趋势（价格下穿SAR={curr_sar:.2f}）")

                    # 先平多仓
                    if pos_long > 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",
                            offset    = "CLOSE",
                            volume    = pos_long
                        )
                        print(f"  → 平多仓 {pos_long}手")

                    # 开空仓
                    if pos_short == 0:
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",
                            offset    = "OPEN",
                            volume    = VOLUME
                        )
                        print(f"  → 开空仓 {VOLUME}手（SAR反转做空）")

    finally:
        api.close()
        print("[抛物线SAR策略] 已退出")


if __name__ == "__main__":
    main()
