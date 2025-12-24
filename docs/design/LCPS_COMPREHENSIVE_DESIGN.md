# LCPS 观测调试工具 - 综合设计方案

**版本**: 2.0
**创建日期**: 2025-12-24
**状态**: 设计完成，待评审
**作者**: Claude (基于PRD和现有ADR)

## 文档目的

本文档提供LCPS观测调试工具的完整设计方案，整合了PRD需求、现有架构决策（4个ADR）和完整的实施计划。

## 关联文档

- **需求文档**: `claudedocs/PRD_LCPS工具咨询.md`
- **架构决策**: `docs/management/PLANNING.md` (ADR-001~004)
- **详细规范**:
  - [数据协议规范](LCPS_DATA_PROTOCOL.md)
  - [插件架构指南](LCPS_PLUGIN_ARCHITECTURE.md)
  - [异常检测规范](LCPS_ANOMALY_DETECTION.md)
  - [HDF5格式规范](LCPS_HDF5_FORMAT.md)
  - [实施计划](LCPS_IMPLEMENTATION_PLAN.md)

---

## 1. 需求概述

### 1.1 核心问题

LCPS（激光碰撞预防系统）作为关键安全功能，面临以下挑战：

1. **安全风险**
   - 逻辑复杂，少量改动可能导致漏报（应报警未报警）
   - 生命周期管理问题（未按预期开启/关闭）
   - 障碍物生成不及预期（不同堆场环境、激光配置）

2. **调试困难**
   - 问题定位困难，需要获取中间数据恢复场景
   - 某些漏报场景数据缺失，难以复现
   - 依赖本地log和存储的context，分析效率低

3. **数据传输限制**
   - 点云数据量大，难以实时传输观测
   - 带宽有限，会影响其他功能

### 1.2 核心需求（优先级排序）

| 优先级 | 需求 | 关键指标 |
|--------|------|---------|
| **P0** | 实时监控LCPS防护状态 | 延迟 < 100ms，FPS ≥ 30 |
| **P0** | 漏报/误报检测 | 检测率 ≥ 95% |
| **P1** | 数据录制和回放 | 完整性 100%，压缩率 ≥ 70% |
| **P1** | 问题定位和调试 | 定位时间 < 5分钟 |
| **P2** | 可扩展性（不修改代码增加观测维度） | 插件化架构 |
| **P2** | 标准化数据格式 | 支持深度学习等高级分析 |

### 1.3 约束条件

1. **非侵入性**: 不能影响LCPS主功能（非阻塞发送、独立进程）
2. **带宽限制**: crane系统与观测工具间带宽有限
3. **协同开发**: icrane LCPS和观测工具需协同修改
4. **迭代策略**: Python先行（快速验证），后续C++ QT版本

---

## 2. 总体架构

### 2.1 系统全局架构

```
┌────────────────────────────────────────────────────────────────┐
│                    LCPS System (C++)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Point Cloud  │  │ Obstacle Gen │  │ Alert Logic  │        │
│  │  Processing  │→ │  & Tracking  │→ │  & Control   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│         │                  │                  │                │
│         └──────────────────┴──────────────────┘                │
│                            │ (ZMQ PUB, 非阻塞)                 │
└────────────────────────────┼───────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
      :5556 PC          :5555 OBB           :5557 Status
         │                   │                   │
         └───────────────────┴───────────────────┘
                             │
    ┌────────────────────────┴────────────────────────┐
    │         LCPS Observer Tool (Python/C++)         │
    │  ┌──────────────────────────────────────────┐  │
    │  │  Layer 1: Data Acquisition               │  │
    │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ │  │
    │  │  │ OBB Chan │ │  PC Chan │ │Stat Chan │ │  │
    │  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ │  │
    │  └───────┼────────────┼────────────┼────────┘  │
    │  ┌───────┴────────────┴────────────┴────────┐  │
    │  │  Layer 2: Data Processing               │  │
    │  │  ┌────────────┐ ┌──────────────────────┐│  │
    │  │  │Synchronizer│ │ Validator & Recorder ││  │
    │  │  └─────┬──────┘ └──────────┬───────────┘│  │
    │  └────────┼───────────────────┼────────────┘  │
    │  ┌────────┴───────────────────┴────────────┐  │
    │  │  Layer 3: Analysis & Detection          │  │
    │  │  ┌──────────────┐ ┌──────────────────┐  │  │
    │  │  │   Anomaly    │ │   Performance    │  │  │
    │  │  │   Detector   │ │    Analyzer      │  │  │
    │  │  └──────┬───────┘ └────────┬─────────┘  │  │
    │  └─────────┼──────────────────┼────────────┘  │
    │  ┌─────────┴──────────────────┴────────────┐  │
    │  │  Layer 4: Visualization & UI            │  │
    │  │  ┌─────────┐ ┌────────┐ ┌────────────┐  │  │
    │  │  │ 3D View │ │ HUD    │ │ Timeline   │  │  │
    │  │  │(OpenGL) │ │(ImGui) │ │  Control   │  │  │
    │  │  └─────────┘ └────────┘ └────────────┘  │  │
    │  └──────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────┘
                       │
                       v
            ┌──────────────────────┐
            │  HDF5 Recording File │
            │  (zstd compressed)   │
            └──────────────────────┘
```

