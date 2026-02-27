"""
================================================================================
策略16：Aroon指标趋势策略（Aroon Trend Strategy）
================================================================================

【策略背景与来源】
Aroon指标由Tushar Chande于1995年发明，"Aroon"来自梵文，意为"黎明前的曙光"。
该指标专门设计用来判断趋势的强弱和方向，以及趋势是否正在形成或消退。与传统
动量指标不同，Aroon通过测量价格创出新高/新低以来经过的时间来衡量趋势强度，
是一种基于时间维度的趋势确认工具。Aroon指标在中短期趋势交易中被广泛应用，
尤其适合日内和短线期货交易。

【核心逻辑】
Aroon指标包含两条线：
- Aroon Up：衡量距离最近N周期最高点经过了多少周期
- Aroon Down：衡量距离最近N周期最低点经过了多少周期

当Aroon Up高于Aroon Down，说明上涨趋势较强；
当Aroon Down高于Aroon Up，说明下跌趋势较强；
当两线接近（如都在50附近），说明市场处于震荡整理阶段。

策略通过两线的交叉来捕捉趋势的转折点：
- Aroon Up从下方上穿Aroon Down → 趋势由空转多 → 做多信号
- Aroon Down从下方上穿Aroon Up → 趋势由多转空 → 做空信号

同时引入阈值过滤（如Aroon Up > 70 才确认强势上涨），避免在震荡市中频繁交易。

【计算公式】
设周期为N：
  Aroon Up   = ((N - 距最近N根K线最高点的周期数) / N) × 100
  Aroon Down = ((N - 距最近N根K线最低点的周期数) / N) × 100

例：N=25，最近25根K线最高价出现在3根前：
  Aroon Up = (25 - 3) / 25 × 100 = 88

取值范围：0 ~ 100
- Aroon Up = 100：当前K线刚创25周期新高
- Aroon Down = 100：当前K线刚创25周期新低
- Aroon Up = 0：25周期前就创过高点，此后再未刷新

【交易信号说明】
开多仓：Aroon Up 上穿 Aroon Down（crossup），且 Aroon Up > 阈值（默认70）
开空仓：Aroon Down 上穿 Aroon Up（crossup），且 Aroon Down > 阈值（默认70）
平多仓：Aroon Down 上穿 Aroon Up，即趋势反转
平空仓：Aroon Up 上穿 Aroon Down，即趋势反转

【适用品种和周期】
适用品种：趋势性较强的商品期货，如原油（SC）、铜（CU）、黄金（AU）、螺纹钢（RB）
适用周期：5分钟 ~ 30分钟 K线，Aroon周期参数建议14~25
不适合：震荡型品种（如菜粕）、波动极小的品种

【优缺点分析】
优点：
  1. 不依赖价格绝对值，纯时间维度衡量趋势
  2. 信号明确，交叉信号易于程序化实现
  3. 对趋势强弱有清晰的量化描述（0-100）
  4. 相比MA交叉，对趋势初期更灵敏

缺点：
  1. 在震荡市场频繁产生虚假信号
  2. 对周期参数较敏感，需要针对不同品种优化
  3. 本质仍为滞后指标，无法预测拐点
  4. 单独使用胜率有限，建议配合趋势过滤器使用

【参数说明】
SYMBOL        : 交易品种，默认螺纹钢主力合约 SHFE.rb2405
AROON_PERIOD  : Aroon计算周期，默认25根K线
AROON_THRESH  : Aroon强势阈值，超过该值才确认趋势，默认70
KLINE_DURATION: K线周期（秒），默认300秒（5分钟）
VOLUME        : 每次下单手数，默认1手
DATA_LENGTH   : 历史K线数量，建议 > AROON_PERIOD × 3
================================================================================
"""

import numpy as np
from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import crossup, crossdown

# ==================== 策略参数配置 ====================
SYMBOL         = "SHFE.rb2405"   # 交易品种：螺纹钢主力合约
AROON_PERIOD   = 25              # Aroon指标计算周期（根K线数）
AROON_THRESH   = 70              # 趋势确认阈值，Aroon需超过该值才入场
KLINE_DURATION = 5 * 60          # K线周期：5分钟（单位：秒）
VOLUME         = 1               # 每次交易手数
DATA_LENGTH    = 200             # 拉取历史K线数量

