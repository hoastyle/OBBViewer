# LCPS 插件架构开发指南

**版本**: 2.0
**创建日期**: 2025-12-24
**父文档**: [LCPS综合设计方案](LCPS_COMPREHENSIVE_DESIGN.md)
**关联ADR**: [ADR v2.0 决策5](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计)

---

## 📋 文档概述

本文档提供LCPS观测工具插件系统的完整开发指南，包括：
- 插件架构设计和分类
- 核心API接口和示例
- 插件开发SDK
- 8个内置插件参考实现
- 最佳实践和常见问题

**插件系统收益**（ADR v2.0验证）:
- ✅ 开发效率提升 70%（7天 → 2天添加新功能）
- ✅ 维护成本降低 40%（插件隔离，减少回归测试）
- ✅ 100% PRD覆盖（可扩展性需求满足）

---

## 1. 插件系统概述

### 1.1 设计目标

| 目标 | 说明 | 验证标准 |
|------|------|---------|
| **不修改代码即可扩展** | 通过配置文件启用/禁用功能 | 新增功能无需改核心代码 |
| **配置驱动** | YAML配置管理插件 | 配置验证和错误提示 |
| **第三方插件支持** | 用户可编写自定义插件 | 提供SDK和示例 |
| **热加载** | 运行时加载/卸载插件 | 无需重启工具 |
| **故障隔离** | 插件崩溃不影响核心系统 | 异常捕获和降级 |

### 1.2 插件分类（4类）

```
插件类型层次
═══════════════════════════════════════════════════════
IPlugin（基类）
  ├─ IDataChannelPlugin     数据通道插件（扩展数据源）
  ├─ IMonitorPlugin         监控插件（实时监控和可视化）
  ├─ IAnalyzerPlugin        分析插件（异常检测和分析）
  └─ IExporterPlugin        导出插件（数据导出和格式转换）
```

| 类型 | 职责 | 典型用途 | 内置示例 |
|------|------|---------|---------|
| **DataChannel** | 从ZMQ端口接收数据 | 新增数据源（热成像、雷达） | OBBChannel, PointCloudChannel, StatusChannel |
| **Monitor** | 实时监控和可视化 | 3D渲染、HUD、热力图 | LiveMonitor, LifecycleMonitor |
| **Analyzer** | 异常检测和分析 | 漏报/误报检测、统计分析 | MissedAlertDetector, FalseAlarmDetector |
| **Exporter** | 数据导出 | HDF5录制、ML数据集导出 | HDF5Recorder, MLDatasetExporter |

---

## 2. 核心接口定义

### 2.1 IPlugin（基类）

所有插件必须实现的基础接口：

```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class IPlugin(ABC):
    """插件基类（所有插件必须继承）"""

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据

        Returns:
            {
                "name": "PluginName",
                "version": "1.0.0",
                "author": "Author Name",
                "description": "插件功能描述",
                "dependencies": ["plugin1", "plugin2"]  # 可选
            }
        """
        pass

    @abstractmethod
    def on_init(self, config: Dict[str, Any]):
        """初始化插件

        Args:
            config: 来自plugin_config.yaml的配置字典

        Raises:
            ConfigError: 配置验证失败
        """
        pass

    @abstractmethod
    def on_enable(self):
        """启用插件（开始工作）

        Called after on_init, when plugin is ready to start.
        """
        pass

    @abstractmethod
    def on_disable(self):
        """禁用插件（暂停工作）

        Called when plugin needs to pause (e.g., user disabled via UI).
        """
        pass

    @abstractmethod
    def on_destroy(self):
        """销毁插件（释放资源）

        Called when plugin is being unloaded.
        Must release all resources (threads, file handles, etc.).
        """
        pass
```

**插件生命周期**:
```
[创建] → on_init() → [初始化完成] → on_enable() → [运行中]
                                              ↓
                                         on_disable() → [暂停]
                                              ↓
                                         on_destroy() → [销毁]
```

---

### 2.2 IDataChannelPlugin（数据通道）

用于扩展数据源（从新的ZMQ端口接收数据）：