### 2.2 分层架构设计（基于ADR-001）

#### Layer 1: Data Acquisition（数据采集层）

**职责**: 从多个ZMQ端口接收数据，解析并传递给处理层

**核心组件**:
```python
class MultiChannelReceiver:
    """多通道接收器（复用recvOBB.py的多线程架构）"""

    def __init__(self, config: ReceiverConfig):
        self.channels: List[DataChannel] = []
        self.data_queue = queue.Queue(maxsize=100)
        self.stop_event = threading.Event()

    def add_channel(self, channel: DataChannel):
        """添加数据通道（插件化设计）"""

    def start(self):
        """启动所有接收线程"""

    def stop(self):
        """优雅停止所有线程"""
```

**数据通道（DataChannel）**:
```python
class DataChannel(ABC):
    """抽象数据通道（支持插件扩展）"""

    @abstractmethod
    def get_config(self) -> ChannelConfig:
        """返回通道配置（端口、订阅主题、数据格式）"""

    @abstractmethod
    def parse_data(self, raw_data: bytes) -> DataFrame:
        """解析原始数据为标准DataFrame"""

    def receive_thread(self):
        """接收线程主循环"""
```

**内置通道**:
- `OBBChannel` (端口5555): 接收OBB数据
- `PointCloudChannel` (端口5556): 接收点云数据（可选下采样）
- `StatusChannel` (端口5557): 接收LCPS状态
- `ImageChannel` (端口5558, 可选): 接收图像数据

#### Layer 2: Data Processing（数据处理层）

**职责**: 时间戳同步、数据验证、录制和回放

**核心组件**:

1. **DataSynchronizer（数据同步器）**
```python
class DataSynchronizer:
    """时间戳对齐和数据同步"""

    def __init__(self, tolerance_ms: float = 50):
        self.tolerance_ms = tolerance_ms  # 时间戳容忍度
        self.buffers: Dict[str, Deque] = {}  # 每个通道的缓冲

    def add_frame(self, channel: str, frame: DataFrame):
        """添加数据帧到缓冲"""

    def get_synchronized_frame(self) -> Optional[SyncedFrame]:
        """获取时间戳对齐的数据帧"""
        # 返回所有通道在同一时间点的数据
```

2. **DataRecorder（数据录制器，基于ADR-002）**
```python
class DataRecorder:
    """HDF5数据录制器"""

    def __init__(self, output_path: Path, compression="zstd", level=3):
        self.file = h5py.File(output_path, 'w')
        self.compression = compression
        self.level = level

    def start_recording(self):
        """开始录制"""

    def write_frame(self, synced_frame: SyncedFrame):
        """写入同步后的数据帧"""

    def stop_recording(self):
        """停止录制并写入元数据"""
```

3. **DataReplayer（数据回放器）**
```python
class DataReplayer:
    """HDF5数据回放器"""

    def __init__(self, file_path: Path):
        self.file = h5py.File(file_path, 'r')

    def seek(self, timestamp: float):
        """跳转到指定时间戳"""

    def play(self, speed: float = 1.0):
        """以指定速度回放"""

    def get_frame(self) -> Optional[SyncedFrame]:
        """获取当前帧"""
```

