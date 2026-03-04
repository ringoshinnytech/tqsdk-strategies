"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【关于 TqSdk —— 天勤量化开发包】

TqSdk 是由信易科技发起并开源的 Python 量化交易框架，专为国内期货市场设计，
是国内最主流的期货量化开发工具之一。

核心优势：
  ● 极简代码：几十行即可构建完整策略，内置 MA/MACD/BOLL/RSI/ATR 等近百个技术指标
  ● 全品种实时行情：期货、期权、股票，毫秒级推送，数据全在内存，零延迟
  ● 全流程支持：历史回测 → 模拟交易 → 实盘交易 → 运行监控，一套 API 全覆盖
  ● 广泛兼容：支持 90%+ 期货公司 CTP 直连及主流资管柜台
  ● Pandas 友好：K 线 / Tick 数据直接返回 DataFrame，与 NumPy 无缝配合

官方资源：
  📘 官方文档：https://doc.shinnytech.com/tqsdk/latest/
  🐙 GitHub  ：https://github.com/shinnytech/tqsdk-python
  🧑‍💻 账户注册：https://account.shinnytech.com/
  💬 用户社区：https://www.shinnytech.com/qa/

安装：pip install tqsdk -U
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

策略名称：线性回归通道突破策略
策略编号：32
作者：TqSdk 策略库
更新日期：2026-03-02

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

线性回归通道（Linear Regression Channel）是一种基于统计学的趋势分析工具，
在技术分析领域广受学术机构和专业交易员的推崇。它通过对历史价格序列做最小二乘
线性回归，得出当前市场价格的"内在趋势方向"，并以标准误差构建上下通道带，
从而区分价格的正常波动范围与突破性行情。

与布林带（Bollinger Bands）相比，线性回归通道的关键区别在于：
  · 布林带以移动平均（MA）为中轴，对历史价格等权重平均，存在较大滞后；
  · 线性回归通道以最小二乘拟合直线为中轴，能更准确地刻画"当前趋势斜率"，
    对最新价格赋予更高的统计权重，信号更灵敏、方向性更强。

【核心计算公式】

给定过去 N 根 K 线的收盘价序列 {y₀, y₁, ..., y_{N-1}}（y_{N-1} 为最新）：

  1. 线性回归拟合：
     y = a + b·x，其中 x = 0, 1, 2, ..., N-1

     斜率 b = [N·Σ(x·y) - Σx·Σy] / [N·Σx² - (Σx)²]
     截距 a = (Σy - b·Σx) / N

  2. 回归中轨（Linear Regression Line，最新一点值）：
     LR_MID = a + b·(N-1)

  3. 标准误差（Standard Error of Regression）：
     SE = sqrt[Σ(y - ŷ)² / (N - 2)]

  4. 上下通道：
     LR_UPPER = LR_MID + k·SE
     LR_LOWER = LR_MID - k·SE
     其中 k 为通道倍数参数，默认为 2.0

【交易逻辑】

本策略结合"趋势突破"和"通道内均值回归"两种模式：

  模式一：趋势突破（主要信号）
    当价格由通道内向上突破上轨时：
      → 表明多头力量强劲，突破了统计上的"合理高点" → 做多
    当价格由通道内向下突破下轨时：
      → 表明空头力量主导，跌破了统计上的"合理低点" → 做空

  模式二：回归中轨止盈
    持多仓时，价格回落至中轨附近（± 0.3·SE）→ 止盈平仓
    持空仓时，价格回升至中轨附近（± 0.3·SE）→ 止盈平仓

  止损逻辑：
    反向突破 1.0·SE 时强制止损，防止趋势完全反转后仍持有方向错误的仓位

  斜率过滤（可选）：
    只有当回归线斜率方向与突破方向一致时才入场，避免逆势突破带来的假信号

【策略特点与优势】

  1. 统计学根基扎实：最小二乘法是数学上"最优线性无偏估计量（BLUE）"，
     通道带具有明确的统计意义（类似 2σ 置信区间）；
  2. 自适应趋势感知：斜率 b 实时反映价格动量方向和强度，正斜率表示上升趋势，
     负斜率表示下降趋势，绝对值越大趋势越强；
  3. 兼顾趋势与震荡：在趋势明显时做突破，在震荡市场可配合中轨回归策略；
  4. 与布林带互补：可与布林带策略组合，用回归通道过滤布林带假突破信号。