def calc_aroon(high_series, low_series, period):
    """
    手动计算Aroon Up和Aroon Down指标
    
    参数：
        high_series: 最高价序列（pandas Series）
        low_series:  最低价序列（pandas Series）
        period:      计算周期
    
    返回：
        aroon_up:   Aroon Up序列（numpy array）
        aroon_down: Aroon Down序列（numpy array）
    """
    n = len(high_series)
    aroon_up   = np.full(n, np.nan)   # 初始化Aroon Up数组
    aroon_down = np.full(n, np.nan)   # 初始化Aroon Down数组

    for i in range(period, n):
        # 取最近period+1根K线的区间（包含当前K线）
        high_window = high_series.iloc[i - period: i + 1].values
        low_window  = low_series.iloc[i - period: i + 1].values

        # 找到最高价所在位置（从右侧算距离）
        # argmax返回从左算的索引，period - argmax = 距当前K线的根数
        high_idx = np.argmax(high_window)   # 区间内最高价的位置（0-indexed）
        low_idx  = np.argmin(low_window)    # 区间内最低价的位置（0-indexed）

        # 距当前K线的周期数 = period - 该位置索引
        periods_since_high = period - high_idx
        periods_since_low  = period - low_idx

        # 计算Aroon值：(period - 距离) / period × 100
        aroon_up[i]   = (period - periods_since_high) / period * 100
        aroon_down[i] = (period - periods_since_low)  / period * 100

    return aroon_up, aroon_down


def main():
    # 初始化TqApi，使用模拟账户TqSim，需填入您的天勤账号密码
    api = TqApi(account=TqSim(), auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"))
    print(f"[Aroon趋势策略] 启动，品种={SYMBOL}, 周期={AROON_PERIOD}, 阈值={AROON_THRESH}")

    # 获取K线数据（返回pandas DataFrame）
    klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)

    # 获取账户与持仓信息
    account  = api.get_account()
    position = api.get_position(SYMBOL)

    try:
        while True:
            api.wait_update()  # 等待任意数据更新

            # 只在K线有新数据时重新计算指标（提升效率）
            if api.is_changing(klines.iloc[-1], "datetime"):

                # ====== 提取收盘、最高、最低价序列 ======
                close  = klines["close"]
                high   = klines["high"]
                low    = klines["low"]

                # ====== 计算Aroon Up 和 Aroon Down ======
                aroon_up, aroon_down = calc_aroon(high, low, AROON_PERIOD)

                # 转换为pandas Series以使用tafunc的crossup/crossdown
                import pandas as pd
                aroon_up_s   = pd.Series(aroon_up,   name="aroon_up")
                aroon_down_s = pd.Series(aroon_down, name="aroon_down")

                # ====== 计算交叉信号 ======
                # crossup(a, b) 返回Series：a从下方上穿b时为True
                cross_up_signal   = crossup(aroon_up_s,   aroon_down_s)  # Aroon Up 上穿 Aroon Down
                cross_down_signal = crossup(aroon_down_s, aroon_up_s)    # Aroon Down 上穿 Aroon Up

                # 取最新一根K线的值（iloc[-1]为最新，iloc[-2]为上一根）
                last_aroon_up      = aroon_up[-1]
                last_aroon_down    = aroon_down[-1]
                last_cross_up      = bool(cross_up_signal.iloc[-1])    # 是否刚发生Up上穿
                last_cross_down    = bool(cross_down_signal.iloc[-1])  # 是否刚发生Down上穿

                # ====== 读取当前持仓状态 ======
                pos_long  = position.volume_long   # 多仓持仓量
                pos_short = position.volume_short  # 空仓持仓量

                print(f"[{klines.iloc[-1]['datetime']}] "
                      f"AroonUp={last_aroon_up:.1f}, AroonDown={last_aroon_down:.1f}, "
                      f"多仓={pos_long}, 空仓={pos_short}")

                # ====== 交易逻辑 ======

                # --- 开多信号：Aroon Up 上穿 Aroon Down，且 Aroon Up 超过阈值 ---
                if last_cross_up and last_aroon_up > AROON_THRESH:
                    if pos_short > 0:
                        # 先平掉空仓
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",       # 买入
                            offset    = "CLOSE",     # 平仓
                            volume    = pos_short    # 平全部空仓
                        )
                        print(f"  → 平空仓 {pos_short}手")

                    if pos_long == 0:
                        # 开多仓
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "BUY",   # 买入方向
                            offset    = "OPEN",  # 开仓
                            volume    = VOLUME   # 手数
                        )
                        print(f"  → 开多仓 {VOLUME}手（Aroon Up={last_aroon_up:.1f} 上穿 AroonDown）")

                # --- 开空信号：Aroon Down 上穿 Aroon Up，且 Aroon Down 超过阈值 ---
                elif last_cross_down and last_aroon_down > AROON_THRESH:
                    if pos_long > 0:
                        # 先平掉多仓
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",   # 卖出
                            offset    = "CLOSE",  # 平仓
                            volume    = pos_long  # 平全部多仓
                        )
                        print(f"  → 平多仓 {pos_long}手")

                    if pos_short == 0:
                        # 开空仓
                        api.insert_order(
                            symbol    = SYMBOL,
                            direction = "SELL",  # 卖出方向
                            offset    = "OPEN",  # 开仓
                            volume    = VOLUME   # 手数
                        )
                        print(f"  → 开空仓 {VOLUME}手（Aroon Down={last_aroon_down:.1f} 上穿 AroonUp）")

    finally:
        api.close()
        print("[Aroon趋势策略] 已退出")


if __name__ == "__main__":
    main()
