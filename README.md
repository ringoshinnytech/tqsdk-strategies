# TqSdk 量化交易策略集

> 基于 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现的期货量化交易策略示例集合，每个策略附有完整中文注释和详细策略思路讲解。

---

## 📖 关于 TqSdk

**TqSdk（天勤量化开发包）** 是由 [信易科技](https://www.shinnytech.com/) 发起并开源的 Python 量化交易框架，专为国内期货市场设计。

### 核心特性

- 🚀 **极简代码**：几十行代码即可构建完整的量化交易策略
- 📊 **全品种数据**：覆盖期货、期权、股票，提供全历史 Tick 与 K 线数据（从上市日起）
- ⚡ **实时行情**：毫秒级行情推送，数据全在内存，零访问延迟
- 🔄 **全流程支持**：历史数据 → 开发调试 → 策略回测 → 模拟交易 → 实盘交易 → 运行监控
- 🏦 **广泛兼容**：支持市场上 90% 以上的期货公司实盘交易
- 🐼 **Pandas 友好**：K 线、Tick 数据直接以 `pandas.DataFrame` 返回，配合 numpy 无缝分析
- 📐 **近百个技术指标**：内置 MA、EMA、BOLL、RSI、MACD、ATR 等常用指标函数及源码
- 🤖 **多账户支持**：支持多个实盘账户、模拟账户同时运行
- 🔁 **灵活回测**：支持 Tick 级和 K 线级回测，无需建立和维护数据库

### 系统架构

```
策略程序 (TqSdk)
    ├── 行情网关  ←→  实时行情 / 历史数据（Diff 协议）
    └── 交易中继  ←→  期货公司交易系统（CTP / 资管柜台 / 高速柜台）
```

### 支持的交易类型

| 类型 | 说明 |
|------|------|
| 期货实盘 | 支持 CTP 直连及众期、融航、杰宜斯等资管柜台，易达、ctpmini 等高速柜台 |
| 期权交易 | 商品期权、股指期权 |
| 股票交易 | A 股实盘与回测 |
| 模拟交易 | TqKq 快期模拟账户或内置临时模拟账户 |

---

## 🔗 官方资源

| 资源 | 链接 |
|------|------|
| 📘 官方文档 | https://doc.shinnytech.com/tqsdk/latest/ |
| ⚡ 快速入门 | https://doc.shinnytech.com/tqsdk/latest/quickstart.html |
| 🎯 策略示例库 | https://doc.shinnytech.com/tqsdk/latest/demo/strategy.html |
| 📐 API 参考 | https://doc.shinnytech.com/tqsdk/latest/reference/index.html |
| 🐙 GitHub 仓库 | https://github.com/shinnytech/tqsdk-python |
| 🌐 信易科技官网 | https://www.shinnytech.com/ |
| 🧑‍💻 快期账户注册 | https://account.shinnytech.com/ |
| 💬 用户社区论坛 | https://www.shinnytech.com/qa/ |
| 📺 入门视频教程 | https://www.shinnytech.com/tqsdkquickstart/ |
| 🤖 天勤 AI 助手 | https://www.shinnytech.com/products/tqsdk |

---

## 📦 安装

```bash
pip install tqsdk -U
```

**要求：** Python >= 3.8（推荐 3.10+）

使用国内镜像（推荐，速度更快）：

```bash
pip install tqsdk -U -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host=pypi.tuna.tsinghua.edu.cn
```

---

## 🚀 快速上手

### 获取实时行情

```python
from tqsdk import TqApi, TqAuth

api = TqApi(auth=TqAuth("快期账户", "账户密码"))
quote = api.get_quote("SHFE.rb2501")

while True:
    api.wait_update()
    print(quote.last_price, quote.volume)
```

### 策略回测

```python
from datetime import date
from tqsdk import TqApi, TqAuth, TqBacktest

api = TqApi(
    backtest=TqBacktest(start_dt=date(2023, 1, 1), end_dt=date(2024, 1, 1)),
    auth=TqAuth("快期账户", "账户密码")
)
```

---

## 📁 策略列表（31个）

> 每个策略文件包含：**500字以上策略思路讲解 + 完整可运行代码 + 详细中文注释**

### 趋势跟踪类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [01_double_ma.py](strategies/01_double_ma.py) | 双均线趋势策略 | MA5/MA20 金叉做多、死叉做空 |
| [06_macd_trend.py](strategies/06_macd_trend.py) | MACD 趋势策略 | DIF/DEA 金叉死叉，动能确认趋势方向 |
| [16_aroon_trend.py](strategies/16_aroon_trend.py) | Aroon 指标趋势策略 | Aroon Up/Down 强弱对比判断趋势 |
| [20_hull_ma.py](strategies/20_hull_ma.py) | Hull 移动平均线策略 | 减少均线滞后的 WMA 加权趋势跟踪 |
| [22_trix_trend.py](strategies/22_trix_trend.py) | TRIX 三重指数策略 | 三重EMA变化率，过滤短期噪音 |
| [25_multiperiod_ma.py](strategies/25_multiperiod_ma.py) | 多周期均线共振策略 | 日/小时/分钟三周期均线方向一致才入场 |

### 突破类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [02_boll_breakout.py](strategies/02_boll_breakout.py) | 布林带突破策略 | 上轨突破做多、下轨跌破做空、带宽过滤 |
| [08_cci_breakout.py](strategies/08_cci_breakout.py) | CCI 顺势指标策略 | ±100 反向、±200 顺势突破 |
| [10_momentum_breakout.py](strategies/10_momentum_breakout.py) | 价格动量突破策略 | N 日涨跌幅动量信号触发入场 |
| [13_opening_range_breakout.py](strategies/13_opening_range_breakout.py) | 开盘区间突破策略 | 开盘前30分钟高低点作为当日突破区间 |
| [15_donchian_channel.py](strategies/15_donchian_channel.py) | 唐奇安通道策略 | N 日最高最低价通道突破入场 |
| [21_keltner_channel.py](strategies/21_keltner_channel.py) | 肯特纳通道策略 | EMA±ATR 通道，价格突破做趋势 |

### 均值回归类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [03_rsi_mean_reversion.py](strategies/03_rsi_mean_reversion.py) | RSI 均值回归策略 | RSI<30 超卖做多、RSI>70 超买做空 |
| [07_kdj_signal.py](strategies/07_kdj_signal.py) | KDJ 随机指标策略 | K/D/J 线超买超卖，随机波动捕捉反转 |
| [11_mean_reversion_zscore.py](strategies/11_mean_reversion_zscore.py) | Z-Score 均值回归策略 | 价格偏离均值 N 个标准差后回归 |
| [17_stochastic_rsi.py](strategies/17_stochastic_rsi.py) | 随机 RSI 策略 | 对 RSI 再做随机处理，更灵敏的超买超卖 |
| [19_williams_r.py](strategies/19_williams_r.py) | 威廉指标策略 | %R 超买超卖，日内情绪指标 |
| [23_pivot_point.py](strategies/23_pivot_point.py) | 枢轴点支撑阻力策略 | 昨日高低收计算今日支撑阻力，关键位反转 |

### 日内策略类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [04_dual_thrust.py](strategies/04_dual_thrust.py) | Dual Thrust 日内突破 | 开盘价±Range 动态轨道，收盘前强制平仓 |
| [24_r_breaker.py](strategies/24_r_breaker.py) | R-Breaker 日内策略 | 6条价格线：突破/观察/反转三类信号 |

### 系统化/风控类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [05_turtle_trading.py](strategies/05_turtle_trading.py) | 海龟交易策略 | 唐奇安通道突破 + ATR 仓位管理 |
| [09_atr_stop_loss.py](strategies/09_atr_stop_loss.py) | ATR 动态止损策略 | 均线趋势入场 + ATR 追踪止损出场 |
| [12_grid_trading.py](strategies/12_grid_trading.py) | 网格交易策略 | 价格区间内按网格间距自动挂单买卖 |
| [14_volume_price_trend.py](strategies/14_volume_price_trend.py) | 量价趋势策略 | 成交量配合价格突破做信号验证 |
| [18_parabolic_sar.py](strategies/18_parabolic_sar.py) | 抛物线转向策略 | SAR 跟踪止损点，价格穿越 SAR 转向 |

### 资金流向类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [26_chaikin_money_flow.py](strategies/26_chaikin_money_flow.py) | 蔡金资金流量策略 | CMF 衡量买卖资金净流向，上穿阈值做多，下穿阈值做空 |
| [28_obv_trend.py](strategies/28_obv_trend.py) | OBV 能量潮趋势策略 | OBV 短/长均线金叉死叉，量能领先价格判断资金流向 |

### 多周期综合类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [27_elder_triple_screen.py](strategies/27_elder_triple_screen.py) | Elder 三屏交易系统 | 日线MACD趋势+小时线Stochastic超买超卖+15分钟均线精确入场 |

### 趋势强度过滤类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [29_adx_trend_filter.py](strategies/29_adx_trend_filter.py) | ADX 趋势强度过滤策略 | ADX>25确认趋势强度，+DI/-DI判断方向，ATR追踪止损动态护盈 |
| [30_supertrend.py](strategies/30_supertrend.py) | SuperTrend 超级趋势指标策略 | ATR倍数动态上下轨，趋势翻转时平仓反手，自带追踪止损 |

### 均值回归（日内）类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [31_vwap_mean_reversion.py](strategies/31_vwap_mean_reversion.py) | VWAP 均值回归日内策略 | 日内滚动VWAP+标准差带，价格偏离N倍σ入场，回归至VWAP附近平仓，尾盘强平 |

---

## 🛠️ 使用说明

1. **克隆仓库**

   ```bash
   git clone https://github.com/ringoshinnytech/tqsdk-strategies.git
   cd tqsdk-strategies
   ```

2. **安装依赖**

   ```bash
   pip install tqsdk -U
   ```

3. **配置账户**  
   在策略文件中替换 `YOUR_ACCOUNT` / `YOUR_PASSWORD` 为你的快期账户信息。  
   注册快期账户：https://account.shinnytech.com/

4. **运行策略（模拟模式）**

   ```bash
   python strategies/01_double_ma.py
   ```

---

## 📅 更新计划

本仓库每天自动新增 **2 个策略**，持续扩充策略库。

---

## ⚠️ 风险提示

- 本仓库所有策略**仅供学习和研究使用**，不构成任何投资建议
- 量化交易存在亏损风险，请在充分理解策略逻辑后再用于实盘
- 建议先使用**模拟账户**充分测试后，再考虑实盘运行
- 过去的回测表现不代表未来的实际收益

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。  
TqSdk 本身基于 [Apache-2.0 License](https://github.com/shinnytech/tqsdk-python/blob/master/LICENSE)。