```python
from dataclasses import dataclass

@dataclass
class ChannelConfig:
    """通道配置"""
    port: int                # ZMQ端口
    topic: str               # ZMQ订阅主题
    format: str              # 数据格式（json/bson/protobuf）
    compression: str = None  # 压缩方式（zlib/none）

@dataclass
class DataFrame:
    """标准数据帧"""
    timestamp: float         # 时间戳（秒）
    data_type: str           # 数据类型（obb/pointcloud/status等）
    data: Any                # 数据内容

class IDataChannelPlugin(IPlugin):
    """数据通道插件接口"""

    @abstractmethod
    def get_channel_config(self) -> ChannelConfig:
        """返回通道配置（ZMQ端口、主题、格式）"""
        pass

    @abstractmethod
    def parse_data(self, raw_data: bytes) -> DataFrame:
        """解析原始数据为标准DataFrame

        Args:
            raw_data: ZMQ接收的原始字节流

        Returns:
            DataFrame: 标准化的数据帧

        Raises:
            ParseError: 数据解析失败
        """
        pass

    def on_connect(self):
        """连接成功回调（可选重载）"""
        pass

    def on_disconnect(self):
        """断开连接回调（可选重载）"""
        pass
```

**示例实现：OBBChannel**（内置）

```python
class OBBChannel(IDataChannelPlugin):
    """OBB数据通道（内置插件）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "OBBChannel",
            "version": "1.0.0",
            "author": "LCPS Team",
            "description": "接收OBB数据（端口5555）"
        }

    def on_init(self, config: Dict[str, Any]):
        self.port = config.get("port", 5555)
        self.compression = config.get("compression", "zlib")

    def get_channel_config(self) -> ChannelConfig:
        return ChannelConfig(
            port=self.port,
            topic="obb",
            format="json",
            compression=self.compression
        )

    def parse_data(self, raw_data: bytes) -> DataFrame:
        # 解压缩
        if self.compression == "zlib":
            raw_data = zlib.decompress(raw_data)

        # 解析JSON
        data = json.loads(raw_data)

        return DataFrame(
            timestamp=data['timestamp'],
            data_type='obb',
            data={
                'obbs': [
                    OBB(
                        position=obj['position'],
                        rotation=obj['rotation'],
                        size=obj['size'],
                        type=obj['type']
                    ) for obj in data['objects']
                ]
            }
        )

    def on_enable(self):
        print(f"OBBChannel: 已连接端口 {self.port}")

    def on_disable(self):
        print("OBBChannel: 已断开")

    def on_destroy(self):
        pass  # 无需释放资源
```

**用户自定义示例：热成像通道**

```python
class ThermalChannel(IDataChannelPlugin):
    """热成像数据通道（用户自定义）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "ThermalChannel",
            "version": "1.0.0",
            "author": "User",
            "description": "接收热成像数据（端口5559）"
        }

    def on_init(self, config: Dict[str, Any]):
        self.port = config["port"]  # 必需参数
        self.image_size = config.get("image_size", (640, 480))

    def get_channel_config(self) -> ChannelConfig:
        return ChannelConfig(
            port=self.port,
            topic="thermal",
            format="bson"
        )

    def parse_data(self, raw_data: bytes) -> DataFrame:
        data = bson.loads(raw_data)
        return DataFrame(
            timestamp=data['timestamp'],
            data_type='thermal',
            data={
                'image': np.array(data['image']).reshape(self.image_size),
                'max_temp': data['max_temp'],
                'min_temp': data['min_temp']
            }
        )

    def on_enable(self):
        print(f"ThermalChannel: 已启用（端口{self.port}）")

    def on_disable(self):
        pass

    def on_destroy(self):
        pass
```

---

### 2.3 IMonitorPlugin（监控可视化）

用于实时监控和可视化：

```python
class IMonitorPlugin(IPlugin):
    """监控可视化插件接口"""

    @abstractmethod
    def on_frame(self, synced_frame: SyncedFrame):
        """处理每一帧数据

        Args:
            synced_frame: 时间戳对齐后的数据帧（包含所有通道数据）

        Called at every frame (30 Hz). Should be fast (<10ms).
        """
        pass

    @abstractmethod
    def render(self):
        """渲染可视化（OpenGL/ImGui）

        Called in the render loop. Can use OpenGL or ImGui API.
        """
        pass

    def on_key_press(self, key: str):
        """键盘事件回调（可选）"""
        pass

    def on_mouse_click(self, x: int, y: int, button: str):
        """鼠标点击回调（可选）"""
        pass
```

**示例实现：LiveMonitor**（内置）

