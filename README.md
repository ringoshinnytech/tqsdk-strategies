# TqSdk 量化交易策略集

> 基于 [天勤量化 TqSdk](https://github.com/shinnytech/tqsdk-python) 实现的期货量化交易策略示例集合，每个策略附有完整中文注释。

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
quote = api.get_quote("SHFE.rb2501")  # 订阅螺纹钢行情

while True:
    api.wait_update()
    print(quote.last_price, quote.volume)
```

### 获取 K 线数据

```python
# 获取 1 分钟 K 线（返回 pandas.DataFrame）
klines = api.get_kline_serial("SHFE.rb2501", 60)

while True:
    api.wait_update()
    print("最新收盘价:", klines.close.iloc[-1])
```

### 下单交易

```python
# 买入开仓 1 手
order = api.insert_order(
    symbol="SHFE.rb2501",
    direction="BUY",
    offset="OPEN",
    volume=1
)
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

## 📁 策略列表

| 策略文件 | 策略名称 | 类型 | 核心逻辑 |
|---------|---------|------|---------|
| [01_double_ma.py](strategies/01_double_ma.py) | 双均线趋势策略 | 趋势跟踪 | MA5/MA20 金叉做多、死叉做空 |
| [02_boll_breakout.py](strategies/02_boll_breakout.py) | 布林带突破策略 | 趋势突破 | 上轨突破做多、下轨跌破做空、带宽过滤 |
| [03_rsi_mean_reversion.py](strategies/03_rsi_mean_reversion.py) | RSI 均值回归策略 | 均值回归 | RSI<30 超卖做多、RSI>70 超买做空 |
| [04_dual_thrust.py](strategies/04_dual_thrust.py) | Dual Thrust 日内突破 | 日内策略 | 开盘价±Range 动态轨道，收盘前强制平仓 |
| [05_turtle_trading.py](strategies/05_turtle_trading.py) | 海龟交易策略 | 趋势跟踪 | 唐奇安通道突破入场 + ATR 仓位管理 |

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

   在各策略文件中替换以下占位符为你的真实账户：

   ```python
   auth=TqAuth("YOUR_ACCOUNT", "YOUR_PASSWORD")
   # 替换为：
   auth=TqAuth("你的快期账号", "你的快期密码")
   ```

   > 注册快期账户：https://account.shinnytech.com/

4. **运行策略（模拟模式）**

   ```bash
   python strategies/01_double_ma.py
   ```

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
