"""
================================================================================
策略名称：量价趋势策略（成交量配合价格突破验证信号）
================================================================================

【策略背景与来源】
量价关系（Volume-Price Relationship）是技术分析领域最核心的研究方向之一。
著名技术分析理论——道氏理论（Dow Theory）就强调：有效的价格突破必须有成交量的配合，
"量先于价"是市场行为的基本规律。后来 Joseph Granville 提出的OBV（能量潮指标）、
Marc Chaikin 的CMF（资金流量指标）等，均是量价关系研究的重要成果。

在期货市场中，成交量是衡量市场参与度和资金介入程度的重要指标：
- 价格上涨+成交量放大：多头主动买入，趋势有效，信号可信
- 价格下跌+成交量放大：空头主动卖出，趋势有效，信号可信
- 价格上涨+成交量萎缩：缺乏多头支撑，突破可疑，可能假突破
- 价格下跌+成交量萎缩：空头动能不足，跌势可能终结

量价趋势策略将价格突破信号与成交量放大条件相结合，通过双重确认提高信号质量，
降低假突破率，是改进版的价格突破策略。

【核心逻辑】
1. 价格信号：使用N期价格通道（hhv/llv）判断价格是否创新高/新低（突破信号）
2. 成交量信号：当前成交量是否超过M期平均成交量的倍数（放量确认）
3. 双重确认：价格突破 AND 成交量放大 → 开仓
4. 退出条件：价格回归通道内部（反转信号）或达到止盈/止损目标

量价背离（辅助过滤）：
- 价涨量缩（多头背离）：价格新高但成交量低于均值，信号可疑，不开仓
- 价跌量缩（空头背离）：价格新低但成交量低于均值，信号可疑，不开仓

【计算公式】
N期价格通道：
    Channel_High(N) = HHV(Close, N)  # N期最高收盘价
    Channel_Low(N)  = LLV(Close, N)  # N期最低收盘价

M期平均成交量：
    Vol_MA(M) = MA(Volume, M)

成交量倍数（衡量当前成交量是否异常放大）：
    Vol_Ratio = Current_Volume / Vol_MA(M)

价格突破+量价确认条件：
    多头信号：Close > Channel_High(N-1) AND Vol_Ratio > VOL_MULTIPLIER
    空头信号：Close < Channel_Low(N-1)  AND Vol_Ratio > VOL_MULTIPLIER

平仓条件：
    多仓平仓：Close < Channel_Low(EXIT_N)  # 价格跌破短期低点
    空仓平仓：Close > Channel_High(EXIT_N) # 价格涨破短期高点

【交易信号说明】
- 开多：收盘价创N期新高（突破） AND 当根成交量>均值×放量倍数
- 开空：收盘价创N期新低（突破） AND 当根成交量>均值×放量倍数
- 平多：收盘价跌破EXIT_N期低点（反转迹象）
- 平空：收盘价涨破EXIT_N期高点（反转迹象）
- 单边持仓：不同时持有多空双向仓位

【适用品种和周期】
适用品种：
- 流动性好、成交量数据可靠的品种：铜（CU）、螺纹钢（RB）、股指（IF）
- 避免成交量数据失真的品种（如临近到期的冷门合约）
适用周期：
- 日线效果最好（成交量数据最具参考价值）
- 60分钟或以上均可

【优缺点分析】
优点：
1. 量价双重确认显著降低假突破率
2. 有扎实的技术分析理论支持（道氏理论）
3. 成交量放大确认机构资金介入，信号更可靠
4. 逻辑简单清晰，参数少，容易调优

缺点：
1. 成交量放大的阈值（VOL_MULTIPLIER）需要根据品种特性调整
2. 在流动性不佳时段，成交量数据噪声大
3. 期货连续合约换月时成交量会出现异常跳变
4. 纯价格通道策略在区间震荡时会产生假信号

【为何使用 TargetPosTask】
本策略使用 TargetPosTask 替代直接调用 insert_order，原因如下：
- TargetPosTask 内部自动处理追单、撤单、部分成交等复杂场景，无需手动管理订单状态
- 只需指定目标持仓量（正数=多仓，负数=空仓，0=平仓），框架自动计算需要的净操作
- 避免了先平后开的繁琐逻辑，代码更简洁、更健壮
- 在网络延迟或行情快速变化时，TargetPosTask 能正确处理未成交订单的撤单重发

【参数说明】
- SYMBOL：交易合约，默认 SHFE.cu2506（沪铜）
- BREAKOUT_N：价格通道周期（突破N期高低点），默认20
- EXIT_N：平仓通道周期（短期通道，触发平仓），默认10
- VOL_MA_N：成交量均线周期，默认20
- VOL_MULTIPLIER：放量倍数阈值（当前量>均量×倍数才确认放量），默认1.5
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期（秒），默认86400（日线）
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import hhv, llv, ma

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "SHFE.cu2506"           # 交易合约：沪铜2506合约
BREAKOUT_N = 20                  # 突破通道周期：20期最高/最低价作为突破基准
EXIT_N = 10                      # 平仓通道周期：价格回归10期区间时平仓
VOL_MA_N = 20                    # 成交量均线周期
VOL_MULTIPLIER = 1.5             # 放量倍数：当前成交量>均量×1.5倍才确认信号
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 86400           # K线周期：86400秒 = 1天（日线）
DATA_LENGTH = 150                # 获取K线数量

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

# 初始化 TargetPosTask，自动管理持仓目标（自动处理追单/撤单/部分成交）
target_pos = TargetPosTask(api, SYMBOL)

print(f"[量价策略] 启动成功，交易品种：{SYMBOL}，K线周期：{KLINE_DURATION}秒")
print(
    f"[量价策略] 参数：突破周期={BREAKOUT_N}，平仓周期={EXIT_N}，"
    f"量线周期={VOL_MA_N}，放量倍数={VOL_MULTIPLIER}"
)

# ============================================================
# 主循环：等待K线更新并计算量价信号
# ============================================================
try:
    while True:
        api.wait_update()

        if api.is_changing(klines):

            close = klines["close"]    # 收盘价序列
            volume = klines["volume"]  # 成交量序列
            high = klines["high"]      # 最高价序列
            low = klines["low"]        # 最低价序列

            # ---- 计算价格通道 ----
            # 突破通道：用于开仓判断
            # 注意：为避免当前K线影响，用 .iloc[-3:] 之前的区间判断突破
            # 实现：取前N根K线（不含当前K线-2）的高低极值
            # tafunc的hhv/llv包含当前点，我们用N+1期并取前一根的值
            channel_high_n = hhv(close, BREAKOUT_N)   # N期收盘价最高（含当前点）
            channel_low_n = llv(close, BREAKOUT_N)    # N期收盘价最低

            # 平仓通道：用于平仓判断（更短周期，更灵敏）
            channel_high_exit = hhv(high, EXIT_N)
            channel_low_exit = llv(low, EXIT_N)

            # ---- 计算成交量指标 ----
            vol_ma = ma(volume, VOL_MA_N)  # 成交量均线

            # 取最新完成K线的数据（-2为当前完成K线）
            close_cur = close.iloc[-2]            # 当前收盘价
            close_prev = close.iloc[-3]           # 前一收盘价

            # 突破基准：用前N根K线（不含当前K线）的极值，即 index -3 位置的通道值
            # 这样可以判断当前K线是否突破了前N期极值
            prev_channel_high = channel_high_n.iloc[-3]  # 前N期最高价（不含当前）
            prev_channel_low = channel_low_n.iloc[-3]    # 前N期最低价（不含当前）

            # 当前K线成交量
            vol_cur = volume.iloc[-2]
            vol_ma_cur = vol_ma.iloc[-2]           # 当前成交量均线

            # 计算成交量倍数（放量比例）
            if vol_ma_cur > 0:
                vol_ratio = vol_cur / vol_ma_cur  # 当前量/均量
            else:
                vol_ratio = 0

            # 平仓通道值（当前）
            exit_high = channel_high_exit.iloc[-2]  # EXIT_N期最高价
            exit_low = channel_low_exit.iloc[-2]    # EXIT_N期最低价

            # 打印状态
            print(
                f"[{klines['datetime'].iloc[-2]}] "
                f"收盘={close_cur:.2f}，前{BREAKOUT_N}期高={prev_channel_high:.2f}，"
                f"低={prev_channel_low:.2f}，量比={vol_ratio:.2f}x"
            )

            # ---- 量价双重确认——判断是否放量（成交量倍数超过阈值）----
            is_big_volume = vol_ratio >= VOL_MULTIPLIER

            # ---- 平仓逻辑（优先）----

            # 持多仓：价格回落到EXIT_N期低点（短期低点），说明趋势减弱，平多
            # 持空仓：价格反弹至EXIT_N期高点，说明空头趋势减弱，平空
            # 注意：TargetPosTask 内部会读取当前持仓，无需手动查询 position
            if close_cur < exit_low:
                target_pos.set_target_volume(0)
                print(
                    f"[量价策略] 平多仓：价格{close_cur:.2f} < "
                    f"{EXIT_N}期低点{exit_low:.2f}，平仓"
                )
            elif close_cur > exit_high:
                target_pos.set_target_volume(0)
                print(
                    f"[量价策略] 平空仓：价格{close_cur:.2f} > "
                    f"{EXIT_N}期高点{exit_high:.2f}，平仓"
                )

            # ---- 开仓逻辑 ----

            # 【开多信号】价格突破前N期收盘价高点 + 成交量放大
            elif (close_cur > prev_channel_high     # 价格突破N期最高价
                    and is_big_volume):             # 成交量放大确认

                target_pos.set_target_volume(VOLUME)
                print(
                    f"[量价策略] 量价多头开多！"
                    f"价格={close_cur:.2f}>{prev_channel_high:.2f}，"
                    f"量比={vol_ratio:.2f}x，目标{VOLUME}手"
                )

            # 【开空信号】价格跌破前N期收盘价低点 + 成交量放大
            elif (close_cur < prev_channel_low    # 价格突破N期最低价
                      and is_big_volume):         # 成交量放大确认

                target_pos.set_target_volume(-VOLUME)
                print(
                    f"[量价策略] 量价空头开空！"
                    f"价格={close_cur:.2f}<{prev_channel_low:.2f}，"
                    f"量比={vol_ratio:.2f}x，目标{-VOLUME}手"
                )

            else:
                # 未触发信号的情况下，记录量价状态
                if not is_big_volume and (close_cur > prev_channel_high or close_cur < prev_channel_low):
                    print(
                        f"[量价策略] 价格突破但量能不足（量比={vol_ratio:.2f}x"
                        f"<{VOL_MULTIPLIER}x），忽略信号（避免假突破）"
                    )

except KeyboardInterrupt:
    print("[量价策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[量价策略] API连接已关闭")
