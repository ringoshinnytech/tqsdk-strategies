#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双均线趋势跟踪策略 (Double Moving Average Strategy)
====================================================

策略逻辑：
    - 使用短期均线（MA5）和长期均线（MA20）的交叉信号判断趋势方向
    - 金叉（短均线从下方向上穿越长均线）：开多头仓位
    - 死叉（短均线从上方向下穿越长均线）：开空头仓位
    - 反向信号出现时先平旧仓再开新仓

适用品种：
    趋势性较强的品种，如螺纹钢（SHFE.rb）、原油（INE.sc）、铜（SHFE.cu）等

风险提示：
    - 均线策略在震荡行情中容易产生频繁的假信号（亏损）
    - 建议结合成交量、波动率等过滤器使用
    - 本代码仅供学习参考，不构成任何投资建议

参数说明：
    SYMBOL      : 交易合约代码，格式为 "交易所.合约代码"
    SHORT_PERIOD: 短期均线周期（K线根数）
    LONG_PERIOD : 长期均线周期（K线根数）
    KLINE_DUR   : K线周期（秒），60=1分钟K线，3600=1小时K线
    VOLUME      : 每次开仓手数

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
"""

from tqsdk import TqApi, TqAuth, TqSim
from tqsdk.tafunc import ma, crossup, crossdown

# ===================== 策略参数 =====================
SYMBOL = "SHFE.rb2501"     # 交易合约：上期所螺纹钢2501合约
SHORT_PERIOD = 5            # 短期均线周期：5根K线
LONG_PERIOD = 20            # 长期均线周期：20根K线
KLINE_DUR = 60 * 60         # K线周期：3600秒 = 1小时K线
VOLUME = 1                  # 每次开仓手数

# ===================================================


def main():
    """
    策略主函数

    使用 TqSim 进行模拟回测，如需实盘请替换为:
        TqAccount("期货公司名称", "资金账号", "交易密码")
    并在 TqApi 中传入 auth=TqAuth("快期账号", "快期密码")
    """

    # 初始化 API：使用模拟账户进行策略测试
    # 如需实盘，请替换 TqSim() 为实际账户，并填入快期认证
    api = TqApi(
        account=TqSim(),                      # 使用内置模拟账户
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),  # 替换为你的快期账户
    )

    # 订阅 K 线数据：获取最近 LONG_PERIOD+10 根 K 线用于计算均线
    # get_kline_serial 返回 pandas.DataFrame，包含 open/high/low/close/volume 等字段
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=LONG_PERIOD + 10)

    # 获取持仓引用：用于查看当前净持仓（多头-空头）
    position = api.get_position(SYMBOL)

    print(f"[策略启动] 双均线策略 | 合约: {SYMBOL} | 短周期: {SHORT_PERIOD} | 长周期: {LONG_PERIOD}")

    while True:
        # 等待行情数据更新（阻塞直到有新数据）
        api.wait_update()

        # 仅在 K 线有更新时重新计算信号，避免重复计算
        if not api.is_changing(klines):
            continue

        # ---- 计算技术指标 ----
        # ma() 返回 pandas.Series，每个元素是对应时刻的均线值
        ma_short = ma(klines.close, SHORT_PERIOD)   # 短期均线序列
        ma_long = ma(klines.close, LONG_PERIOD)     # 长期均线序列

        # crossup(a, b)：a 向上穿越 b 时最后一根值为 1，否则为 0
        # crossdown(a, b)：a 向下穿越 b 时最后一根值为 1，否则为 0
        is_golden_cross = crossup(ma_short, ma_long).iloc[-1]   # 金叉信号
        is_death_cross = crossdown(ma_short, ma_long).iloc[-1]  # 死叉信号

        # 当前净持仓：正数=多头，负数=空头，0=空仓
        # volume_long / volume_short 分别为总多头/空头持仓手数
        net_pos = position.volume_long - position.volume_short

        # 打印当前状态（调试用）
        print(
            f"最新价: {klines.close.iloc[-1]:.2f} | "
            f"MA{SHORT_PERIOD}: {ma_short.iloc[-1]:.2f} | "
            f"MA{LONG_PERIOD}: {ma_long.iloc[-1]:.2f} | "
            f"净持仓: {net_pos}"
        )

        # ---- 交易信号处理 ----

        if is_golden_cross:
            # 金叉：短均线上穿长均线 → 趋势向上，做多
            print(">>> 金叉信号！做多开仓")

            if net_pos < 0:
                # 当前持有空头，先平空再做多
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",    # 买入
                    offset="CLOSE",     # 平仓
                    volume=abs(net_pos) # 平掉所有空头
                )

            if net_pos <= 0:
                # 开多头仓位
                api.insert_order(
                    symbol=SYMBOL,
                    direction="BUY",    # 买入
                    offset="OPEN",      # 开仓
                    volume=VOLUME       # 开仓手数
                )

        elif is_death_cross:
            # 死叉：短均线下穿长均线 → 趋势向下，做空
            print(">>> 死叉信号！做空开仓")

            if net_pos > 0:
                # 当前持有多头，先平多再做空
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",   # 卖出
                    offset="CLOSE",     # 平仓
                    volume=net_pos      # 平掉所有多头
                )

            if net_pos >= 0:
                # 开空头仓位
                api.insert_order(
                    symbol=SYMBOL,
                    direction="SELL",   # 卖出
                    offset="OPEN",      # 开仓
                    volume=VOLUME       # 开仓手数
                )

    # 关闭 API 连接（正常情况下不会到达这里）
    api.close()


if __name__ == "__main__":
    main()
