# LCPS 插件架构开发指南

**版本**: 1.0
**创建日期**: 2025-12-24
**父文档**: [LCPS综合设计方案](LCPS_COMPREHENSIVE_DESIGN.md)

## 1. 插件系统概述

### 1.1 设计目标

- ✅ 不修改核心代码即可扩展功能
- ✅ 配置驱动的插件管理
- ✅ 支持第三方插件开发
- ✅ 插件热加载/卸载（Phase 3）

### 1.2 插件类型

| 类型 | 说明 | 示例 |
|------|------|------|
| **DataChannelPlugin** | 数据通道插件 | 新增端口接收数据 |
| **AnomalyPlugin** | 异常检测插件 | 自定义检测规则 |
| **VisualizerPlugin** | 可视化插件 | 自定义渲染 |
| **AnalyzerPlugin** | 分析插件 | 自定义分析算法 |

## 2. 核心接口

### 2.1 DataChannelPlugin

```python
from abc import ABC, abstractmethod

class DataChannelPlugin(ABC):
    """数据通道插件基类"""

    @abstractmethod
    def get_config(self) -> ChannelConfig:
        """返回通道配置"""
        pass

    @abstractmethod
    def parse_data(self, raw_data: bytes) -> DataFrame:
        """解析原始数据"""
        pass

    def on_connect(self):
        """连接回调（可选）"""
        pass

    def on_disconnect(self):
        """断开回调（可选）"""
        pass
```

**示例实现**：

```python
class CustomSensorChannel(DataChannelPlugin):
    """自定义传感器通道"""

    def get_config(self) -> ChannelConfig:
        return ChannelConfig(
            port=5559,
            topic="sensor_data",
            format="json"
        )

    def parse_data(self, raw_data: bytes) -> DataFrame:
        data = json.loads(raw_data)
        return DataFrame(
            timestamp=data['timestamp'],
            sensor_values=data['values']
        )
```

### 2.2 AnomalyPlugin

```python
class AnomalyPlugin(ABC):
    """异常检测插件基类"""

    @abstractmethod
    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        """执行异常检测"""
        pass

    def configure(self, config: dict):
        """配置插件（可选）"""
        pass
```

**示例实现**：

```python
class CustomRuleDetector(AnomalyPlugin):
    """自定义规则检测器"""

    def configure(self, config: dict):
        self.threshold = config.get('threshold', 10)

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        anomalies = []

        # 自定义检测逻辑
        if frame.data['obb'].count > self.threshold:
            anomalies.append(Anomaly(
                type="custom_too_many_obbs",
                severity="medium",
                message=f"OBB数量 ({frame.data['obb'].count}) 超过阈值"
            ))

        return anomalies
```

## 3. 插件注册和加载

### 3.1 插件配置文件

```yaml
# plugins/plugin_config.yaml
plugins:
  channels:
    - name: "OBBChannel"
      module: "lcps_observer.channels.obb_channel"
      class: "OBBChannel"
      enabled: true
      config:
        port: 5555

    - name: "CustomSensorChannel"
      module: "plugins.custom_sensor"
      class: "CustomSensorChannel"
      enabled: false
      config:
        port: 5559

  analyzers:
    - name: "MissedAlertDetector"
      module: "lcps_observer.analyzers.missed_alert"
      class: "MissedAlertDetector"
      enabled: true
      config:
        min_points: 50

    - name: "CustomRuleDetector"
      module: "plugins.custom_detector"
      class: "CustomRuleDetector"
      enabled: false
      config:
        threshold: 10
```

### 3.2 插件管理器

```python
import importlib
import yaml

class PluginManager:
    """插件管理器"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.plugins = {}

    def _load_config(self, path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)

    def load_plugins(self, plugin_type: str):
        """加载指定类型的插件"""
        plugins = []

        for plugin_config in self.config['plugins'].get(plugin_type, []):
            if not plugin_config['enabled']:
                continue

            # 动态导入模块
            module = importlib.import_module(plugin_config['module'])
            plugin_class = getattr(module, plugin_config['class'])

            # 实例化插件
            plugin = plugin_class()
            if 'config' in plugin_config and hasattr(plugin, 'configure'):
                plugin.configure(plugin_config['config'])

            plugins.append(plugin)
            self.plugins[plugin_config['name']] = plugin

        return plugins

    def get_plugin(self, name: str):
        """获取指定插件"""
        return self.plugins.get(name)
```

## 4. 插件开发流程

### Step 1: 创建插件文件

```bash
mkdir -p plugins/my_custom_plugin
touch plugins/my_custom_plugin/__init__.py
touch plugins/my_custom_plugin/detector.py
```

### Step 2: 实现插件接口

```python
# plugins/my_custom_plugin/detector.py
from lcps_observer.plugins import AnomalyPlugin

class MyCustomDetector(AnomalyPlugin):
    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        # 实现检测逻辑
        return []
```

### Step 3: 注册插件

```yaml
# plugins/plugin_config.yaml
plugins:
  analyzers:
    - name: "MyCustomDetector"
      module: "plugins.my_custom_plugin.detector"
      class: "MyCustomDetector"
      enabled: true
```

### Step 4: 测试插件

```bash
python -m pytest plugins/my_custom_plugin/test_detector.py
```

## 5. 最佳实践

1. **插件独立性**: 插件不应依赖其他插件
2. **配置验证**: 在configure()中验证配置
3. **错误处理**: 捕获异常，避免crash核心系统
4. **文档完整**: 提供README和API文档
5. **测试覆盖**: 编写单元测试

---

**版本历史**：
- v1.0 (2025-12-24): 初始版本
