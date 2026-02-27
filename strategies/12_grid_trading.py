"""
================================================================================
策略名称：网格交易策略（在价格区间内按网格间距自动挂单买卖）
================================================================================

【策略背景与来源】
网格交易（Grid Trading）是一种以固定价格间距，在价格区间内分层布置买单和卖单，
通过价格在区间内的波动来反复盈利的交易策略。该策略起源于外汇市场，广泛应用于
波动较为规律的品种，是量化交易中最具"机械化"特征的策略之一。

网格交易的核心理念是：不预测价格方向，而是利用价格的上下波动套利。
只要价格在设定的区间内震荡，每一次价格穿越网格线都可以完成一次低买高卖的循环，
积累小额利润。即使是随机游走的价格，在一个区间内反复震荡也能产生稳定收益。

网格交易在加密货币（如BTC/USDT）、外汇和商品期货市场中均有广泛应用。
对于期货市场，需要特别注意：期货有到期日，需要及时换月，且期货有杠杆风险。

【核心逻辑】
1. 预设价格区间：[GRID_LOW, GRID_HIGH]
2. 在区间内按固定间距（GRID_STEP）划分若干网格线
3. 在每条网格线设置买入/卖出逻辑：
   - 当价格从上方跌穿网格线时：在该网格线价位买入1手（低买）
   - 当价格从下方涨穿网格线时：在该网格线价位卖出1手（高卖）
4. 对每个网格层级记录状态（是否持有），避免重复下单
5. 当价格突破区间上限时：平掉所有多仓，等待价格回归区间
6. 当价格突破区间下限时：停止买入，等待价格回归

【计算公式】
网格数量：
    GRID_COUNT = (GRID_HIGH - GRID_LOW) / GRID_STEP

网格线价格（第i条，从下到上）：
    Grid_Price[i] = GRID_LOW + i × GRID_STEP

每个网格理论利润（不含手续费）：
    Profit_per_Grid = GRID_STEP × Contract_Multiplier

网格总投入资金（参考）：
    Capital = GRID_COUNT × VOLUME × Initial_Margin_per_Lot

【交易信号说明】
- 初始化：在策略启动时，根据当前价格在每条网格线以下放置买单
- 买入信号：当前价格下穿某网格线（且该层未持仓），在该价位附近买入
- 卖出信号：当前价格上穿某网格线（且该层上方有持仓），在该价位附近卖出
- 止损：价格跌破区间下限（GRID_LOW）时，清空所有多仓（可选）
- 止盈：价格涨破区间上限（GRID_HIGH）时，清空所有多仓

注意：本策略实现简化版，使用实时价格判断是否穿越网格线（模拟限价单效果）

【适用品种和周期】
适用品种：
- 价格长期在区间内震荡的品种：农产品（豆粕、玉米）、贵金属（黄金）
- 历史波动率适中、趋势性不强的品种
不适用：
- 单边趋势强烈的品种（价格突破区间后网格策略会大幅亏损）

适用周期：
- 实时行情触发（无固定K线周期要求），推荐tick或1分钟级别更新

【优缺点分析】
优点：
1. 不需要预测价格方向，在震荡市场中持续盈利
2. 策略逻辑简单，自动化程度高，情绪干扰少
3. 只要价格在区间内，每次波动都能产生利润
4. 可以通过调整网格密度灵活适应不同波动率

缺点：
1. 单边趋势行情中，可能持续买入而价格持续下跌（左侧接刀）
2. 需要大量资金分散在多个网格层级
3. 价格突破区间后，策略失效，需要手动调整区间
4. 期货到期换月时需要重新设置网格
5. 手续费累积对策略盈利有较大影响

【参数说明】
- SYMBOL：交易合约，默认 CZCE.MA506（甲醇，偏震荡品种）
- GRID_LOW：网格区间下限价格，默认2200
- GRID_HIGH：网格区间上限价格，默认2600
- GRID_STEP：网格间距（每格价格差），默认40
- VOLUME：每格交易手数，默认1
- MAX_GRID_POSITION：最大网格持仓手数（防止持仓过多），默认10
================================================================================
"""

from tqsdk import TqApi, TqAuth, TqSim
import math

# ============================================================
# 策略参数配置
# ============================================================
SYMBOL = "CZCE.MA509"            # 交易合约：郑商所甲醇合约（震荡特性较好）
GRID_LOW = 2200                  # 网格区间下限（需根据实际价格调整）
GRID_HIGH = 2600                 # 网格区间上限（需根据实际价格调整）
GRID_STEP = 40                   # 网格间距（每格40点）
VOLUME = 1                       # 每格交易手数
MAX_GRID_POSITION = 10           # 最大允许持仓手数（风控）

# ============================================================
# 初始化网格
# ============================================================
# 根据区间和间距计算网格线列表
grid_lines = []
price = GRID_LOW
while price <= GRID_HIGH:
    grid_lines.append(round(price, 2))  # 保留2位小数，避免浮点误差
    price += GRID_STEP

print(f"[网格策略] 网格线设置：{grid_lines}")
print(f"[网格策略] 共{len(grid_lines)}条网格线，区间[{GRID_LOW}, {GRID_HIGH}]，间距{GRID_STEP}")

