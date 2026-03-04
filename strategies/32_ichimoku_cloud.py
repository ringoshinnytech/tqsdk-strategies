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

策略名称：Ichimoku Cloud 一目均衡表策略
策略编号：32
作者：TqSdk 策略库
更新日期：2026-03-03

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【策略背景与原理】

Ichimoku Cloud（一目均衡表），又称 Ichimoku Kinko Hyo，是日本著名分析师
细田悟一（Goichi Hosoda）于 1930 年代创立的技术分析系统。该指标在日本
被誉为"一目了然"的分析工具，能够在单一图表中同时提供趋势判断、支撑阻力
识别、动量信号等多维信息，是日本蜡烛图技术的重要补充。

Ichimoku Cloud 的核心设计理念是通过多条曲线的交叉关系和"云层"的遮挡
效果，直观展示市场的多空力量对比和时间周期关系。与传统单一指标相比，
它具有以下独特优势：

  1. 全方位市场视角：同时展示趋势方向、动量强弱、支撑阻力、进出时机
  2. 多时间周期融合：基准线和转换线的交叉反映短期与中期趋势的互动
  3. 云层过滤机制：价格位于云层上方为多头格局，下方为空头格局
  4. 延迟线（Chikou Span）验证：利用"以今论古"的思路验证趋势可靠性

【Ichimoku 五大要素详解】

本策略使用 Ichimoku Cloud 的五个核心组件：

  1. 转换线（Tenkan-Sen，转换线）：
     计算：(9日最高价 + 9日最低价) / 2
     作用：反映短期趋势动向，类似快速移动平均线

  2. 基准线（Kijun-Sen，基准线）：
     计算：(26日最高价 + 26日最低价) / 2
     作用：反映中期趋势动向，作为动态支撑/阻力线

  3. 先行带 A（Senkou Span A，先行上线）：
     计算：(转换线 + 基准线) / 2，向前平移 26 日
     作用：云层上边界，反映中期多空平衡点

  4. 先行带 B（Senkou Span B，先行下线）：
     计算：(52日最高价 + 52日最低价) / 2，向前平移 26 日
     作用：云层下边界，反映长期成本区间

  5. 延迟线（Chikou Span，迟行带）：
     计算：收盘价向后平移 26 日
     作用：验证趋势的可持续性，"以今论古"确认信号

【云层（Kumo）的解读】

  ● 云层厚度：反映多空分歧程度，厚云层提供更强的支撑/阻力
  ● 云层颜色：先行带A > 先行带B 为多头云（绿色），反之为空头云（红色）
  ● 价格与云层：价格位于云上方为强势多头，位于云下方为强势空头
  ● 云层突破：价格突破云层通常预示趋势转换

【策略交易信号】

本策略采用经典的三重确认信号系统：

  1. 转换线/基准线交叉信号：
     - 转换线从下向上穿越基准线 → 金叉 → 做多
     - 转换线从上向下穿越基准线 → 死叉 → 做空

  2. 价格与云层关系过滤：
     - 仅在价格位于云层上方时做多，仅在价格位于云层下方时做空
     - 过滤逆势交易信号，提高信号质量

  3. 延迟线确认：
     - 做多时，延迟线需位于 26 日前价格上方
     - 做空时，延迟线需位于 26 日前价格下方
     - 确认趋势的可持续性

【出场策略】

  1. 跟踪止损：以基准线作为动态止损线，价格向不利方向突破基准线时止损
  2. 趋势反转：出现相反方向的买入/卖出信号时平仓反手
  3. 云层突破：价格突破云层另一侧时平仓

【策略特点】

  1. 多维度确认：三重信号过滤有效减少假突破，提高信号可靠性
  2. 自动趋势识别：云层颜色和位置自动标注市场多空状态
  3. 动态支撑阻力：基准线作为移动止损线，随趋势调整保护位
  4. 适合中长线：26 日参数设计适合波段和趋势跟踪
  5. 直观可视化：云层直观展示支撑阻力区域，新手友好

【适用品种与时间周期】

  推荐品种：趋势明显的品种，如螺纹钢、铁矿石、沪铜、橡胶等
  推荐周期：日线或 4 小时 K 线（可根据品种特性调整参数）
  不适合：长期横盘震荡、成交量低迷的品种

【参数说明】

  SYMBOL         : 目标合约代码
  KLINE_PERIOD   : K 线周期（日/小时/分钟），默认 86400（日线）
  TENKAN_PERIOD  : 转换线周期，默认 9
  KIJUN_PERIOD   : 基准线周期，默认 26
  SENKOU_PERIOD  : 先行带周期，默认 52
  CHIKOU_OFFSET  : 延迟线偏移，默认 26
  LOT_SIZE       : 每次开仓手数