```python
import pygame
from OpenGL.GL import *
import imgui

class LiveMonitor(IMonitorPlugin):
    """实时3D监控（内置插件）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "LiveMonitor",
            "version": "1.0.0",
            "author": "LCPS Team",
            "description": "实时3D点云和OBB可视化"
        }

    def on_init(self, config: Dict[str, Any]):
        self.fps_target = config.get("fps_target", 30)
        self.current_frame = None

    def on_frame(self, synced_frame: SyncedFrame):
        """更新当前帧数据"""
        self.current_frame = synced_frame

    def render(self):
        """OpenGL渲染"""
        if not self.current_frame:
            return

        # 渲染点云
        if 'pointcloud' in self.current_frame.data:
            self._render_pointcloud(self.current_frame.data['pointcloud'])

        # 渲染OBB
        if 'obb' in self.current_frame.data:
            self._render_obbs(self.current_frame.data['obb']['obbs'])

        # 渲染HUD
        self._render_hud()

    def _render_pointcloud(self, pc_data):
        """渲染点云（OpenGL）"""
        glBegin(GL_POINTS)
        glColor3f(1.0, 1.0, 1.0)
        for point in pc_data['points']:
            glVertex3fv(point)
        glEnd()

    def _render_obbs(self, obbs):
        """渲染OBB（OpenGL线框）"""
        for obb in obbs:
            # 绘制线框立方体（复用现有代码）
            draw_wire_cube(obb.position, obb.rotation, obb.size)

    def _render_hud(self):
        """渲染HUD（ImGui）"""
        imgui.begin("Live Monitor")
        imgui.text(f"FPS: {self.fps_target}")
        imgui.text(f"Timestamp: {self.current_frame.timestamp:.3f}")
        if 'obb' in self.current_frame.data:
            imgui.text(f"OBB Count: {len(self.current_frame.data['obb']['obbs'])}")
        imgui.end()

    def on_enable(self):
        print("LiveMonitor: 已启用")

    def on_disable(self):
        pass

    def on_destroy(self):
        pass
```

**用户自定义示例：热力图监控**

```python
class HeatmapMonitor(IMonitorPlugin):
    """点云密度热力图监控（用户自定义）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "HeatmapMonitor",
            "version": "1.0.0",
            "author": "User",
            "description": "点云密度热力图可视化"
        }

    def on_init(self, config: Dict[str, Any]):
        self.grid_size = config.get("grid_size", 0.5)
        self.map_size = config.get("map_size", 100)
        self.heatmap = np.zeros((self.map_size, self.map_size))

    def on_frame(self, synced_frame: SyncedFrame):
        """更新热力图"""
        if 'pointcloud' not in synced_frame.data:
            return

        # 重置热力图
        self.heatmap.fill(0)

        # 计算点云密度
        points = synced_frame.data['pointcloud']['points']
        for point in points:
            x_idx = int((point[0] + 50) / self.grid_size)  # 假设场景范围 [-50, 50]
            y_idx = int((point[1] + 50) / self.grid_size)
            if 0 <= x_idx < self.map_size and 0 <= y_idx < self.map_size:
                self.heatmap[x_idx, y_idx] += 1

    def render(self):
        """渲染热力图（ImGui）"""
        imgui.begin("Heatmap Monitor")

        # 将numpy数组转为ImGui纹理（简化示例）
        # 实际需要创建OpenGL纹理
        imgui.text(f"Grid Size: {self.grid_size}m")
        imgui.text(f"Max Density: {self.heatmap.max():.0f} points/cell")

        # 绘制热力图（伪代码，实际需要纹理）
        # imgui.image(heatmap_texture, 400, 400)

        imgui.end()

    def on_enable(self):
        print("HeatmapMonitor: 已启用")

    def on_disable(self):
        pass

    def on_destroy(self):
        pass
```

---

### 2.4 IAnalyzerPlugin（分析检测）

用于异常检测和数据分析：

```python
@dataclass
class Anomaly:
    """异常检测结果"""
    type: str            # 异常类型（missed_alert/false_alarm/lifecycle_error等）
    severity: str        # 严重程度（low/medium/high/critical）
    timestamp: float     # 发生时间
    message: str         # 详细描述
    data: Any = None     # 附加数据

class IAnalyzerPlugin(IPlugin):
    """分析检测插件接口"""

    @abstractmethod
    def analyze(self, frame: SyncedFrame) -> List[Anomaly]:
        """分析数据帧，返回异常列表

        Args:
            frame: 同步数据帧

        Returns:
            List[Anomaly]: 检测到的异常列表（空列表表示无异常）
        """
        pass

    def on_anomaly_detected(self, anomaly: Anomaly):
        """异常检测回调（可选）

        Called after analyze() returns non-empty list.
        """
        pass
```

**示例实现：MissedAlertDetector**（内置）

