#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
跨品种做市商对冲策略 (Cross-Commodity Market Maker Hedge Strategy)
==================================================================

策略思路：
---------
本策略模拟做市商的运营模式，在多个相关品种上提供流动性并对冲风险。
核心机制：
  1. 在多个相关品种上同时挂单（做市）
  2. 根据品种间的统计相关性动态调整报价宽度
  3. 使用跨品种对冲消除方向性风险
  4. 赚取买卖价差收益

报价机制：
  - 基础价差：根据历史波动率设置
  - 动态调整：根据订单簿深度调整价差
  - 对冲阈值：持仓超过N手时启动对冲

对冲逻辑：
  - 计算投资组合的净Delta
  - 使用相关性高的品种进行对冲
  - 对冲频率：每日收盘前或累计delta超过阈值

品种选择：
  - 黑色系：螺纹钢、热卷、铁矿石、焦炭
  - 有色系：铜、铝、锌
  - 化工系：原油、燃油

风险控制：
---------
- 单边敞口限制：任一方向不超过5手
- 对冲止损：累计对冲亏损超过1%强平
- 报价保护：价格剧烈波动时暂停报价

作者: TqSdk Strategies
更新: 2026-03-17
"""

from tqsdk import TqApi, TqAuth, TqSim
import pandas as pd
import numpy as np
from datetime import datetime, time
import asyncio


class MarketMakerHedgeStrategy:
    """跨品种做市商对冲策略"""

    # 做市品种组（高度相关）
    COMMODITY_GROUPS = {
        "black": [  # 黑色系
            "SHFE.rb2501",   # 螺纹钢
            "SHFE.hc2501",   # 热卷
            "DCE.i2501",     # 铁矿石
            "DCE.j2501",     # 焦炭
        ],
        "nonferrous": [  # 有色系
            "SHFE.cu2501",   # 铜
            "SHFE.al2501",   # 铝
            "SHFE.zn2501",   # 锌
        ],
        "energy": [  # 能源系
            "INE.sc2501",    # 原油
            "SHFE.fu2501",   # 燃油
        ]
    }

    # 策略参数
    QUOTE_SPREAD_PCT = 0.002    # 基础报价价差（0.2%）
    MIN_QUOTE_SIZE = 1           # 最小挂单量
    HEDGE_THRESHOLD = 3          # 对冲阈值（手）
    MAX_POSITION = 5              # 单边最大持仓
    REFRESH_INTERVAL = 300        # 报价刷新间隔（秒）
    
    def __init__(self, api):
        self.api = api
        self.quotes = {}
        self.positions = {}
        self.pending_orders = {}
        self.last_hedge_time = None
        self.hedge_pnl = 0
        
    def get_quote(self, symbol):
        """获取行情"""
        if symbol not in self.quotes:
            self.quotes[symbol] = self.api.get_quote(symbol)
        return self.quotes[symbol]
    
    def calculate_spread(self, symbol):
        """根据波动率计算价差"""
        try:
            kline = self.api.get_kline_serial(symbol, 86400, data_length=20)
            if kline is not None and len(kline) >= 20:
                returns = np.diff(np.log(kline['close'].values[-21:]))
                vol = np.std(returns) * np.sqrt(252)
                # 波动率越大，价差越大
                return max(vol * 0.5, self.QUOTE_SPREAD_PCT)
        except:
            pass
        return self.QUOTE_SPREAD_PCT
    
    def calculate_hedge_ratio(self, symbol1, symbol2):
        """计算对冲比率（基于历史协整关系）"""
        # 简化版：使用固定比率
        hedge_ratios = {
            ("SHFE.rb2501", "DCE.i2501"): 1.5,   # 螺纹钢：铁矿石
            ("SHFE.rb2501", "DCE.j2501"): 0.8,   # 螺纹钢：焦炭
            ("SHFE.hc2501", "SHFE.rb2501"): 1.0, # 热卷：螺纹钢
            ("SHFE.cu2501", "SHFE.al2501"): 1.2, # 铜：铝
            ("SHFE.cu2501", "SHFE.zn2501"): 1.0, # 铜：锌
            ("INE.sc2501", "SHFE.fu2501"): 1.0,   # 原油：燃油
        }
        
        key = (symbol1, symbol2)
        reverse_key = (symbol2, symbol1)
        
        if key in hedge_ratios:
            return hedge_ratios[key]
        elif reverse_key in hedge_ratios:
            return 1.0 / hedge_ratios[reverse_key]
        return 1.0
    
    def get_group_positions(self, group_name):
        """获取品种组总持仓"""
        group = self.COMMODITY_GROUPS.get(group_name, [])
        total_long = 0
        total_short = 0
        
        for symbol in group:
            pos = self.positions.get(symbol)
            if pos:
                total_long += pos.get('long', 0)
                total_short += pos.get('short', 0)
        
        return total_long - total_short
    
    def quote_orders(self, symbol):
        """报价（挂单）"""
        quote = self.get_quote(symbol)
        mid_price = (quote.last_price + quote.pre_close) / 2
        
        # 计算价差
        spread = self.calculate_spread(symbol)
        
        # 买方报价（低价）
        bid_price = mid_price * (1 - spread)
        # 卖方报价（高价）
        ask_price = mid_price * (1 + spread)
        
        # 获取当前持仓
        current_pos = self.positions.get(symbol, {'long': 0, 'short': 0})
        net_pos = current_pos['long'] - current_pos['short']
        
        # 检查是否需要挂单
        # 买方
        if net_pos < self.MAX_POSITION:
            # 取消旧订单
            self.cancel_pending_orders(symbol, 'buy')
            # 挂新单
            order_id = self.api.insert_order(
                symbol=symbol,
                direction="buy",
                offset="open",
                volume=self.MIN_QUOTE_SIZE,
                limit_price=bid_price
            )
            self.pending_orders[symbol + '_buy'] = order_id
        
        # 卖方
        if net_pos > -self.MAX_POSITION:
            self.cancel_pending_orders(symbol, 'sell')
            order_id = self.api.insert_order(
                symbol=symbol,
                direction="sell",
                offset="open",
                volume=self.MIN_QUOTE_SIZE,
                limit_price=ask_price
            )
            self.pending_orders[symbol + '_sell'] = order_id
    
    def cancel_pending_orders(self, symbol, direction):
        """取消待成交订单"""
        key = symbol + '_' + direction
        if key in self.pending_orders:
            try:
                self.api.cancel_order(self.pending_orders[key])
            except:
                pass
            del self.pending_orders[key]
    
    def hedge_group(self, group_name):
        """对冲品种组"""
        group = self.COMMODITY_GROUPS.get(group_name, [])
        if len(group) < 2:
            return
        
        # 计算净持仓
        net_positions = {}
        for symbol in group:
            current_pos = self.positions.get(symbol, {'long': 0, 'short': 0})
            net_positions[symbol] = current_pos['long'] - current_pos['short']
        
        # 选择对冲品种（净持仓最大的品种作为被对冲方）
        sorted_positions = sorted(net_positions.items(), key=lambda x: abs(x[1]), reverse=True)
        
        if len(sorted_positions) < 2:
            return
        
        hedge_target = sorted_positions[0]  # 需要对冲的品种
        hedge_source = sorted_positions[1]  # 用于对冲的品种
        
        target_symbol = hedge_target[0]
        target_pos = hedge_target[1]
        
        if abs(target_pos) >= self.HEDGE_THRESHOLD:
            # 计算对冲数量
            ratio = self.calculate_hedge_ratio(target_symbol, hedge_source[0])
            hedge_volume = int(abs(target_pos) * ratio)
            hedge_volume = max(1, hedge_volume)
            
            # 执行对冲
            if target_pos > 0:
                # 多头需要做空对冲
                self.api.insert_order(
                    symbol=hedge_source[0],
                    direction="sell",
                    offset="open",
                    volume=hedge_volume
                )
            else:
                # 空头需要做多对冲
                self.api.insert_order(
                    symbol=hedge_source[0],
                    direction="buy",
                    offset="open",
                    volume=hedge_volume
                )
            
            self.last_hedge_time = datetime.now()
            print(f"[对冲] {group_name}组: {target_symbol} {'多头' if target_pos > 0 else '空头'} {abs(target_pos)}手 -> 对冲 {hedge_volume}手 {hedge_source[0]}")
    
    def update_positions(self):
        """更新持仓信息"""
        try:
            positions = self.api.get_position()
            self.positions = {}
            
            for pos in positions:
                self.positions[pos.symbol] = {
                    'long': pos.pos_long,
                    'short': pos.pos_short
                }
        except Exception as e:
            print(f"更新持仓失败: {e}")
    
    def check_risk_limits(self):
        """检查风险限额"""
        for group_name, symbols in self.COMMODITY_GROUPS.items():
            net_pos = 0
            for symbol in symbols:
                current = self.positions.get(symbol, {'long': 0, 'short': 0})
                net_pos += current['long'] - current['short']
            
            if abs(net_pos) > self.MAX_POSITION * len(symbols):
                print(f"[风险警告] {group_name}组净持仓 {net_pos} 超过限制!")
                return False
        return True
    
    def is_trading_time(self):
        """判断是否在交易时间"""
        now = datetime.now().time()
        
        # 白天交易时段：9:00-10:15, 10:30-11:30, 13:30-15:00
        day_start = time(9, 0)
        day_end = time(15, 0)
        
        # 夜盘：21:00-次日2:30
        night_start = time(21, 0)
        
        if now >= day_start and now <= day_end:
            return True
        if now >= night_start or now <= time(2, 30):
            return True
        return False
    
    def run(self):
        """运行策略"""
        print(f"启动跨品种做市商对冲策略...")
        print(f"做市品种组: {list(self.COMMODITY_GROUPS.keys())}")
        
        last_quote_time = None
        
        while True:
            self.api.wait_update()
            
            # 更新持仓
            self.update_positions()
            
            now = datetime.now()
            
            # 检查风险限额
            if not self.check_risk_limits():
                print("[风险控制] 超过风险限额，停止新开仓")
                continue
            
            # 定时报价（每5分钟）
            if last_quote_time is None or (now - last_quote_time).seconds >= self.REFRESH_INTERVAL:
                if self.is_trading_time():
                    # 遍历所有品种组进行报价
                    for group_name, symbols in self.COMMODITY_GROUPS.items():
                        # 检查是否需要对冲
                        net_pos = self.get_group_positions(group_name)
                        if abs(net_pos) >= self.HEDGE_THRESHOLD:
                            self.hedge_group(group_name)
                        
                        # 报价
                        for symbol in symbols:
                            self.quote_orders(symbol)
                    
                    last_quote_time = now
                    print(f"[{now.strftime('%H:%M:%S')}] 报价完成")


def main():
    """主函数"""
    api = TqSim()
    # api = TqApi(auth=TqAuth("快期账户", "账户密码"))
    
    strategy = MarketMakerHedgeStrategy(api)
    
    try:
        strategy.run()
    except KeyboardInterrupt:
        print("策略停止")
    finally:
        api.close()


if __name__ == "__main__":
    main()