#### Layer 3: Analysis & Detection（分析检测层）

**职责**: 异常检测、性能分析、报告生成

**核心组件**:

1. **AnomalyDetector（异常检测器）**
```python
class AnomalyDetector:
    """异常检测器（插件化设计）"""

    def __init__(self):
        self.detectors: List[AnomalyPlugin] = []

    def register_detector(self, detector: AnomalyPlugin):
        """注册检测插件"""

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        """执行所有检测器，返回异常列表"""
```

**内置检测器**:
- `MissedAlertDetector`: 漏报检测
- `FalseAlarmDetector`: 误报检测
- `LifecycleMonitor`: 生命周期异常监控
- `PointCloudDensityChecker`: 点云密度异常检测

2. **PerformanceAnalyzer（性能分析器）**
```python
class PerformanceAnalyzer:
    """性能分析和统计"""

    def analyze_pointcloud_density(self, frames: List[SyncedFrame]):
        """分析点云密度分布"""

    def analyze_obb_statistics(self, frames: List[SyncedFrame]):
        """分析OBB统计（数量、大小、位置分布）"""

    def generate_report(self) -> AnalysisReport:
        """生成分析报告（HTML/PDF）"""
```

#### Layer 4: Visualization & UI（可视化层）

**职责**: 3D渲染、HUD显示、时间轴控制

**核心组件**:

1. **Visualizer3D（3D可视化器）**
```python
class Visualizer3D:
    """OpenGL 3D渲染器（复用现有代码）"""

    def render_pointcloud(self, points: np.ndarray):
        """渲染点云"""

    def render_obbs(self, obbs: List[OBB]):
        """渲染OBB（线框或实体）"""

    def render_danger_zones(self, zones: List[Zone]):
        """渲染危险区域（半透明）"""
```

2. **HUDManager（HUD管理器）**
```python
class HUDManager:
    """ImGui HUD管理器（基于现有实现）"""

    def render_status_panel(self, status: LCPSStatus):
        """渲染状态面板"""

    def render_metrics_panel(self, metrics: Metrics):
        """渲染性能指标"""

    def render_anomaly_alerts(self, anomalies: List[Anomaly]):
        """渲染异常警告（高亮显示）"""

    def render_timeline(self, replayer: DataReplayer):
        """渲染时间轴控制（Phase 2）"""
```

### 2.3 数据流

```
ZMQ Data → MultiChannelReceiver (Queue)
    → DataSynchronizer (时间戳对齐)
    → [DataRecorder (可选录制)]
    → AnomalyDetector (异常检测)
    → PerformanceAnalyzer (性能分析)
    → Visualizer3D + HUDManager (显示)
```

**回放模式数据流**:
```
HDF5 File → DataReplayer
    → [跳转/速度控制]
    → AnomalyDetector (重新分析)
    → PerformanceAnalyzer (离线分析)
    → Visualizer3D + HUDManager (显示)
```

---

## 3. 关键技术决策

### 3.1 已确定的ADR（PLANNING.md）

| ADR | 决策 | 理由 |
|-----|------|------|
| **ADR-001** | 分层架构（4层） | 职责清晰、可测试、可扩展 |
| **ADR-002** | HDF5 + zstd | 74%压缩率、支持大规模时序数据 |
| **ADR-003** | 点云下采样 | 90%带宽优化、满足实时性要求 |
| **ADR-004** | Python先行 | 快速验证、降低风险、后续C++重写 |

### 3.2 新增技术决策

#### 决策5: 插件化架构（满足可扩展性需求）

**背景**: PRD要求"不修改代码就能增加观测维度"

**决策**: 采用插件化架构 + 配置文件驱动

**方案**:
```python
# plugin_config.yaml
plugins:
  channels:
    - name: "OBBChannel"
      port: 5555
      enabled: true
    - name: "CustomChannel"  # 用户自定义
      module: "plugins.custom_channel"
      port: 5559
      enabled: false

  analyzers:
    - name: "MissedAlertDetector"
      enabled: true
      config:
        danger_zones: [...]
    - name: "CustomAnalyzer"  # 用户自定义
      module: "plugins.custom_analyzer"
      enabled: false
```