```python
class MissedAlertDetector(IAnalyzerPlugin):
    """漏报检测器（内置插件）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "MissedAlertDetector",
            "version": "1.0.0",
            "author": "LCPS Team",
            "description": "检测应该报警但未报警的情况（漏报）"
        }

    def on_init(self, config: Dict[str, Any]):
        # 危险区域定义（从配置读取）
        self.danger_zones = [
            Zone(x_min=cfg["x_min"], y_min=cfg["y_min"],
                 x_max=cfg["x_max"], y_max=cfg["y_max"])
            for cfg in config["danger_zones"]
        ]
        self.min_obstacle_points = config.get("min_obstacle_points", 50)

    def analyze(self, frame: SyncedFrame) -> List[Anomaly]:
        anomalies = []

        # 检查点云数据
        if 'pointcloud' not in frame.data:
            return anomalies

        pc_data = frame.data['pointcloud']
        obb_data = frame.data.get('obb', {'obbs': []})

        # 检测逻辑：危险区域内有足够点云，但无OBB
        for zone in self.danger_zones:
            points_in_zone = self._count_points_in_zone(pc_data['points'], zone)

            if points_in_zone >= self.min_obstacle_points:
                # 检查是否有对应的OBB
                obb_in_zone = any(
                    self._obb_in_zone(obb, zone)
                    for obb in obb_data['obbs']
                )

                if not obb_in_zone:
                    # 漏报！
                    anomalies.append(Anomaly(
                        type="missed_alert",
                        severity="high",
                        timestamp=frame.timestamp,
                        message=f"危险区域 {zone.name} 有 {points_in_zone} 个点，但未生成OBB",
                        data={'zone': zone, 'points': points_in_zone}
                    ))

        return anomalies

    def _count_points_in_zone(self, points, zone) -> int:
        """统计区域内点数"""
        count = 0
        for point in points:
            if (zone.x_min <= point[0] <= zone.x_max and
                zone.y_min <= point[1] <= zone.y_max):
                count += 1
        return count

    def _obb_in_zone(self, obb, zone) -> bool:
        """检查OBB是否在区域内"""
        pos = obb.position
        return (zone.x_min <= pos[0] <= zone.x_max and
                zone.y_min <= pos[1] <= zone.y_max)

    def on_enable(self):
        print(f"MissedAlertDetector: 已启用（监控 {len(self.danger_zones)} 个危险区域）")

    def on_disable(self):
        pass

    def on_destroy(self):
        pass
```

---

### 2.5 IExporterPlugin（数据导出）

用于数据导出和格式转换：

```python
class IExporterPlugin(IPlugin):
    """数据导出插件接口"""

    @abstractmethod
    def export(self, data: Any, output_path: Path):
        """导出数据到指定路径

        Args:
            data: 要导出的数据（可能是SyncedFrame列表、分析报告等）
            output_path: 输出路径
        """
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """返回支持的导出格式"""
        pass
```

**示例实现：MLDatasetExporter**（内置）

```python
class MLDatasetExporter(IExporterPlugin):
    """ML数据集导出器（内置插件）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "MLDatasetExporter",
            "version": "1.0.0",
            "author": "LCPS Team",
            "description": "导出KITTI/TFRecord格式的ML数据集"
        }

    def on_init(self, config: Dict[str, Any]):
        self.format = config.get("format", "KITTI")  # KITTI/TFRecord/PyTorch
        self.train_val_split = config.get("train_val_split", 0.8)

    def get_supported_formats(self) -> List[str]:
        return ["KITTI", "TFRecord", "PyTorch"]

    def export(self, data: List[SyncedFrame], output_path: Path):
        """导出数据集"""
        if self.format == "KITTI":
            self._export_kitti(data, output_path)
        elif self.format == "TFRecord":
            self._export_tfrecord(data, output_path)
        elif self.format == "PyTorch":
            self._export_pytorch(data, output_path)

    def _export_kitti(self, frames: List[SyncedFrame], output_path: Path):
        """导出KITTI格式"""
        # KITTI格式：
        # data/
        #   velodyne/  # 点云（.bin）
        #   label_2/   # OBB标注（.txt）
        #   ImageSets/ # train/val划分

        velodyne_dir = output_path / "velodyne"
        label_dir = output_path / "label_2"
        imageset_dir = output_path / "ImageSets"

        velodyne_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        imageset_dir.mkdir(parents=True, exist_ok=True)

        train_list = []
        val_list = []

        for idx, frame in enumerate(frames):
            # 保存点云
            pc_file = velodyne_dir / f"{idx:06d}.bin"
            points = frame.data['pointcloud']['points']
            points.astype(np.float32).tofile(pc_file)

            # 保存标注
            label_file = label_dir / f"{idx:06d}.txt"
            with open(label_file, 'w') as f:
                for obb in frame.data['obb']['obbs']:
                    # KITTI格式：type truncated occluded alpha bbox dimensions location rotation_y
                    f.write(f"{obb.type} 0 0 0 ")
                    f.write(f"0 0 0 0 ")  # bbox（2D，可选）
                    f.write(f"{obb.size[0]} {obb.size[1]} {obb.size[2]} ")
                    f.write(f"{obb.position[0]} {obb.position[1]} {obb.position[2]} ")
                    f.write(f"{obb.rotation_y}\n")

            # train/val划分
            if idx < len(frames) * self.train_val_split:
                train_list.append(f"{idx:06d}")
            else:
                val_list.append(f"{idx:06d}")

        # 保存train/val列表
        with open(imageset_dir / "train.txt", 'w') as f:
            f.write('\n'.join(train_list))
        with open(imageset_dir / "val.txt", 'w') as f:
            f.write('\n'.join(val_list))

        print(f"✅ 导出KITTI数据集完成：{len(frames)} 帧")
        print(f"   Train: {len(train_list)}, Val: {len(val_list)}")

    def on_enable(self):
        print(f"MLDatasetExporter: 已启用（格式: {self.format}）")

    def on_disable(self):
        pass

    def on_destroy(self):
        pass
```

