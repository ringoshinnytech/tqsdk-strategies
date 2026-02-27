"""
================================================================================
策略名称：开盘区间突破策略（ORB - Opening Range Breakout）
================================================================================

【策略背景与来源】
开盘区间突破策略（Opening Range Breakout，ORB）是由著名交易员 Toby Crabel 在其
1990年出版的经典著作《Day Trading with Short-Term Price Patterns and Opening Range 
Breakout》中系统性地提出和验证的。该策略认为，开盘后的前N分钟（通常是前15-60分钟）
是当天多空双方争夺的关键时段，这段时间内形成的高低点代表了市场短期内的"共识区间"。

当价格向上突破开盘区间高点时，多头占优，趋势向上；
当价格向下突破开盘区间低点时，空头占优，趋势向下。
该策略在美国股票期货（ES）、商品期货以及中国商品期货市场均有大量实证研究支持。

在中国期货市场中，由于每天的开盘行情（尤其是夜盘转日盘的第一波行情）往往具有较强的
方向性，ORB策略的应用具有良好的理论基础。

【核心逻辑】
1. 等待交易日开盘（检测当天是否为新交易日）
2. 记录开盘后前OPEN_RANGE_MINUTES分钟（默认30分钟）内的最高价和最低价
   形成"开盘区间"[ORB_LOW, ORB_HIGH]
3. 开盘区间确立后（30分钟结束），开始监控价格突破：
   - 价格向上突破ORB_HIGH：做多
   - 价格向下突破ORB_LOW：做空
4. 持仓至收盘前平仓（或达到止损/止盈目标）

过滤条件（可选）：
- 突破幅度过滤：突破幅度需超过最小阈值（避免噪声假突破）
- 成交量过滤：突破时成交量需放大
- 趋势过滤：与昨日收盘价方向一致时信号更强

【计算公式】
开盘区间（取开盘后前N分钟的高低点）：
    ORB_HIGH = MAX(High, 开盘后前N分钟)
    ORB_LOW  = MIN(Low,  开盘后前N分钟)

区间宽度：
    ORB_RANGE = ORB_HIGH - ORB_LOW

突破信号：
    做多：current_price > ORB_HIGH（价格向上穿越区间高点）
    做空：current_price < ORB_LOW（价格向下穿越区间低点）

止损设置（基于ATR或区间宽度）：
    多仓止损 = 开仓价 - ORB_RANGE（或固定止损点数）
    空仓止损 = 开仓价 + ORB_RANGE

【交易信号说明】
- 每天只交易一次：一旦建仓，当天不再接受新信号
- 开多：价格突破ORB_HIGH，以突破价格附近开多仓
- 开空：价格跌破ORB_LOW，以跌破价格附近开空仓
- 收盘前平仓：在收盘前固定时间（如14:45）强制平掉所有仓位
- 止损：亏损超过止损目标时平仓

【适用品种和周期】
适用品种：
- 开盘趋势性强的品种：股指期货（IF、IC、IM）、原油（SC）、黄金（AU）
- 日内波动较大的品种
适用周期：
- 基于日内分钟K线（1分钟或5分钟）
- 参考时段：日盘09:00-15:00，夜盘21:00-次日凌晨

【优缺点分析】
优点：
1. 逻辑清晰，开盘区间具有明确的经济学意义（多空博弈结果）
2. 每天只交易一次，减少了交易成本和过度交易
3. 突破信号在趋势性强的市场中表现出色
4. 结合日内收盘平仓，避免隔夜风险

缺点：
1. 在开盘区间过宽的日子，止损距离大，风险较高
2. 假突破（价格突破后反转）频繁发生，需要过滤
3. 策略依赖固定时间规则，对非标准开盘时间（节假日）需要特殊处理
4. 每天只有一个交易机会，时间效率相对较低

【参数说明】
- SYMBOL：交易合约，默认 CFFEX.IF2506（沪深300股指期货）
- OPEN_RANGE_MINUTES：开盘区间时长（分钟），默认30
- CLOSE_HOUR/MIN：收盘平仓时间，默认14:45
- OPEN_HOUR/MIN：市场开盘时间，默认09:30（股指）
- STOP_LOSS_MULTIPLIER：止损为区间宽度的倍数，默认1.0
- VOLUME：每次交易手数，默认1
- KLINE_DURATION：K线周期，默认60（1分钟）
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import hhv, llv
import datetime

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "CFFEX.IF2506"          # 交易合约：沪深300股指期货2506合约
OPEN_RANGE_MINUTES = 30          # 开盘区间时长（分钟）
OPEN_HOUR = 9                    # 开盘时间：小时（股指期货09:30）
OPEN_MIN = 30                    # 开盘时间：分钟
CLOSE_HOUR = 14                  # 收盘平仓时间：小时
CLOSE_MIN = 45                   # 收盘平仓时间：分钟（14:45强制平仓）
STOP_LOSS_MULTIPLIER = 1.0       # 止损距离 = 区间宽度 × 该倍数
VOLUME = 1                       # 每次交易手数
KLINE_DURATION = 60              # K线周期：60秒 = 1分钟

# 开盘区间结束时间 = 开盘时间 + 开盘区间时长
ORB_END_HOUR = OPEN_HOUR
ORB_END_MIN = OPEN_MIN + OPEN_RANGE_MINUTES
if ORB_END_MIN >= 60:
    ORB_END_HOUR += 1
    ORB_END_MIN -= 60
# 例如：09:30 + 30分钟 = 10:00

# ============================================================
# 初始化 TqApi
# ============================================================
api = TqApi(
    account=TqSim(),
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")
)

# 订阅1分钟K线
klines = api.get_kline_serial(SYMBOL, KLINE_DURATION, data_length=100)

# 订阅实时报价
quote = api.get_quote(SYMBOL)

print(f"[ORB策略] 启动成功，交易品种：{SYMBOL}")
print(
    f"[ORB策略] 参数：开盘区间={OPEN_RANGE_MINUTES}分钟，"
    f"区间结束时间={ORB_END_HOUR:02d}:{ORB_END_MIN:02d}，"
    f"收盘平仓={CLOSE_HOUR:02d}:{CLOSE_MIN:02d}"
)

# 每日状态变量（每天交易开始时重置）
orb_high = None           # 开盘区间最高价
orb_low = None            # 开盘区间最低价
orb_confirmed = False     # 开盘区间是否已确立
traded_today = False      # 今天是否已经交易过
current_date = None       # 当前交易日期
stop_loss_price = None    # 当前止损价格


def reset_daily_state():
    """重置每日交易状态变量"""
    global orb_high, orb_low, orb_confirmed, traded_today, stop_loss_price
    orb_high = None
    orb_low = None
    orb_confirmed = False
    traded_today = False
    stop_loss_price = None
    print(f"[ORB策略] 新交易日开始，状态已重置")


# ============================================================
# 主循环
# ============================================================
try:
    # TargetPosTask：只需声明目标仓位，自动处理追单/撤单/部分成交
    target_pos = TargetPosTask(api, SYMBOL)

    while True:
        api.wait_update()

        if api.is_changing(klines):

            # 获取最新完成K线时间
            bar_dt_ns = klines["datetime"].iloc[-2]  # 纳秒时间戳

            # 将纳秒时间戳转换为datetime对象
            bar_dt = datetime.datetime.fromtimestamp(bar_dt_ns / 1e9)
            bar_date = bar_dt.date()
            bar_time = bar_dt.time()

            # ---- 检测新交易日 ----
            if current_date != bar_date:
                current_date = bar_date
                reset_daily_state()  # 新的一天，重置状态

            # ---- 强制平仓：收盘前固定时间 ----
            close_time = datetime.time(CLOSE_HOUR, CLOSE_MIN)
            if bar_time >= close_time:
                if position.volume_long > 0:
                    target_pos.set_target_volume(0)           # 平仓：TargetPosTask自动平掉全部持仓
                    print(f"[ORB策略] 收盘强制平多：{position.volume_long}手")
                if position.volume_short > 0:
                    target_pos.set_target_volume(0)           # 平仓：TargetPosTask自动平掉全部持仓
                    print(f"[ORB策略] 收盘强制平空：{position.volume_short}手")
                continue  # 收盘时间后不再执行其他逻辑

            # ---- 开盘区间建立阶段 ----
            # 在开盘区间时段内（开盘 ~ ORB结束时间），收集高低点
            open_time = datetime.time(OPEN_HOUR, OPEN_MIN)
            orb_end_time = datetime.time(ORB_END_HOUR, ORB_END_MIN)

            if open_time <= bar_time < orb_end_time:
                # 在开盘区间内，不断更新最高/最低价
                bar_high = klines["high"].iloc[-2]
                bar_low = klines["low"].iloc[-2]

                if orb_high is None:
                    orb_high = bar_high
                    orb_low = bar_low
                else:
                    orb_high = max(orb_high, bar_high)  # 滚动更新最高价
                    orb_low = min(orb_low, bar_low)     # 滚动更新最低价

                print(
                    f"[ORB策略] 建立开盘区间中 {bar_time}："
                    f"区间高={orb_high:.2f}，区间低={orb_low:.2f}"
                )

            # ---- 开盘区间确立 ----
            elif bar_time >= orb_end_time and not orb_confirmed:
                # 开盘区间时间结束，区间确立
                if orb_high is not None and orb_low is not None:
                    orb_confirmed = True
                    orb_range = orb_high - orb_low  # 区间宽度
                    print(
                        f"[ORB策略] 开盘区间确立：高={orb_high:.2f}，"
                        f"低={orb_low:.2f}，宽度={orb_range:.2f}"
                    )

            # ---- 突破交易阶段 ----
            elif orb_confirmed and not traded_today:
                current_price = quote.last_price  # 实时价格
                if current_price <= 0 or current_price != current_price:
                    continue

                orb_range = orb_high - orb_low  # 区间宽度
                stop_dist = orb_range * STOP_LOSS_MULTIPLIER  # 止损距离


                # ---- 止损检查（持仓时实时监控）----
                if stop_loss_price is not None:
                    if position.volume_long > 0 and current_price < stop_loss_price:
                        target_pos.set_target_volume(0)           # 平仓：TargetPosTask自动平掉全部持仓
                        print(
                            f"[ORB策略] 多仓止损触发：价格={current_price:.2f}，"
                            f"止损线={stop_loss_price:.2f}"
                        )
                        traded_today = True  # 止损后今日不再交易
                        continue

                    if position.volume_short > 0 and current_price > stop_loss_price:
                        target_pos.set_target_volume(0)           # 平仓：TargetPosTask自动平掉全部持仓
                        print(
                            f"[ORB策略] 空仓止损触发：价格={current_price:.2f}，"
                            f"止损线={stop_loss_price:.2f}"
                        )
                        traded_today = True
                        continue

                # ---- 无持仓时判断突破信号 ----
                if position.volume_long == 0 and position.volume_short == 0:

                    # 【向上突破】价格突破区间高点，做多
                    if current_price > orb_high:
                        target_pos.set_target_volume(VOLUME)   # 做多：TargetPosTask自动追单到目标仓位
                        stop_loss_price = current_price - stop_dist  # 设置止损价
                        traded_today = True  # 标记今日已交易（只交易一次）
                        print(
                            f"[ORB策略] 向上突破开多！"
                            f"价格={current_price:.2f}，区间高={orb_high:.2f}，"
                            f"止损={stop_loss_price:.2f}，开{VOLUME}手"
                        )

                    # 【向下突破】价格跌破区间低点，做空
                    elif current_price < orb_low:
                        target_pos.set_target_volume(-VOLUME)  # 做空：TargetPosTask自动追单到目标仓位
                        stop_loss_price = current_price + stop_dist  # 设置止损价
                        traded_today = True
                        print(
                            f"[ORB策略] 向下突破开空！"
                            f"价格={current_price:.2f}，区间低={orb_low:.2f}，"
                            f"止损={stop_loss_price:.2f}，开{VOLUME}手"
                        )

except KeyboardInterrupt:
    print("[ORB策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[ORB策略] API连接已关闭")
