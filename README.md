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

## 🌐 TqSdk 策略生态矩阵

本仓库是 **TqSdk 策略生态** 的综合趋势策略分支，与以下专项仓库共同构成完整的期货量化策略体系，每日持续更新：

| 仓库 | 作者 | 专项方向 | 链接 |
|------|------|---------|------|
| 📈 tqsdk-strategies | ringoshinnytech | **综合趋势策略**（MA/MACD/SuperTrend/ATR等） | [本仓库](https://github.com/ringoshinnytech/tqsdk-strategies) |
| ⚖️ tqsdk-arbitrage | kubangr | **套利策略**（跨期套利、跨品种套利、统计套利、期现套利） | [查看](https://github.com/kubangr/tqsdk-arbitrage) |
| 🛡️ tqsdk-options | setherffw | **期权策略**（Delta对冲、Gamma Scalping、波动率套利、期权组合） | [查看](https://github.com/setherffw/tqsdk-options) |
| 🏭 tqsdk-commodities | attiathcoope4jaf | **商品期货专项**（铜/螺纹/豆粕/原油等各品种定制策略） | [查看](https://github.com/attiathcoope4jaf/tqsdk-commodities) |
| 💹 tqsdk-financials | leancu | **金融期货专项**（IF/IC/IM/IH股指期货、国债期货） | [查看](https://github.com/leancu/tqsdk-financials) |
| ⚡ tqsdk-intraday | yscoku | **高频日内策略**（Tick级别、开盘突破ORB、隔夜缺口、VWAP日内） | [查看](https://github.com/yscoku/tqsdk-intraday) |
| 🔒 tqsdk-riskmanager | logueidi | **风控与资金管理**（Kelly仓位、ATR动态仓位、最大回撤控制） | [查看](https://github.com/logueidi/tqsdk-riskmanager) |
| 🔬 tqsdk-research | sjyachie | **量化研究工具**（回测框架、指标库、绩效评估、数据清洗） | [查看](https://github.com/sjyachie/tqsdk-research) |
| 🧩 tqsdk-portfolio | helgejaystea | **多品种组合/配对交易**（协整配对、均值方差优化、风险平价） | [查看](https://github.com/helgejaystea/tqsdk-portfolio) |
| 🌱 tqsdk-seasonal | profedge6 | **季节性/事件驱动**（农产品季节规律、节假日效应、USDA事件） | [查看](https://github.com/profedge6/tqsdk-seasonal) |

> 💡 **10个仓库均每日自动更新，覆盖期货量化交易全场景，欢迎逐一 Star ⭐**

---

### 截面多空类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [27_multi_factor_ranking.py](strategies/27_multi_factor_ranking.py) | 多因子截面排名策略 | 动量+波动率+趋势三因子截面排名，做多综合得分最高、做空得分最低 |
| [28_volatility_breakout.py](strategies/28_volatility_breakout.py) | 波动率动量突破策略 | ATR 突破 + ADX 趋势确认，动态止损跟踪趋势 |

## 📁 策略列表（59个）

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

### 多因子/对冲类

| 策略文件 | 策略名称 | 核心逻辑 |
|---------|---------|---------|
| [46_multi_factor.py](strategies/46_multi_factor.py) | 多因子量化选股策略 | 动量+趋势+波动率+成交量四因子加权评分，选强势品种交易 |
| [47_cross_market_hedge.py](strategies/47_cross_market_hedge.py) | 跨市场对冲策略 | 基于Z-Score的跨品种价差套利，做多低估做空高估 |
| [48_sector_rotation_multi_factor.py](strategies/48_sector_rotation_multi_factor.py) | 截面多因子行业轮动策略 | 动量+波动率+成交量+趋势四因子截面打分，跨板块多空轮动 |
| [49_mean_variance_portfolio.py](strategies/49_mean_variance_portfolio.py) | 均值方差最优组合策略 | Markowitz最大夏普比率组合，波动率目标调仓，多品种联合配置 |
| [50_volatility_skew.py](strategies/50_volatility_skew.py) | 截面波动率偏度交易策略 | 20日收益率分布偏度+波动率水平+动量+成交量四因子截面打分，筛选低风险高动量品种 |
| [51_term_structure.py](strategies/51_term_structure.py) | 期限结构基差回归策略 | 基于近远月价比的对数斜率，当斜率偏离历史均值1.5倍标准差时入场，做价差均值回归 |
| [52_multi_factor_ai_prediction.py](strategies/52_multi_factor_ai_prediction.py) | 多因子AI预测策略 | 融合动量/趋势/波动率/成交量因子，基于预测信号进行品种轮动和仓位调整 |
| [53_market_maker_hedge.py](strategies/53_market_maker_hedge.py) | 跨品种做市商对冲策略 | 模拟做市商在多品种上挂单，使用跨品种对冲消除方向性风险，赚取买卖价差 |
| [54_multi_asset_long_short_hedge.py](strategies/54_multi_asset_long_short_hedge.py) | 多标的截面多空对冲策略 | 动量因子截面排名+趋势过滤+流动性过滤，构建等权多空对冲组合剥离系统性风险 |
| [55_momentum_value_factor_composite.py](strategies/55_momentum_value_factor_composite.py) | 时序动量与截面价值因子复合策略 | 20日动量因子与期限结构价值因子加权组合，截面多空+ADX趋势确认 |
| [56_cross_section_multi_factor_ranking.py](strategies/56_cross_section_multi_factor_ranking.py) | 截面多因子Ranking轮动策略 | 黑色系五品种截面动量+波动率+ADX三因子排名，多空轮动消除单边风险 |
| [57_adaptive_volatility_breakout.py](strategies/57_adaptive_volatility_breakout.py) | 自适应波动率突破策略（基于波动锥） | 三档波动率锥动态调整止损止盈，波动率越高仓位越低，趋势自适应 |
| [58_money_flow_rotation.py](strategies/58_money_flow_rotation.py) | 截面资金流向多空轮动策略 | CMF资金流向+OI持仓量背离+VWAP偏离三重因子截面排名，多空轮动捕捉主力资金动向 |
| [59_vol_momentum_composite.py](strategies/59_vol_momentum_composite.py) | 时序波动率与截面动量复合趋势策略 | 时序布林带+ADX+RSI与截面收益率双重确认，ADX自适应仓位过滤噪音趋势 |

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