---

## 3. 插件管理系统

### 3.1 PluginManager（插件管理器）

```python
import importlib
import yaml
from pathlib import Path
from typing import Dict, List

class PluginManager:
    """插件管理器（核心）"""

    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self.plugins: Dict[str, IPlugin] = {}
        self.event_bus = EventBus()  # 插件间通信

    def _load_config(self, path: Path) -> dict:
        """加载配置文件"""
        with open(path) as f:
            config = yaml.safe_load(f)
        self._validate_config(config)
        return config

    def _validate_config(self, config: dict):
        """验证配置文件"""
        if 'plugins' not in config:
            raise ConfigError("配置文件缺少 'plugins' 节")

        for plugin_type in ['data_channels', 'monitors', 'analyzers', 'exporters']:
            if plugin_type not in config['plugins']:
                config['plugins'][plugin_type] = []

    def load_plugins(self):
        """加载所有启用的插件"""
        for plugin_type in ['data_channels', 'monitors', 'analyzers', 'exporters']:
            for plugin_config in self.config['plugins'][plugin_type]:
                if plugin_config.get('enabled', False):
                    self._load_plugin(plugin_config)

    def _load_plugin(self, plugin_config: dict):
        """加载单个插件"""
        try:
            # 动态导入模块
            module_path = plugin_config['module']
            module = importlib.import_module(module_path)

            # 获取插件类
            class_name = plugin_config.get('class', plugin_config['name'])
            plugin_class = getattr(module, class_name)

            # 实例化插件
            plugin = plugin_class()

            # 初始化
            plugin.on_init(plugin_config.get('config', {}))

            # 注册
            self.plugins[plugin_config['name']] = plugin

            print(f"✅ 加载插件: {plugin_config['name']}")

        except Exception as e:
            print(f"❌ 加载插件失败: {plugin_config['name']}")
            print(f"   错误: {e}")
            raise

    def enable_plugin(self, name: str):
        """启用插件"""
        if name in self.plugins:
            self.plugins[name].on_enable()
            print(f"✅ 启用插件: {name}")

    def disable_plugin(self, name: str):
        """禁用插件"""
        if name in self.plugins:
            self.plugins[name].on_disable()
            print(f"⏸️  禁用插件: {name}")

    def reload_plugin(self, name: str):
        """热加载插件（运行时重新加载）"""
        if name not in self.plugins:
            raise ValueError(f"插件 {name} 不存在")

        # 禁用插件
        self.disable_plugin(name)

        # 销毁插件
        self.plugins[name].on_destroy()

        # 重新导入模块（刷新代码）
        plugin_config = self._find_plugin_config(name)
        module = importlib.import_module(plugin_config['module'])
        importlib.reload(module)

        # 重新加载
        del self.plugins[name]
        self._load_plugin(plugin_config)

        # 启用插件
        self.enable_plugin(name)

        print(f"🔄 热加载插件: {name}")

    def _find_plugin_config(self, name: str) -> dict:
        """查找插件配置"""
        for plugin_type in ['data_channels', 'monitors', 'analyzers', 'exporters']:
            for cfg in self.config['plugins'][plugin_type]:
                if cfg['name'] == name:
                    return cfg
        raise ValueError(f"配置中未找到插件: {name}")

    def get_plugins_by_type(self, plugin_type: str) -> List[IPlugin]:
        """获取指定类型的所有插件"""
        # 根据类型过滤
        result = []
        for name, plugin in self.plugins.items():
            if isinstance(plugin, self._get_plugin_interface(plugin_type)):
                result.append(plugin)
        return result

    def _get_plugin_interface(self, plugin_type: str):
        """获取插件接口类"""
        mapping = {
            'data_channels': IDataChannelPlugin,
            'monitors': IMonitorPlugin,
            'analyzers': IAnalyzerPlugin,
            'exporters': IExporterPlugin
        }
        return mapping.get(plugin_type, IPlugin)
```