【适用品种与参数推荐】

  推荐品种：日线级别的中低频趋势策略，适合螺纹钢(rb)、铁矿石(i)、
            豆粕(m)、甲醇(MA)等工业品/农产品主力合约。
  推荐周期：60 分钟 K 线（日内中频），或日线级别长期持仓。
  LR_PERIOD   : 回归周期，推荐 20–40 根 K 线（太短噪音大，太长滞后重）
  CHANNEL_K   : 通道倍数，推荐 1.5–2.5，根据品种波动率调整
  LOT_SIZE    : 开仓手数，根据账户资金和合约保证金调整

【风险提示】

  1. 线性回归假设价格趋势在回看窗口内为线性，强非线性行情（如 V 型反转）
     会导致信号严重失真，建议配合成交量过滤；
  2. 频繁重新计算回归会消耗一定计算资源，建议 K 线周期不低于 30 分钟；
  3. 重大宏观事件（如 FOMC、美联储议息、大宗商品产量报告）发布当日慎用；
  4. 本策略仅供学习研究使用，实盘前请做充分回测和参数优化。
"""

import numpy as np
from tqsdk import TqApi, TqAuth, TqSim, BacktestFinished
from tqsdk.tafunc import sma

# ─────────────────────────────────────────────
# 策略参数
# ─────────────────────────────────────────────
SYMBOL = "KQ.m@SHFE.rb"     # 螺纹钢主力合约（自动展期）
KLINE_PERIOD = 3600          # K 线周期：3600 秒 = 60 分钟
LR_PERIOD = 30               # 线性回归计算窗口（根 K 线数量）
CHANNEL_K = 2.0              # 通道宽度倍数（标准误差的倍数）
EXIT_K = 0.3                 # 回归中轨平仓阈值（中轨 ± EXIT_K × SE）
STOP_K = 1.0                 # 止损阈值（突破方向反向 STOP_K × SE 时止损）
LOT_SIZE = 1                 # 每次开仓手数
SLOPE_FILTER = True          # 是否启用斜率方向过滤


def linear_regression_channel(closes: np.ndarray):
    """
    计算线性回归通道（最小二乘法）。

    参数：
        closes  : 价格序列，np.ndarray，最新价格在末尾

    返回：
        mid     : 回归线最新点的预测价格
        upper   : 上轨（mid + CHANNEL_K × SE）
        lower   : 下轨（mid - CHANNEL_K × SE）
        slope   : 回归斜率（正值=上升趋势，负值=下降趋势）
        se      : 标准误差
    """
    n = len(closes)
    x = np.arange(n, dtype=float)
    y = closes

    # 普通最小二乘回归
    x_mean = x.mean()
    y_mean = y.mean()
    ss_xx = np.sum((x - x_mean) ** 2)
    ss_xy = np.sum((x - x_mean) * (y - y_mean))

    if ss_xx < 1e-10:
        return None, None, None, None, None

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    # 预测值与标准误差
    y_pred = intercept + slope * x
    residuals = y - y_pred

    # 标准误差 SE（自由度 = n - 2）
    if n > 2:
        se = np.sqrt(np.sum(residuals ** 2) / (n - 2))
    else:
        se = 0.0

    # 回归线最新一点
    mid = intercept + slope * (n - 1)
    upper = mid + CHANNEL_K * se
    lower = mid - CHANNEL_K * se

    return mid, upper, lower, slope, se


def main():
    # ─────────────────────────────────────────
    # 初始化 TqApi（使用模拟账户）
    # ─────────────────────────────────────────
    api = TqApi(
        account=TqSim(init_balance=500000),
        auth=TqAuth("your_username", "your_password"),   # 请替换为实际账号
    )

    # 获取 K 线数据（需要 LR_PERIOD + 缓冲，取 200 根）
    klines = api.get_kline_serial(SYMBOL, KLINE_PERIOD, data_length=200)
    quote = api.get_quote(SYMBOL)
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(f"[线性回归通道] 启动策略：{SYMBOL}")
    print(f"  回归周期={LR_PERIOD} | 通道倍数={CHANNEL_K} | 斜率过滤={SLOPE_FILTER}")

    # 持仓方向：1=多, -1=空, 0=空仓
    position_side = 0

    # 记录上一根 K 线的通道状态
    prev_above_upper = False
    prev_below_lower = False

    try:
        while True:
            api.wait_update()

            # 仅在有新完成的 K 线时触发计算
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue

            # 确保有足够数据
            close_series = klines["close"].dropna().values
            if len(close_series) < LR_PERIOD + 5:
                continue

            # 取最近 LR_PERIOD 根已完成 K 线的收盘价
            closes = close_series[-(LR_PERIOD + 1):-1]   # 排除最新未完成 K 线

            mid, upper, lower, slope, se = linear_regression_channel(closes)

            if mid is None or se < 1e-6:
                continue

            current_price = quote.last_price
            if current_price != current_price:   # NaN 检查
                continue

            long_pos = position.pos_long_today + position.pos_long
            short_pos = position.pos_short_today + position.pos_short

            # 当前价格相对通道的位置
            above_upper = current_price > upper
            below_lower = current_price < lower
            near_mid = abs(current_price - mid) <= EXIT_K * se

            # ─────────────────────────────────────────
            # 止损逻辑（反向突破止损）
            # ─────────────────────────────────────────
            if position_side == 1:
                # 持多时，若价格跌破下轨 → 止损
                stop_price = mid - STOP_K * se
                if current_price < stop_price and long_pos > 0:
                    api.insert_order(SYMBOL, "SELL", "CLOSE", long_pos, quote.bid_price1)
                    print(f"[线性回归通道] 止损平多 price={current_price:.2f} "
                          f"stop={stop_price:.2f} mid={mid:.2f}")
                    position_side = 0
                    prev_above_upper = False

            elif position_side == -1:
                # 持空时，若价格突破上轨 → 止损
                stop_price = mid + STOP_K * se
                if current_price > stop_price and short_pos > 0:
                    api.insert_order(SYMBOL, "BUY", "CLOSE", short_pos, quote.ask_price1)
                    print(f"[线性回归通道] 止损平空 price={current_price:.2f} "
                          f"stop={stop_price:.2f} mid={mid:.2f}")
                    position_side = 0
                    prev_below_lower = False

            # ─────────────────────────────────────────
            # 平仓逻辑（回归至中轨附近）
            # ─────────────────────────────────────────
            if position_side == 1 and near_mid and long_pos > 0:
                api.insert_order(SYMBOL, "SELL", "CLOSE", long_pos, quote.bid_price1)
                print(f"[线性回归通道] 多头回归中轨平仓 price={current_price:.2f} mid={mid:.2f}")
                position_side = 0
                prev_above_upper = False

            elif position_side == -1 and near_mid and short_pos > 0:
                api.insert_order(SYMBOL, "BUY", "CLOSE", short_pos, quote.ask_price1)
                print(f"[线性回归通道] 空头回归中轨平仓 price={current_price:.2f} mid={mid:.2f}")
                position_side = 0
                prev_below_lower = False

            # ─────────────────────────────────────────
            # 开仓逻辑（价格突破通道上下轨）
            # ─────────────────────────────────────────
            if position_side == 0:

                # 做多条件：价格由通道内向上突破上轨
                if above_upper and not prev_above_upper:
                    # 斜率过滤：只有上升趋势才做多突破
                    if not SLOPE_FILTER or slope > 0:
                        api.insert_order(SYMBOL, "BUY", "OPEN", LOT_SIZE, quote.ask_price1)
                        print(f"[线性回归通道] 做多突破上轨 price={current_price:.2f} "
                              f"upper={upper:.2f} mid={mid:.2f} slope={slope:.4f}")
                        position_side = 1

                # 做空条件：价格由通道内向下突破下轨
                elif below_lower and not prev_below_lower:
                    # 斜率过滤：只有下降趋势才做空突破
                    if not SLOPE_FILTER or slope < 0:
                        api.insert_order(SYMBOL, "SELL", "OPEN", LOT_SIZE, quote.bid_price1)
                        print(f"[线性回归通道] 做空突破下轨 price={current_price:.2f} "
                              f"lower={lower:.2f} mid={mid:.2f} slope={slope:.4f}")
                        position_side = -1

            # 更新上根 K 线状态（用于下次突破判断）
            prev_above_upper = above_upper
            prev_below_lower = below_lower

            # 打印状态（每根 K 线输出）
            print(
                f"[线性回归通道] mid={mid:.2f} upper={upper:.2f} lower={lower:.2f} "
                f"slope={slope:.4f} se={se:.2f} price={current_price:.2f} "
                f"pos={position_side}"
            )

    except BacktestFinished:
        bal = account.balance
        print("\n════════════════════════════════════")
        print(f"[线性回归通道] 回测结束 | 最终权益: {bal:.2f}")
        print("════════════════════════════════════")
    finally:
        api.close()


if __name__ == "__main__":
    main()
