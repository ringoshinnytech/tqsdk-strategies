"""
================================================================================
策略名称：Z-Score均值回归策略（价格偏离均值N个标准差后回归）
================================================================================

【策略背景与来源】
均值回归（Mean Reversion）是金融市场中另一个被广泛研究和应用的价格行为规律，
与动量效应方向相反：价格在偏离长期均值后有回归均值的倾向。
该理论基于统计学中的均值回归（Regression to the Mean）概念，在金融市场中最早
被应用于配对交易（Pairs Trading）和统计套利领域，后被扩展到单一资产的短期交易。

Z-Score（标准分数）是衡量数据点偏离均值程度的统计量，以标准差为单位：
Z = (X - μ) / σ，表示X偏离均值μ有多少个标准差。
当Z-Score达到±2时，正态分布下该点处于95.5%置信区间之外，属于统计意义上的"异常偏离"。

Z-Score均值回归策略将这一统计工具应用于价格序列：
当价格Z-Score过高（偏离均值过多），做空，等待价格回归均值；
当价格Z-Score过低（偏离均值过多向下），做多，等待价格回归均值。

【核心逻辑】
1. 计算价格在过去N期内的均值（Mean）和标准差（Std）
2. 计算当前价格的Z-Score = (当前价格 - N期均值) / N期标准差
3. 当Z-Score > ENTRY_Z（如+2），价格统计意义上"过高"，做空
4. 当Z-Score < -ENTRY_Z（如-2），价格统计意义上"过低"，做多
5. 当Z-Score回归至EXIT_Z（如0.5）附近时，认为均值回归完成，平仓
6. 设置最大持仓期（MAX_HOLD_BARS），避免价格长时间不回归导致损失扩大

【计算公式】
N期均值：
    Mean(N) = SUM(Close, N) / N = MA(Close, N)

N期标准差：
    Std(N) = SQRT(SUM((Close_i - Mean)^2, N) / N)

Z-Score：
    Z = (Close - Mean(N)) / Std(N)

Bollinger Band 上轨（供参考）：
    Upper = Mean + ENTRY_Z × Std
Bollinger Band 下轨（供参考）：
    Lower = Mean - ENTRY_Z × Std

【交易信号说明】
- 开空：Z-Score > +ENTRY_Z（价格显著高于均值），做空等待回归
- 开多：Z-Score < -ENTRY_Z（价格显著低于均值），做多等待回归
- 平空：Z-Score 回落至 +EXIT_Z 以下（均值回归完成）
- 平多：Z-Score 回升至 -EXIT_Z 以上（均值回归完成）
- 超时平仓：持仓超过MAX_HOLD_BARS根K线强制平仓（控制风险）

【适用品种和周期】
适用品种：
- 均值回归特性强的品种：豆粕（M）、菜油（OI）、贵金属等
- 配对交易：同板块两个高度相关品种的价差（如 IF 和 IC）
不适用：
- 单边趋势明显的品种（价格持续偏离均值不回归）

适用周期：
- 日内：5分钟至30分钟，Z-Score回归速度快
- 日线：适合中期均值回归，但需要更大止损空间

【优缺点分析】
优点：
1. 有扎实的统计学理论支撑，信号具有客观性
2. 逆势做单，往往在较好的价位入场
3. Z-Score明确量化了偏离程度，阈值设置有参考依据
4. 可以很好地捕捉过度波动后的回归行情

缺点：
1. 在强趋势行情中，价格可能长期不回归，持续亏损
2. 均值和标准差的回望期N对结果影响极大
3. 假设价格服从正态分布，而现实中价格分布有肥尾特征
4. 需要配合趋势过滤，否则在趋势行情中损失惨重

【参数说明】
- SYMBOL：交易合约，默认 DCE.m2506（豆粕）
- ZSCORE_N：Z-Score计算回望周期，默认20（20根K线的均值和标准差）
- ENTRY_Z：开仓Z-Score阈值，默认2.0（偏离2个标准差时入场）
- EXIT_Z：平仓Z-Score阈值，默认0.5（回归到0.5个标准差以内时平仓）
- MAX_HOLD_BARS：最大持仓K线数，默认10（超时强制平仓）
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期（秒），默认1800（30分钟）
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma, std

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "DCE.m2506"             # 交易合约：豆粕2506合约
ZSCORE_N = 20                    # Z-Score计算回望周期（K线数）
ENTRY_Z = 2.0                    # 开仓阈值：偏离ENTRY_Z个标准差时入场
EXIT_Z = 0.5                     # 平仓阈值：Z-Score回归至此值以内时平仓
MAX_HOLD_BARS = 10               # 最大持仓K线数（超时强制平仓，控制风险）
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 1800            # K线周期：1800秒 = 30分钟
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

# 订阅实时报价
quote = api.get_quote(SYMBOL)

print(f"[Z-Score策略] 启动成功，交易品种：{SYMBOL}，K线周期：{KLINE_DURATION}秒")
print(f"[Z-Score策略] 参数：回望N={ZSCORE_N}，开仓Z={ENTRY_Z}，平仓Z={EXIT_Z}，最大持仓={MAX_HOLD_BARS}根")

# 持仓计时器（记录当前持仓已持有多少根K线）
hold_bars_count = 0           # 已持仓K线数
last_signal_bar_index = -1   # 上次开仓时的K线索引（用于计算持仓时长）

# ============================================================
# 主循环
# ============================================================
try:
    while True:
        api.wait_update()

        if api.is_changing(klines):

            close = klines["close"]  # 收盘价序列

            # ---- 计算Z-Score指标 ----
            # N期均值
            mean_n = ma(close, ZSCORE_N)

            # N期标准差（ddof=0，总体标准差，与tafunc.std一致）
            std_n = std(close, ZSCORE_N)

            # 取最近完成K线的数据
            close_cur = close.iloc[-2]
            mean_cur = mean_n.iloc[-2]
            std_cur = std_n.iloc[-2]

            # 防止标准差为0（价格没有波动，无法计算Z-Score）
            if std_cur == 0 or std_cur != std_cur:  # 检查0和NaN
                print(f"[Z-Score策略] 标准差为0或NaN，跳过本次计算")
                continue

            # 计算Z-Score
            zscore = (close_cur - mean_cur) / std_cur

            # 打印状态
            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"价格={close_cur:.2f}，均值={mean_cur:.2f}，"
                f"标准差={std_cur:.2f}，Z-Score={zscore:.3f}"
            )

            # ---- 查询持仓 ----
            position = api.get_position(SYMBOL)
            volume_long = position.volume_long
            volume_short = position.volume_short

            # ---- 更新持仓计时器 ----
            if volume_long > 0 or volume_short > 0:
                hold_bars_count += 1  # 每根K线更新时增加计数
            else:
                hold_bars_count = 0   # 无持仓时重置计数

            # ---- 平仓逻辑（优先于开仓）----

            # 多仓平仓：Z-Score从负极值回归到-EXIT_Z以上，或超时平仓
            if volume_long > 0:
                should_close_long = (
                    zscore > -EXIT_Z or              # Z-Score已回归到阈值以内
                    hold_bars_count >= MAX_HOLD_BARS  # 持仓超时
                )
                if should_close_long:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=volume_long,
                        limit_price=quote.bid_price1
                    )
                    reason = "均值回归" if zscore > -EXIT_Z else "超时强制平仓"
                    print(
                        f"[Z-Score策略] 平多仓（{reason}）："
                        f"Z-Score={zscore:.3f}，持仓={hold_bars_count}根K线，平{volume_long}手"
                    )
                    hold_bars_count = 0  # 平仓后重置计数
                    continue

            # 空仓平仓：Z-Score从正极值回归到+EXIT_Z以下，或超时平仓
            if volume_short > 0:
                should_close_short = (
                    zscore < EXIT_Z or               # Z-Score已回归到阈值以内
                    hold_bars_count >= MAX_HOLD_BARS  # 持仓超时
                )
                if should_close_short:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=volume_short,
                        limit_price=quote.ask_price1
                    )
                    reason = "均值回归" if zscore < EXIT_Z else "超时强制平仓"
                    print(
                        f"[Z-Score策略] 平空仓（{reason}）："
                        f"Z-Score={zscore:.3f}，持仓={hold_bars_count}根K线，平{volume_short}手"
                    )
                    hold_bars_count = 0
                    continue

            # ---- 开仓逻辑（无持仓时才开仓）----
            if volume_long == 0 and volume_short == 0:

                # 【开多信号】Z-Score < -ENTRY_Z，价格严重低于均值，预期回归，做多
                if zscore < -ENTRY_Z:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.ask_price1
                    )
                    hold_bars_count = 0  # 重置持仓计数
                    print(
                        f"[Z-Score策略] 开多（价格低于均值{abs(zscore):.2f}个标准差）："
                        f"Z-Score={zscore:.3f}，价格={close_cur:.2f}，均值={mean_cur:.2f}"
                    )

                # 【开空信号】Z-Score > +ENTRY_Z，价格严重高于均值，预期回归，做空
                elif zscore > ENTRY_Z:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="OPEN",
                        volume=VOLUME,
                        limit_price=quote.bid_price1
                    )
                    hold_bars_count = 0  # 重置持仓计数
                    print(
                        f"[Z-Score策略] 开空（价格高于均值{zscore:.2f}个标准差）："
                        f"Z-Score={zscore:.3f}，价格={close_cur:.2f}，均值={mean_cur:.2f}"
                    )

except KeyboardInterrupt:
    print("[Z-Score策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[Z-Score策略] API连接已关闭")