【风险提示】

  1. Ichimoku 在横盘震荡行情中可能产生频繁交叉信号，需结合其他指标过滤
  2. 参数基于日本股市设计，期货市场可根据波动性适当调整（如 17/26/52）
  3. 云层信号存在滞后性，突破时可能已经错过部分行情
  4. 本策略仅供学习参考，实盘请做充分回测和风控验证
"""

import datetime
from tqsdk import TqApi, TqAuth, TqSim, BacktestFinished

# ─────────────────────────────────────────────
# 策略参数
# ─────────────────────────────────────────────
SYMBOL = "KQ.m@SHFE.rb"      # 螺纹钢主力合约（自动展期）
KLINE_PERIOD = 86400         # 日线 K 线（86400 秒 = 1 天）
TENKAN_PERIOD = 9            # 转换线周期（短期）
KIJUN_PERIOD = 26            # 基准线周期（中期）
SENKOU_PERIOD = 52           # 先行带周期（长期）
CHIKOU_OFFSET = 26           # 延迟线偏移
LOT_SIZE = 1                 # 每次开仓手数


class IchimokuCloud:
    """
    Ichimoku Cloud（一目均衡表）指标计算器。

    五大组件：
      tenkan_sen  : 转换线（9日高低点均值）
      kijun_sen   : 基准线（26日高低点均值）
      senkou_a    : 先行上线（转换线与基准线的均值，向前平移26日）
      senkou_b    : 先行下线（52日高低点均值，向前平移26日）
      chikou_span : 延迟线（收盘价向后平移26日）

    云层（Kumo）：senkou_a 与 senkou_b 之间的区域
    """

    def __init__(self, tenkan_period: int = 9, kijun_period: int = 26,
                 senkou_period: int = 52, chikou_offset: int = 26):
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_period = senkou_period
        self.chikou_offset = chikou_offset

        # 指标缓存
        self.tenkan_sen = None      # 转换线
        self.kijun_sen = None        # 基准线
        self.senkou_a = None         # 先行上线 A
        self.senkou_b = None         # 先行下线 B
        self.chikou_span = None      # 延迟线
        self.cloud_shift_a = None   # 偏移后的先行上线 A（26日后的值）
        self.cloud_shift_b = None   # 偏移后的先行下线 B（26日后的值）

    def _calculate_midprice(self, klines, period: int) -> float | None:
        """计算周期内的最高价和最低价的均值"""
        if len(klines) < period:
            return None
        high = klines["high"].tail(period).max()
        low = klines["low"].tail(period).min()
        return (high + low) / 2.0

    def update(self, klines) -> bool:
        """
        根据最新 K 线数据更新 Ichimoku 指标。

        参数：
            klines: 包含 high, low, close 的 DataFrame

        返回：
            bool: 所有指标计算成功返回 True，否则返回 False
        """
        n = len(klines)
        min_required = max(self.tenkan_period, self.kijun_period,
                          self.senkou_period) + self.chikou_offset

        if n < min_required:
            return False

        # 1. 计算转换线（Tenkan-Sen）：9日周期
        tenkan_mid = self._calculate_midprice(klines, self.tenkan_period)
        if tenkan_mid is None:
            return False
        self.tenkan_sen = tenkan_mid

        # 2. 计算基准线（Kijun-Sen）：26日周期
        kijun_mid = self._calculate_midprice(klines, self.kijun_period)
        if kijun_mid is None:
            return False
        self.kijun_sen = kijun_mid

        # 3. 计算先行上线（Senkou Span A）：(转换线+基准线)/2，平移26日
        senkou_a_mid = (self.tenkan_sen + self.kijun_sen) / 2.0
        # 取 26 日前的值
        if n >= self.chikou_offset + 1:
            self.senkou_a = senkou_a_mid
            # 26 日后的先行上线（用于判断云层方向）
            idx = n - self.chikou_offset - 1
            if idx >= 0:
                past_klines = klines.iloc[:idx+1]
                if len(past_klines) >= 2:
                    past_tenkan = self._calculate_midprice(past_klines, self.tenkan_period)
                    past_kijun = self._calculate_midprice(past_klines, self.kijun_period)
                    if past_tenkan and past_kijun:
                        self.cloud_shift_a = (past_tenkan + past_kijun) / 2.0

        # 4. 计算先行下线（Senkou Span B）：52日周期，平移26日
        senkou_b_mid = self._calculate_midprice(klines, self.senkou_period)
        if senkou_b_mid is None:
            return False
        self.senkou_b = senkou_b_mid
        # 26 日后的先行下线
        idx = n - self.chikou_offset - 1
        if idx >= 0:
            past_klines = klines.iloc[:idx+1]
            if len(past_klines) >= self.senkou_period:
                self.cloud_shift_b = past_klines["high"].tail(self.senkou_period).max() + \
                                     past_klines["low"].tail(self.senkou_period).min()
                self.cloud_shift_b /= 2.0

        # 5. 计算延迟线（Chikou Span）：收盘价向后平移26日
        # 取 26 日前的收盘价
        if n > self.chikou_offset:
            self.chikou_span = klines.iloc[-(self.chikou_offset + 1)]["close"]

        return True

    def get_signal(self, current_price: float, past_price_26: float = None) -> dict:
        """
        获取交易信号。

        参数：
            current_price : 当前价格
            past_price_26 : 26 日前的价格（用于延迟线验证）

        返回：
            dict: 包含信号类型和强度
        """
        if None in (self.tenkan_sen, self.kijun_sen, self.senkou_a,
                   self.senkou_b, self.chikou_span):
            return {"signal": "none", "reason": "指标未就绪"}

        # 云层状态
        cloud_top = max(self.senkou_a, self.senkou_b)
        cloud_bottom = min(self.senkou_a, self.senkou_b)
        cloud_green = self.senkou_a > self.senkou_b  # 多头云

        # 延迟线验证
        chikou_above = past_price_26 is not None and self.chikou_span > past_price_26
        chikou_below = past_price_26 is not None and self.chikou_span < past_price_26

        # ─────────────────────────────────────────
        # 买入信号（做多）
        # ─────────────────────────────────────────
        # 1. 转换线从下向上穿越基准线（金叉）
        # 2. 价格位于云层上方
        # 3. 延迟线位于 26 日前价格上方
        tenkan_cross_up = False  # 需要记录上一根的状态，这里简化处理
        # 简化：以当前价格判断趋势方向
        if current_price > cloud_top:  # 价格在云层上方
            if self.tenkan_sen > self.kijun_sen:  # 转换线 > 基准线
                if chikou_above:  # 延迟线确认
                    return {
                        "signal": "buy",
                        "reason": "转换线>基准线 + 价格>云层 + 延迟线确认"
                    }

        # ─────────────────────────────────────────
        # 卖出信号（做空）
        # ─────────────────────────────────────────
        if current_price < cloud_bottom:  # 价格在云层下方
            if self.tenkan_sen < self.kijun_sen:  # 转换线 < 基准线
                if chikou_below:  # 延迟线确认
                    return {
                        "signal": "sell",
                        "reason": "转换线<基准线 + 价格<云层 + 延迟线确认"
                    }

        # ─────────────────────────────────────────
        # 趋势确认（仅持有，不开仓）
        # ─────────────────────────────────────────
        if current_price > cloud_top and self.tenkan_sen > self.kijun_sen:
            return {"signal": "keep_long", "reason": "多头趋势延续"}

        if current_price < cloud_bottom and self.tenkan_sen < self.kijun_sen:
            return {"signal": "keep_short", "reason": "空头趋势延续"}

        return {"signal": "none", "reason": "无明确信号"}


def main():
    # ─────────────────────────────────────────
    # 初始化 TqApi
    # ─────────────────────────────────────────
    api = TqApi(
        account=TqSim(init_balance=200000),
        auth=TqAuth("your_username", "your_password"),  # 请替换为实际账号
    )

    klines = api.get_kline_serial(SYMBOL, KLINE_PERIOD, data_length=200)
    quote = api.get_quote(SYMBOL)
    account = api.get_account()
    position = api.get_position(SYMBOL)

    print(f"[Ichimoku] 启动策略：{SYMBOL} | 日线周期 | 转换线={TENKAN_PERIOD} | 基准线={KIJUN_PERIOD}")

    ichimoku = IchimokuCloud(
        tenkan_period=TENKAN_PERIOD,
        kijun_period=KIJUN_PERIOD,
        senkou_period=SENKOU_PERIOD,
        chikou_offset=CHIKOU_OFFSET
    )

    # 当前仓位方向（1=多, -1=空, 0=空仓）
    position_side = 0
    last_tenkan = None  # 用于检测转换线与基准线交叉
    last_kijun = None

    try:
        while True:
            api.wait_update()

            # 等待 K 线更新
            if not api.is_changing(klines.iloc[-1], "datetime"):
                continue

            # 取倒数第 2 根（已完成的 K 线）
            bar = klines.iloc[-2]

            # 更新 Ichimoku 指标
            if not ichimoku.update(klines):
                continue

            current_price = quote.last_price
            long_pos = position.pos_long_today + position.pos_long
            short_pos = position.pos_short_today + position.pos_short

            # 获取 26 日前的价格（用于延迟线验证）
            past_price_26 = None
            if len(klines) > CHIKOU_OFFSET + 1:
                past_price_26 = klines.iloc[-(CHIKOU_OFFSET + 1)]["close"]

            # ─────────────────────────────────────────
            # 交叉检测（转换线与基准线）
            # ─────────────────────────────────────────
            tenkan = ichimoku.tenkan_sen
            kijun = ichimoku.kijun_sen
            cross_up = last_tenkan is not None and last_kijun is not None and \
                       last_tenkan <= last_kijun and tenkan > kijun
            cross_down = last_tenkan is not None and last_kijun is not None and \
                         last_tenkan >= last_kijun and tenkan < kijun
            last_tenkan = tenkan
            last_kijun = kijun

            # 获取交易信号
            signal_info = ichimoku.get_signal(current_price, past_price_26)

            # ─────────────────────────────────────────
            # 平仓逻辑（趋势反转或出现相反信号）
            # ─────────────────────────────────────────
            if position_side == 1:
                # 持多时检测卖出信号
                if signal_info["signal"] in ["sell", "none"]:
                    if cross_down or (current_price < ichimoku.kijun_sen and ichimoku.kijun_sen is not None):
                        if long_pos > 0:
                            api.insert_order(SYMBOL, "SELL", "CLOSE", long_pos, quote.bid_price1)
                            print(f"[Ichimoku] 平多 | 价格={current_price:.2f} | 基准线={kijun:.2f} | {signal_info['reason']}")
                            position_side = 0

            elif position_side == -1:
                # 持空时检测买入信号
                if signal_info["signal"] in ["buy", "none"]:
                    if cross_up or (current_price > ichimoku.kijun_sen and ichimoku.kijun_sen is not None):
                        if short_pos > 0:
                            api.insert_order(SYMBOL, "BUY", "CLOSE", short_pos, quote.ask_price1)
                            print(f"[Ichimoku] 平空 | 价格={current_price:.2f} | 基准线={kijun:.2f} | {signal_info['reason']}")
                            position_side = 0

            # ─────────────────────────────────────────
            # 开仓逻辑
            # ─────────────────────────────────────────
            elif position_side == 0:
                # 买入条件：转换线从下穿越基准线 + 价格在云层上方 + 延迟线确认
                if cross_up:
                    cloud_top = max(ichimoku.senkou_a, ichimoku.senkou_b) if ichimoku.senkou_a and ichimoku.senkou_b else None
                    if cloud_top is None or current_price > cloud_top:
                        past_for_chikou = past_price_26 if past_price_26 else (klines.iloc[-30]["close"] if len(klines) > 30 else None)
                        if past_for_chikou and ichimoku.chikou_span and ichimoku.chikou_span > past_for_chikou:
                            api.insert_order(SYMBOL, "BUY", "OPEN", LOT_SIZE, quote.ask_price1)
                            print(f"[Ichimoku] 做多开仓 | 价格={current_price:.2f} | "
                                  f"转换线={tenkan:.2f} | 基准线={kijun:.2f}")
                            position_side = 1

                # 卖出条件：转换线从上穿越基准线 + 价格在云层下方 + 延迟线确认
                elif cross_down:
                    cloud_bottom = min(ichimoku.senkou_a, ichimoku.senkou_b) if ichimoku.senkou_a and ichimoku.senkou_b else None
                    if cloud_bottom is None or current_price < cloud_bottom:
                        past_for_chikou = past_price_26 if past_price_26 else (klines.iloc[-30]["close"] if len(klines) > 30 else None)
                        if past_for_chikou and ichimoku.chikou_span and ichimoku.chikou_span < past_for_chikou:
                            api.insert_order(SYMBOL, "SELL", "OPEN", LOT_SIZE, quote.bid_price1)
                            print(f"[Ichimoku] 做空开仓 | 价格={current_price:.2f} | "
                                  f"转换线={tenkan:.2f} | 基准线={kijun:.2f}")
                            position_side = -1

    except BacktestFinished:
        bal = account.balance
        mdd = account.max_drawdown
        print("\n════════════════════════════════════")
        print(f"[Ichimoku] 回测结束")
        print(f"  最终权益：{bal:.2f}")
        print(f"  最大回撤：{mdd:.2f}%")
        print("════════════════════════════════════")
    finally:
        api.close()


if __name__ == "__main__":
    main()