---

### 3.2 EventBus（事件总线）

用于插件间解耦通信：

```python
from typing import Callable, Dict, List

class EventBus:
    """事件总线（插件间通信）"""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event: str, callback: Callable):
        """订阅事件

        Args:
            event: 事件名（如 "frame_received", "anomaly_detected"）
            callback: 回调函数
        """
        if event not in self.subscribers:
            self.subscribers[event] = []
        self.subscribers[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable):
        """取消订阅"""
        if event in self.subscribers:
            self.subscribers[event].remove(callback)

    def publish(self, event: str, data: Any):
        """发布事件

        Args:
            event: 事件名
            data: 事件数据
        """
        for callback in self.subscribers.get(event, []):
            try:
                callback(data)
            except Exception as e:
                print(f"❌ 事件处理错误: {event}")
                print(f"   {e}")

    def publish_async(self, event: str, data: Any):
        """异步发布事件（不阻塞）"""
        import threading
        thread = threading.Thread(target=self.publish, args=(event, data))
        thread.start()
```

**EventBus使用示例**：

```python
# 在 AnomalyDetector 中发布事件
class MissedAlertDetector(IAnalyzerPlugin):
    def on_init(self, config):
        # ...
        self.event_bus = event_bus  # 由 PluginManager 注入

    def analyze(self, frame):
        anomalies = []
        # ... 检测逻辑 ...

        # 发布事件
        for anomaly in anomalies:
            self.event_bus.publish("anomaly_detected", anomaly)

        return anomalies

# 在 NotificationPlugin 中订阅事件
class NotificationPlugin(IMonitorPlugin):
    def on_init(self, config):
        # 订阅异常事件
        event_bus.subscribe("anomaly_detected", self.on_anomaly)

    def on_anomaly(self, anomaly: Anomaly):
        """接收异常通知"""
        if anomaly.severity == "high":
            # 发送邮件/短信告警
            self.send_alert(anomaly)
```

---

## 4. 配置文件规范

### 4.1 配置文件结构

```yaml
# plugins/plugin_config.yaml
plugins:
  # 数据通道插件
  data_channels:
    - name: "OBBChannel"
      module: "lcps_observer.channels.obb_channel"
      class: "OBBChannel"
      enabled: true
      config:
        port: 5555
        compression: "zlib"

    - name: "PointCloudChannel"
      module: "lcps_observer.channels.pointcloud_channel"
      enabled: true
      config:
        port: 5556
        downsample: true
        voxel_size: 0.1

    - name: "StatusChannel"
      module: "lcps_observer.channels.status_channel"
      enabled: true
      config:
        port: 5557

    - name: "ThermalChannel"  # 用户自定义
      module: "plugins.thermal_channel"
      enabled: false
      config:
        port: 5559
        image_size: [640, 480]

  # 监控插件
  monitors:
    - name: "LiveMonitor"
      module: "lcps_observer.monitors.live_monitor"
      enabled: true
      config:
        fps_target: 30

    - name: "LifecycleMonitor"
      module: "lcps_observer.monitors.lifecycle_monitor"
      enabled: true
      config:
        alert_on_error: true

    - name: "HeatmapMonitor"  # 用户自定义
      module: "plugins.heatmap_monitor"
      enabled: false
      config:
        grid_size: 0.5
        map_size: 100

  # 分析插件
  analyzers:
    - name: "MissedAlertDetector"
      module: "lcps_observer.analyzers.missed_alert"
      enabled: true
      config:
        danger_zones:
          - { name: "Zone1", x_min: 0, y_min: 0, x_max: 10, y_max: 10 }
          - { name: "Zone2", x_min: -10, y_min: -10, x_max: 0, y_max: 0 }
        min_obstacle_points: 50

    - name: "FalseAlarmDetector"
      module: "lcps_observer.analyzers.false_alarm"
      enabled: true
      config:
        threshold: 0.5

  # 导出插件
  exporters:
    - name: "HDF5Recorder"
      module: "lcps_observer.exporters.hdf5_recorder"
      enabled: true
      config:
        output_dir: "/data/recordings"
        compression: "zstd"
        level: 3

    - name: "MLDatasetExporter"
      module: "lcps_observer.exporters.ml_dataset"
      enabled: false
      config:
        format: "KITTI"
        output_dir: "/data/ml_datasets"
        train_val_split: 0.8
```

