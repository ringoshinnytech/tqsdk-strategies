"""
================================================================================
策略名称：MACD趋势跟踪策略（DIF与DEA金叉死叉）
================================================================================

【策略背景与来源】
MACD（Moving Average Convergence Divergence，移动平均收敛/发散指标）由 Gerald Appel
于1970年代末期发明，是技术分析领域最经典、应用最广泛的趋势跟踪指标之一。该指标通过
计算两条不同周期指数移动平均线（EMA）之差，来衡量价格的趋势方向与动能强弱，兼具趋势
跟踪与动量测量的双重功能。在期货量化交易中，MACD 被广泛用于判断趋势方向、过滤震荡信号，
是中长线趋势策略的核心工具之一。

【核心逻辑】
策略基于三条核心线：
1. DIF（差离值）：快速EMA(12) 减去慢速EMA(26) 的差值，反映短期趋势与长期趋势的偏离程度
2. DEA（信号线）：对DIF进行EMA(9)平滑，起到信号确认作用
3. MACD柱（BAR）：DIF - DEA，以柱状图形式展示动能大小

核心交易逻辑：
- 金叉买入：DIF从下方穿越DEA（crossup），表示短期动能超过长期，趋势转为上行，做多
- 死叉卖出：DIF从上方穿越DEA（crossdown），表示短期动能弱于长期，趋势转为下行，做空
- 持仓期间：仅在信号反转时进行平仓并开反向仓，保持持仓直至反向信号出现

【计算公式】
EMA_fast  = EMA(close, 12)
EMA_slow  = EMA(close, 26)
DIF       = EMA_fast - EMA_slow
DEA       = EMA(DIF, 9)
MACD_BAR  = (DIF - DEA) × 2

金叉：上一根K线 DIF < DEA，当前K线 DIF > DEA
死叉：上一根K线 DIF > DEA，当前K线 DIF < DEA

【交易信号说明】
- 开多信号：DIF 上穿 DEA（金叉），当市场无持仓或持有空仓时触发
- 开空信号：DIF 下穿 DEA（死叉），当市场无持仓或持有多仓时触发
- 平多信号：持有多仓且DIF死叉DEA时，先平多仓再开空仓
- 平空信号：持有空仓且DIF金叉DEA时，先平空仓再开多仓
- 策略为持仓转换型（反手），不留空仓期

【适用品种和周期】
适用品种：趋势性强的品种，如原油（SC）、黄金（AU）、铜（CU）、股指（IF/IC/IM）
适用周期：建议15分钟至日线，过短周期噪声过多，过长周期信号稀少
推荐周期：60分钟或日线（duration_seconds=3600 或 86400）

【优缺点分析】
优点：
1. 逻辑简单直观，易于理解和实施
2. 对趋势行情有较好的捕捉能力
3. 天然具备过滤小幅震荡的功能（EMA平滑）
4. 参数调整灵活，可根据品种特性优化

缺点：
1. 属于滞后指标，信号出现时价格已有一定移动
2. 在震荡行情中频繁金叉死叉，产生较多假信号
3. 参数固定（12,26,9）可能不适合所有品种和周期
4. 无内置止损机制，需配合其他止损策略使用

【参数说明】
- SYMBOL：交易合约代码，默认 SHFE.cu2506（沪铜）
- FAST_PERIOD：快线EMA周期，默认12
- SLOW_PERIOD：慢线EMA周期，默认26
- SIGNAL_PERIOD：信号线DEA周期，默认9
- VOLUME：每次开仓手数，默认1手
- KLINE_DURATION：K线周期（秒），默认3600（1小时）
- DATA_LENGTH：K线数据长度，默认300根
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ema, crossup, crossdown

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "SHFE.cu2506"          # 交易合约：沪铜2506合约
FAST_PERIOD = 12                 # MACD快线周期（EMA12）
SLOW_PERIOD = 26                 # MACD慢线周期（EMA26）
SIGNAL_PERIOD = 9                # MACD信号线周期（DEA的EMA周期）
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 3600            # K线周期：3600秒 = 1小时
DATA_LENGTH = 300                # 获取K线数量（需大于SLOW_PERIOD以保证指标有效）

# ============================================================
# 初始化 TqApi，使用模拟账户
# ============================================================
api = TqApi(
    account=TqSim(),                                    # 使用模拟账户进行回测/仿真
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")       # 替换为你的天勤账户和密码
)

# 订阅K线数据
klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=DATA_LENGTH)

# 订阅实时报价（用于获取当前价格）
quote = api.get_quote(SYMBOL)

print(f"[MACD策略] 启动成功，交易品种：{SYMBOL}，K线周期：{KLINE_DURATION}秒")
print(f"[MACD策略] 参数：快线={FAST_PERIOD}，慢线={SLOW_PERIOD}，信号线={SIGNAL_PERIOD}")

# ============================================================
# 主循环：等待K线更新并计算信号
# ============================================================
try:
    while True:
        api.wait_update()  # 阻塞等待行情数据更新

        # 判断K线是否有新数据更新
        if api.is_changing(klines):

            # ---- 计算 MACD 指标 ----
            close = klines["close"]  # 获取收盘价序列（pandas Series）

            # 计算快速EMA（12周期）和慢速EMA（26周期）
            ema_fast = ema(close, FAST_PERIOD)   # 快线EMA12
            ema_slow = ema(close, SLOW_PERIOD)   # 慢线EMA26

            # DIF = EMA(fast) - EMA(slow)，反映短长期趋势差异
            dif = ema_fast - ema_slow

            # DEA = EMA(DIF, 9)，对DIF再次平滑，作为信号线
            dea = ema(dif, SIGNAL_PERIOD)

            # MACD柱 = (DIF - DEA) * 2，反映动能强弱（展示用）
            macd_bar = (dif - dea) * 2

            # ---- 检测金叉/死叉信号 ----
            # crossup(a, b)：a从下方穿越b（上穿），即前一根 a<b，当前 a>b
            golden_cross = crossup(dif, dea)    # 金叉信号序列（True/False）
            death_cross = crossdown(dif, dea)   # 死叉信号序列（True/False）

            # 取最新一根K线（已收盘的倒数第二根，避免用未完成K线）
            # index -1 是最新未完成K线，-2 是最近完成的K线
            is_golden = bool(golden_cross.iloc[-2])  # 最新完成K线是否为金叉
            is_death = bool(death_cross.iloc[-2])    # 最新完成K线是否为死叉

            # 打印当前指标状态（调试用）
            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"DIF={dif.iloc[-2]:.4f}, DEA={dea.iloc[-2]:.4f}, "
                f"BAR={macd_bar.iloc[-2]:.4f} | "
                f"金叉={is_golden}, 死叉={is_death}"
            )

            # ---- 查询当前持仓 ----
            position = api.get_position(SYMBOL)
            volume_long = position.volume_long    # 当前多仓手数
            volume_short = position.volume_short  # 当前空仓手数

            # ---- 执行交易逻辑 ----

            # 【金叉信号】DIF上穿DEA，趋势转多，做多
            if is_golden:
                # 如果当前持有空仓，先平空
                if volume_short > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",        # 买入方向
                        offset="CLOSE",         # 平仓
                        volume=volume_short,    # 平掉全部空仓
                        limit_price=quote.ask_price1  # 以卖一价成交（市价买）
                    )
                    print(f"[MACD策略] 金叉平空：平空{volume_short}手")

                # 如果当前无多仓，开多仓
                if volume_long == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="BUY",        # 买入方向
                        offset="OPEN",          # 开仓
                        volume=VOLUME,          # 开仓手数
                        limit_price=quote.ask_price1  # 以卖一价开多（市价买）
                    )
                    print(f"[MACD策略] 金叉开多：开多{VOLUME}手，价格={quote.ask_price1}")

            # 【死叉信号】DIF下穿DEA，趋势转空，做空
            elif is_death:
                # 如果当前持有多仓，先平多
                if volume_long > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",       # 卖出方向
                        offset="CLOSE",         # 平仓
                        volume=volume_long,     # 平掉全部多仓
                        limit_price=quote.bid_price1  # 以买一价成交（市价卖）
                    )
                    print(f"[MACD策略] 死叉平多：平多{volume_long}手")

                # 如果当前无空仓，开空仓
                if volume_short == 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",       # 卖出方向
                        offset="OPEN",          # 开仓
                        volume=VOLUME,          # 开仓手数
                        limit_price=quote.bid_price1  # 以买一价开空（市价卖）
                    )
                    print(f"[MACD策略] 死叉开空：开空{VOLUME}手，价格={quote.bid_price1}")

except KeyboardInterrupt:
    # 捕获 Ctrl+C 信号，优雅退出
    print("[MACD策略] 用户中断，策略停止运行")
finally:
    # 关闭API连接，释放资源
    api.close()
    print("[MACD策略] API连接已关闭")
