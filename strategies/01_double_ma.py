#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双均线趋势跟踪策略 (Double Moving Average Strategy)
====================================================

策略逻辑：
    - 使用短期均线（MA5）和长期均线（MA20）的交叉信号判断趋势方向
    - 金叉（短均线从下方向上穿越长均线）：目标仓位设为 +VOLUME（做多）
    - 死叉（短均线从上方向下穿越长均线）：目标仓位设为 -VOLUME（做空）
    - 使用 TargetPosTask 管理持仓，无需手动处理追单、撤单、部分成交等细节

【为什么用 TargetPosTask 而不是 insert_order】
    insert_order 只是"发一笔委托"，策略需要自己跟踪订单状态：
      - 委托未成交怎么办？追单？改价？
      - 部分成交时剩余量如何处理？
      - 反手时先撤未成交的单？
    TargetPosTask 封装了这一切：
      - 只需告诉它"我现在想持有多少手"
      - 它自动计算需要买卖的数量，并持续追单直到达到目标仓位
      - 目标仓位改变时会自动撤掉旧委托再按新目标下单
      - 正数 = 多头 N 手，负数 = 空头 N 手，0 = 全部平仓

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
    VOLUME      : 持仓手数（目标仓位的绝对值）

依赖：
    pip install tqsdk -U

作者：tqsdk-strategies
文档：https://doc.shinnytech.com/tqsdk/latest/
      https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.api.TqApi.TargetPosTask
"""

from tqsdk import TqApi, TqAuth, TqSim, TargetPosTask
from tqsdk.tafunc import ma, crossup, crossdown

# ===================== 策略参数 =====================
SYMBOL = "SHFE.rb2501"     # 交易合约：上期所螺纹钢2501合约
SHORT_PERIOD = 5            # 短期均线周期：5根K线
LONG_PERIOD = 20            # 长期均线周期：20根K线
KLINE_DUR = 60 * 60         # K线周期：3600秒 = 1小时K线
VOLUME = 1                  # 持仓手数（正数=多头，负数=空头，0=空仓）
# ===================================================


def main():
    """
    策略主函数

    使用 TqSim 进行模拟交易，如需实盘请替换为:
        TqAccount("期货公司名称", "资金账号", "交易密码")
    并在 TqApi 中传入 auth=TqAuth("快期账号", "快期密码")
    """

    # 初始化 API：使用模拟账户进行策略测试
    api = TqApi(
        account=TqSim(),
        auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD"),
    )

    # 订阅 K 线数据
    klines = api.get_kline_serial(SYMBOL, KLINE_DUR, data_length=LONG_PERIOD + 10)

    # ===== TargetPosTask 初始化 =====
    # 在主循环外创建，每个合约对应一个实例
    # 它会在后台持续管理委托，确保实际持仓趋向目标仓位
    target_pos = TargetPosTask(api, SYMBOL)
    # ================================

    print(f"[策略启动] 双均线策略 | 合约: {SYMBOL} | 短周期: {SHORT_PERIOD} | 长周期: {LONG_PERIOD}")

    while True:
        # 等待行情数据更新
        api.wait_update()

        # 仅在 K 线有更新时重新计算信号
        if not api.is_changing(klines):
            continue

        # ---- 计算技术指标 ----
        ma_short = ma(klines.close, SHORT_PERIOD)   # 短期均线序列
        ma_long = ma(klines.close, LONG_PERIOD)     # 长期均线序列

        is_golden_cross = crossup(ma_short, ma_long).iloc[-1]   # 金叉信号
        is_death_cross = crossdown(ma_short, ma_long).iloc[-1]  # 死叉信号

        print(
            f"最新价: {klines.close.iloc[-1]:.2f} | "
            f"MA{SHORT_PERIOD}: {ma_short.iloc[-1]:.2f} | "
            f"MA{LONG_PERIOD}: {ma_long.iloc[-1]:.2f}"
        )

        # ---- 交易信号处理（用 TargetPosTask 设置目标仓位）----

        if is_golden_cross:
            # 金叉：趋势向上 → 目标仓位设为 +VOLUME（多头）
            # TargetPosTask 会自动：平掉空仓（若有）+ 买入到目标手数
            print(f">>> 金叉！目标仓位: +{VOLUME}（做多）")
            target_pos.set_target_volume(VOLUME)

        elif is_death_cross:
            # 死叉：趋势向下 → 目标仓位设为 -VOLUME（空头）
            # TargetPosTask 会自动：平掉多仓（若有）+ 卖出到目标手数
            print(f">>> 死叉！目标仓位: -{VOLUME}（做空）")
            target_pos.set_target_volume(-VOLUME)

    api.close()


if __name__ == "__main__":
    main()