### 4.2 配置验证器

```python
from schema import Schema, And, Or, Optional

plugin_config_schema = Schema({
    'plugins': {
        'data_channels': [
            {
                'name': str,
                'module': str,
                Optional('class'): str,
                'enabled': bool,
                Optional('config'): dict
            }
        ],
        'monitors': [
            {
                'name': str,
                'module': str,
                Optional('class'): str,
                'enabled': bool,
                Optional('config'): dict
            }
        ],
        'analyzers': [
            {
                'name': str,
                'module': str,
                Optional('class'): str,
                'enabled': bool,
                Optional('config'): dict
            }
        ],
        'exporters': [
            {
                'name': str,
                'module': str,
                Optional('class'): str,
                'enabled': bool,
                Optional('config'): dict
            }
        ]
    }
})

def validate_config(config: dict):
    """验证配置文件"""
    try:
        plugin_config_schema.validate(config)
        return True, None
    except Exception as e:
        return False, str(e)
```

---

## 5. 插件开发SDK

### 5.1 项目结构

```
my_custom_plugin/
├── README.md                 # 插件说明
├── setup.py                  # 安装脚本（可选）
├── requirements.txt          # 依赖
├── __init__.py
├── my_plugin.py              # 插件实现
├── tests/
│   ├── __init__.py
│   └── test_my_plugin.py     # 单元测试
└── examples/
    └── plugin_config.yaml    # 配置示例
```

### 5.2 开发流程

**Step 1: 创建插件模板**

```bash
mkdir -p plugins/my_custom_plugin
cd plugins/my_custom_plugin

# 创建基本文件
touch __init__.py my_plugin.py README.md requirements.txt
```

**Step 2: 实现插件接口**

```python
# my_plugin.py
from lcps_observer.plugins import IAnalyzerPlugin, Anomaly
from typing import Dict, Any, List

class MyCustomDetector(IAnalyzerPlugin):
    """自定义检测器（用户实现）"""

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "MyCustomDetector",
            "version": "1.0.0",
            "author": "Your Name",
            "description": "自定义异常检测器"
        }

    def on_init(self, config: Dict[str, Any]):
        # 从配置读取参数
        self.threshold = config.get('threshold', 10)

    def analyze(self, frame: SyncedFrame) -> List[Anomaly]:
        # 实现检测逻辑
        anomalies = []

        # 示例：检测OBB数量异常
        if 'obb' in frame.data:
            obb_count = len(frame.data['obb']['obbs'])
            if obb_count > self.threshold:
                anomalies.append(Anomaly(
                    type="custom_too_many_obbs",
                    severity="medium",
                    timestamp=frame.timestamp,
                    message=f"OBB数量 ({obb_count}) 超过阈值 ({self.threshold})"
                ))

        return anomalies

    def on_enable(self):
        print(f"MyCustomDetector: 已启用（阈值={self.threshold}）")

    def on_disable(self):
        pass

    def on_destroy(self):
        pass
```

**Step 3: 编写单元测试**

```python
# tests/test_my_plugin.py
import pytest
from my_plugin import MyCustomDetector
from lcps_observer.data_types import SyncedFrame

def test_detector_threshold():
    """测试阈值检测"""
    detector = MyCustomDetector()
    detector.on_init({'threshold': 5})

    # 创建测试数据（6个OBB，超过阈值）
    frame = SyncedFrame(
        timestamp=1.0,
        data={
            'obb': {
                'obbs': [{'id': i} for i in range(6)]
            }
        }
    )

    # 执行检测
    anomalies = detector.analyze(frame)

    # 验证结果
    assert len(anomalies) == 1
    assert anomalies[0].type == "custom_too_many_obbs"
    assert anomalies[0].severity == "medium"
```

**Step 4: 配置插件**

```yaml
# examples/plugin_config.yaml
plugins:
  analyzers:
    - name: "MyCustomDetector"
      module: "plugins.my_custom_plugin.my_plugin"
      class: "MyCustomDetector"
      enabled: true
      config:
        threshold: 10
```

**Step 5: 测试插件**

```bash
# 运行单元测试
python -m pytest plugins/my_custom_plugin/tests/

# 在实际环境中测试
python lcps_observer.py --config plugins/my_custom_plugin/examples/plugin_config.yaml
```