# 网格状态记录：记录每条网格线下方是否有持仓
# key: 网格线价格, value: True=该层有持仓（已买入，等待价格回升卖出）
grid_has_position = {line: False for line in grid_lines}

# 上次价格（用于判断是否穿越网格线）
last_price = None

# ============================================================
# 初始化 TqApi
# ============================================================
api = TqApi(
    account=TqSim(),
    auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")
)

# 订阅实时报价（网格策略依赖实时行情，不依赖K线）
quote = api.get_quote(SYMBOL)

# 也订阅1分钟K线（用于初始化当前价格参考）
klines_1m = api.get_kline_serial(SYMBOL, 60, data_length=10)

print(f"[网格策略] 启动成功，交易品种：{SYMBOL}")
print(f"[网格策略] 最大持仓={MAX_GRID_POSITION}手，每格交易{VOLUME}手")


def get_grid_below(price, grid_lines):
    """
    获取当前价格下方最近的网格线

    参数：
        price: 当前价格
        grid_lines: 网格线列表（从低到高排序）

    返回：
        下方最近的网格线价格，如无则返回None
    """
    below = [g for g in grid_lines if g < price]
    return below[-1] if below else None


def get_grid_above(price, grid_lines):
    """
    获取当前价格上方最近的网格线

    参数：
        price: 当前价格
        grid_lines: 网格线列表（从低到高排序）

    返回：
        上方最近的网格线价格，如无则返回None
    """
    above = [g for g in grid_lines if g > price]
    return above[0] if above else None


# ============================================================
# 主循环：实时监控价格变化并执行网格交易
# ============================================================
try:
    while True:
        api.wait_update()

        # 监控实时报价变化
        if api.is_changing(quote):
            current_price = quote.last_price  # 当前最新成交价

            # 价格无效时跳过
            if current_price != current_price or current_price <= 0:
                continue

            # 初始化last_price（第一次运行）
            if last_price is None:
                last_price = current_price
                print(f"[网格策略] 初始化价格：{current_price}")
                continue

            # 查询当前总持仓
            position = api.get_position(SYMBOL)
            total_long = position.volume_long   # 总多仓数量

            # ---- 价格突破区间上限：清仓 ----
            if current_price >= GRID_HIGH:
                if total_long > 0:
                    api.insert_order(
                        symbol=SYMBOL,
                        direction="SELL",
                        offset="CLOSE",
                        volume=total_long,
                        limit_price=quote.bid_price1
                    )
                    # 重置所有网格状态
                    for line in grid_lines:
                        grid_has_position[line] = False
                    print(f"[网格策略] 价格突破上限{GRID_HIGH}，清空全部多仓{total_long}手")

                last_price = current_price
                continue

            # ---- 遍历所有网格线，检测是否发生穿越 ----
            for grid_price in grid_lines:

                # 检测价格从上方下穿网格线（上一价格>网格线 且 当前价格<网格线）
                # 触发买入逻辑：在网格线附近买入
                price_crossed_down = (last_price > grid_price) and (current_price <= grid_price)

                # 检测价格从下方上穿网格线（上一价格<网格线 且 当前价格>网格线）
                # 触发卖出逻辑：在网格线附近卖出（平仓）
                price_crossed_up = (last_price < grid_price) and (current_price >= grid_price)

                # 【买入逻辑】价格下穿网格线且该层没有持仓
                if price_crossed_down and not grid_has_position[grid_price]:
                    # 检查总持仓是否超过上限
                    if total_long < MAX_GRID_POSITION:
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="BUY",
                            offset="OPEN",
                            volume=VOLUME,
                            limit_price=quote.ask_price1  # 以卖一价买入
                        )
                        grid_has_position[grid_price] = True  # 标记该层有持仓
                        total_long += VOLUME  # 更新本地持仓计数
                        print(
                            f"[网格策略] 买入：网格线={grid_price}，"
                            f"当前价={current_price:.2f}，买入{VOLUME}手"
                        )

                # 【卖出逻辑】价格上穿网格线且下方相邻网格有持仓
                if price_crossed_up:
                    # 找下方最近的持仓网格（卖出下方的持仓，实现低买高卖）
                    grid_below = get_grid_below(grid_price, grid_lines)
                    if grid_below is not None and grid_has_position.get(grid_below, False):
                        api.insert_order(
                            symbol=SYMBOL,
                            direction="SELL",
                            offset="CLOSE",
                            volume=VOLUME,
                            limit_price=quote.bid_price1  # 以买一价卖出
                        )
                        grid_has_position[grid_below] = False  # 清除该层持仓状态
                        total_long -= VOLUME
                        profit_estimate = (grid_price - grid_below) * VOLUME
                        print(
                            f"[网格策略] 卖出：网格线={grid_price}，"
                            f"买入层={grid_below}，卖出{VOLUME}手，"
                            f"预估利润≈{profit_estimate}点×合约乘数"
                        )

            # 更新上次价格
            last_price = current_price

            # 定期打印持仓状态
            active_grids = [g for g, has_pos in grid_has_position.items() if has_pos]
            if active_grids:
                print(
                    f"[网格策略] 当前价={current_price:.2f}，"
                    f"持仓网格={active_grids}，总持仓={total_long}手"
                )

except KeyboardInterrupt:
    print("[网格策略] 用户中断，策略停止运行")
finally:
    api.close()
    print("[网格策略] API连接已关闭")