**优点**:
- ✅ 不修改核心代码即可扩展
- ✅ 配置化管理
- ✅ 支持第三方插件

**缺点**:
- ⚠️ 增加系统复杂度
- ⚠️ 需要插件接口文档

**权衡**: 可扩展性收益 > 复杂度成本

---

## 4. 非功能需求

### 4.1 性能指标

| 指标 | 目标值 | 验收标准 |
|------|--------|---------|
| **实时性** | 端到端延迟 < 100ms | P99延迟 < 150ms |
| **渲染帧率** | FPS ≥ 30 | 稳定30 FPS（无抖动） |
| **录制性能** | 写入延迟 < 10ms | 不影响实时渲染 |
| **回放性能** | 支持1x~10x速度 | 快进无卡顿 |
| **内存占用** | < 500MB（实时模式） | 峰值 < 1GB |
| **磁盘占用** | 1小时录制 < 2GB | 压缩率 ≥ 70% |

### 4.2 可靠性

- **数据完整性**: 100%（通过校验和验证）
- **异常恢复**: 数据流中断后自动重连（最多3次）
- **优雅退出**: 确保录制数据完整保存

### 4.3 可用性

- **学习成本**: 新用户15分钟内上手基础功能
- **文档完整性**: API文档 + 用户手册 + 开发指南
- **错误提示**: 清晰的错误信息和解决建议

---

## 5. 实施计划概览

详细计划见 [LCPS_IMPLEMENTATION_PLAN.md](LCPS_IMPLEMENTATION_PLAN.md)

### Phase 1: MVP（2周）
- MultiChannelReceiver (OBB + PC + Status)
- DataSynchronizer
- DataRecorder (HDF5)
- 基础3D可视化 + HUD

**交付物**: 可实时观测和录制的工具

### Phase 2: 调试功能（3周）
- DataReplayer（回放 + 时间轴）
- AnomalyDetector（基础规则）
- PerformanceAnalyzer
- 报告导出

**交付物**: 完整的调试和分析工具

### Phase 3: 高级功能（3周）
- 插件架构实现
- 高级异常检测（基于历史数据）
- 自动化测试
- 配置系统

**交付物**: 生产级Python工具

### Phase 4: C++ QT版本（6周）
- 基于mmtoolkit2框架
- C++ QT界面
- 性能优化
- 部署方案

**交付物**: 高性能生产工具

---

## 6. 风险和缓解措施

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 带宽不足导致丢帧 | 中 | 高 | 点云下采样 + 自适应码率 |
| 时间戳同步误差过大 | 低 | 中 | NTP同步 + 容忍度配置 |
| HDF5写入性能瓶颈 | 低 | 中 | 异步写入 + 批量提交 |
| 插件接口不稳定 | 中 | 低 | 版本管理 + 兼容性测试 |
| C++迁移成本高 | 中 | 中 | Python验证 + 渐进迁移 |

---

## 7. 下一步行动

1. **技术评审**: 与团队评审本设计方案
2. **详细设计**: 完善各子系统详细设计文档
3. **原型开发**: 启动Phase 1 MVP开发
4. **icrane协同**: 与LCPS团队协调数据发送端修改

---

## 附录

### A. 术语表

| 术语 | 定义 |
|------|------|
| **LCPS** | Laser Collision Prevention System（激光碰撞预防系统） |
| **OBB** | Oriented Bounding Box（定向包围盒） |
| **漏报** | 应该报警但未报警（Missed Alert） |
| **误报** | 不应报警但报警了（False Alarm） |
| **下采样** | 减少点云数量以降低数据量（Downsampling） |
| **HDF5** | Hierarchical Data Format 5（层次化数据格式） |

### B. 参考资料

- ZeroMQ Guide: https://zguide.zeromq.org/
- HDF5 Documentation: https://docs.hdfgroup.org/
- Ultrathink Design Philosophy: PLANNING.md § Ultrathink原则

---

**文档版本历史**:
- v2.0 (2025-12-24): 完整设计方案（基于PRD + 4个ADR）
- v1.0 (2025-12-24): 初始架构（4个ADR）