---

## 6. 内置插件参考（8个）

| 插件名 | 类型 | 功能 | 配置示例 |
|--------|------|------|---------|
| **OBBChannel** | DataChannel | 接收OBB数据（端口5555） | `port: 5555, compression: "zlib"` |
| **PointCloudChannel** | DataChannel | 接收点云数据（端口5556） | `port: 5556, downsample: true, voxel_size: 0.1` |
| **StatusChannel** | DataChannel | 接收LCPS状态（端口5557） | `port: 5557` |
| **ImageChannel** | DataChannel | 接收图像数据（端口5558，可选） | `port: 5558, format: "jpeg"` |
| **LiveMonitor** | Monitor | 实时3D可视化 + HUD | `fps_target: 30` |
| **LifecycleMonitor** | Monitor | LCPS生命周期监控 | `alert_on_error: true` |
| **MissedAlertDetector** | Analyzer | 漏报检测 | `danger_zones: [...], min_obstacle_points: 50` |
| **FalseAlarmDetector** | Analyzer | 误报检测 | `threshold: 0.5` |
| **HDF5Recorder** | Exporter | HDF5数据录制 | `output_dir: "/data", compression: "zstd"` |
| **MLDatasetExporter** | Exporter | ML数据集导出 | `format: "KITTI", train_val_split: 0.8` |

---

## 7. 最佳实践

### 7.1 插件设计原则

1. **单一职责** (Single Responsibility)
   - 每个插件只做一件事
   - 避免功能耦合

2. **独立性** (Independence)
   - 插件不应依赖其他插件
   - 通过EventBus通信，而非直接调用

3. **配置驱动** (Configuration Driven)
   - 所有参数通过配置文件传入
   - 提供默认值和验证

4. **错误隔离** (Error Isolation)
   - 捕获所有异常，避免crash核心系统
   - 提供清晰的错误信息

5. **性能优先** (Performance First)
   - `on_frame()` 必须快速（< 10ms）
   - 耗时操作使用异步或后台线程

### 7.2 常见问题和解决方案

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| **插件加载失败** | 模块路径错误 | 检查 `module` 配置，确保 PYTHONPATH 正确 |
| **配置验证失败** | 缺少必需参数 | 在 `on_init()` 中验证并提供默认值 |
| **性能下降** | `on_frame()` 太慢 | 使用性能分析工具，优化算法或异步处理 |
| **插件崩溃** | 未捕获异常 | 使用 try-except 包裹所有接口方法 |
| **热加载失败** | 模块缓存 | 使用 `importlib.reload()` 刷新模块 |

### 7.3 性能优化建议

```python
# ❌ 不推荐：每帧都创建新对象
class SlowPlugin(IMonitorPlugin):
    def on_frame(self, frame):
        data = np.zeros((1000, 1000))  # 每帧分配内存
        # ...

# ✅ 推荐：复用对象
class FastPlugin(IMonitorPlugin):
    def on_init(self, config):
        self.buffer = np.zeros((1000, 1000))  # 初始化时分配

    def on_frame(self, frame):
        self.buffer.fill(0)  # 复用内存
        # ...
```

---

## 8. 版本兼容性

### 8.1 插件API版本

| API版本 | 发布日期 | 主要变更 | 兼容性 |
|---------|---------|---------|--------|
| **v1.0** | 2025-12-24 | 初始版本（4类插件） | - |
| **v2.0** | TBD | EventBus增强 + 异步支持 | 向后兼容 v1.0 |

### 8.2 版本检查

```python
from lcps_observer import __version__

class MyPlugin(IPlugin):
    def on_init(self, config):
        # 检查 API 版本
        required_version = "1.0.0"
        if __version__ < required_version:
            raise RuntimeError(f"需要 LCPS Observer >= {required_version}")
```

---

## 9. 文档和支持

### 9.1 参考文档

- [LCPS综合设计方案](LCPS_COMPREHENSIVE_DESIGN.md)
- [ADR v2.0 - 插件化架构](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计)
- [HDF5格式规范](LCPS_HDF5_FORMAT.md)
- [数据协议规范](LCPS_DATA_PROTOCOL.md)

### 9.2 社区支持

- 问题反馈：GitHub Issues
- 插件分享：plugins/ 目录下提交PR
- 技术讨论：内部Slack频道

---

**版本历史**：
- v2.0 (2025-12-24): 整合claudedocs插件v2内容，增加EventBus、热加载、8个内置插件
- v1.0 (2025-12-24): 初始版本
