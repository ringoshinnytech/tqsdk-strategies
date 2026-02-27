"""
================================================================================
策略名称：价格动量突破策略（N日涨跌幅动量信号）
================================================================================

【策略背景与来源】
动量效应（Momentum Effect）是金融学中经过学术界广泛验证的市场异象之一。
1993年，Jegadeesh 和 Titman 在《Journal of Finance》上发表了经典论文，
证明了在股票市场中过去表现好的资产倾向于在未来继续表现好（动量持续性）。
这一现象在商品期货市场中同样存在，因为期货价格受供需基本面、宏观政策等因素驱动，
趋势往往具有持续性。

价格动量策略（Price Momentum Strategy）是量化交易中最简单、最基础的趋势策略之一，
通过计算过去N期的价格涨跌幅来衡量动量强度，在动量超过阈值时顺势入场。

【核心逻辑】
动量信号计算：
1. 计算过去N根K线的价格涨跌幅（动量值）
   动量 = (当前收盘价 - N根前收盘价) / N根前收盘价 × 100%
2. 当动量超过正阈值（THRESHOLD），认为多头动能充足，开多仓
3. 当动量低于负阈值（-THRESHOLD），认为空头动能充足，开空仓
4. 当动量回归至[-EXIT_THRESHOLD, EXIT_THRESHOLD]区间时，认为动能衰减，平仓

可选增强：
- 使用均线过滤：只有当价格在均线上方才做多，在均线下方才做空
- 使用动量加速度：动量本身也在增加时信号更强
- 使用ATR标准化动量：动量/ATR，消除品种波动率差异

【计算公式】
价格动量（N期回报率）：
    Momentum(N) = (Close_t - Close_{t-N}) / Close_{t-N} × 100%

动量信号：
    做多：Momentum(N) > THRESHOLD（正动量超过阈值）
    做空：Momentum(N) < -THRESHOLD（负动量超过阈值）
    平仓：|Momentum(N)| < EXIT_THRESHOLD（动量衰减到退出阈值以下）

均线过滤（可选）：
    做多条件额外：Close > MA(Close, FILTER_N)
    做空条件额外：Close < MA(Close, FILTER_N)

【交易信号说明】
- 开多：N期动量超过THRESHOLD且价格在均线之上（均线过滤开启时）
- 开空：N期动量低于-THRESHOLD且价格在均线之下
- 平多：动量回落到EXIT_THRESHOLD以下，或动量反转为负
- 平空：动量回升到-EXIT_THRESHOLD以上，或动量反转为正
- 策略中不同时持有多仓和空仓

【适用品种和周期】
适用品种：
- 趋势性强、动量持续性好的品种：螺纹钢（RB）、原油（SC）、铜（CU）
- 避免应用于均值回归特性强的品种（如部分农产品）
适用周期：
- 日线动量：N=10-20，适合中期趋势跟踪
- 小时线动量：N=20-60，适合日内趋势
- 参考文献通常采用日线级别

【优缺点分析】
优点：
1. 逻辑极其简单，无复杂计算，易于理解和实现
2. 有扎实的学术理论支撑（动量效应在期货市场已被验证）
3. 顺势交易，在趋势行情中理论上可获较大盈利
4. 计算量小，适合高频更新

缺点：
1. 在震荡市场中频繁触发阈值，产生大量假信号
2. 动量阈值（THRESHOLD）的设置对结果影响极大，需要历史数据调参
3. 纯动量策略没有内置止损，需额外添加风控
4. 动量信号有一定滞后（N期回看），错过行情初期

【参数说明】
- SYMBOL：交易合约，默认 SHFE.rb2506（螺纹钢）
- MOMENTUM_N：动量计算回望周期（K线数），默认20
- THRESHOLD：开仓动量阈值（%），默认2.0（动量超过2%触发信号）
- EXIT_THRESHOLD：平仓动量阈值（%），默认0.5（动量回归到0.5%以内平仓）
- FILTER_N：均线过滤周期，默认60（用于过滤逆势信号）
- USE_MA_FILTER：是否启用均线过滤，默认True
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期（秒），默认3600（1小时）
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "SHFE.rb2506"          # 交易合约：螺纹钢2506合约
MOMENTUM_N = 20                  # 动量计算回望期（过去N根K线的涨跌幅）
THRESHOLD = 2.0                  # 开仓动量阈值（%），动量绝对值超过此值时触发信号
EXIT_THRESHOLD = 0.5             # 平仓动量阈值（%），动量绝对值低于此值时平仓
FILTER_N = 60                    # 均线过滤周期（K线数）
USE_MA_FILTER = True             # 是否启用均线过滤（True=开启）
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 3600            # K线周期：1小时
DATA_LENGTH = 300                # K线数量（需 > MOMENTUM_N + FILTER_N）

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

print(f"[动量策略] 启动成功，交易品种：{SYMBOL}，K线周期：{KLINE_DURATION}秒")
print(f"[动量策略] 参数：动量周期={MOMENTUM_N}，开仓阈值={THRESHOLD}%，"
      f"平仓阈值={EXIT_THRESHOLD}%，均线过滤={'开启' if USE_MA_FILTER else '关闭'}")

# ============================================================
# 主循环：等待K线更新并计算动量信号
# ============================================================
try:
    while True:
        api.wait_update()  # 等待行情更新

        if api.is_changing(klines):

            close = klines["close"]  # 收盘价序列

            # ---- 计算价格动量 ----
            # 取最近完成K线（-2）和N根前的K线（-2-MOMENTUM_N）
            # 动量 = (当前价 - N根前价) / N根前价 × 100%
            close_cur = close.iloc[-2]                    # 当前收盘价
            close_n_ago = close.iloc[-2 - MOMENTUM_N]    # N根K线前的收盘价

            # 防止除以零（理论上不会发生）
            if close_n_ago == 0:
                continue

            # 计算动量百分比
            momentum = (close_cur - close_n_ago) / close_n_ago * 100.0

            # ---- 均线过滤 ----
            ma_filter = ma(close, FILTER_N)
            ma_cur = ma_filter.iloc[-2]  # 当前均线值

            # 判断价格是否在均线之上/之下
            price_above_ma = close_cur > ma_cur   # 价格在均线上方（多头环境）
            price_below_ma = close_cur < ma_cur   # 价格在均线下方（空头环境）

            # 打印状态信息
            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"当前价={close_cur:.2f}，{MOMENTUM_N}周期前={close_n_ago:.2f}，"
                f"动量={momentum:.2f}%，MA({FILTER_N})={ma_cur:.2f}"
            )

            # ---- 查询持仓状态 ----
            position = api.get_position(SYMBOL)
            volume_long = position.volume_long
            volume_short = position.volume_short

            # ---- 平仓逻辑（优先执行）----

            # 持多仓时：若动量回归至平仓阈值以下，或动量变负，平多仓
            if volume_long > 0:
                if momentum < EXIT_THRESHOLD:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=volume_long,
                        limit_price=quote.bid_price1
                    )
                    print(f"[动量策略] 多仓平仓：动量回落至{momentum:.2f}%，平多{volume_long}手")
                    continue  # 本次K线处理完毕，等待下根K线

            # 持空仓时：若动量回归至平仓阈值以上，或动量变正，平空仓
            if volume_short > 0:
                if momentum > -EXIT_THRESHOLD:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=volume_short,
                        limit_price=quote.ask_price1
                    )
                    print(f"[动量策略] 空仓平仓：动量回升至{momentum:.2f}%，平空{volume_short}手")
                    continue

            # ---- 开仓逻辑 ----

            # 判断是否满足均线过滤条件
            can_go_long = (not USE_MA_FILTER) or price_above_ma    # 多头过滤
            can_go_short = (not USE_MA_FILTER) or price_below_ma   # 空头过滤

            # 【开多信号】正动量超过阈值（强势上涨动能）且满足均线过滤
            if momentum > THRESHOLD and can_go_long and volume_long == 0:
                # 如有空仓先平
                if volume_short > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",
                        offset="CLOSE",
                        volume=volume_short,
                        limit_price=quote.ask_price1
                    )
                    print(f"[动量策略] 动量开多前平空：{volume_short}手")

                # 开多仓
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",
                    offset="OPEN",
                    volume=VOLUME,
                    limit_price=quote.ask_price1
                )
                print(
                    f"[动量策略] 开多：动量={momentum:.2f}%>{THRESHOLD}%，"
                    f"价格={close_cur:.2f}，均线={ma_cur:.2f}，开{VOLUME}手"
                )

            # 【开空信号】负动量超过阈值（强势下跌动能）且满足均线过滤
            elif momentum < -THRESHOLD and can_go_short and volume_short == 0:
                # 如有多仓先平
                if volume_long > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=volume_long,
                        limit_price=quote.bid_price1
                    )
                    print(f"[动量策略] 动量开空前平多：{volume_long}手")

                # 开空仓
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",
                    offset="OPEN",
                    volume=VOLUME,
                    limit_price=quote.bid_price1
                )
                print(
                    f"[动量策略] 开空：动量={momentum:.2f}%<-{THRESHOLD}%，"
                    f"价格={close_cur:.2f}，均线={ma_cur:.2f}，开{VOLUME}手"
                )

except KeyboardInterrupt:
    print("[动量策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[动量策略] API连接已关闭")
