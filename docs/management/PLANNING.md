# OBBDemo 项目规划

**最后更新**: 2025-12-24

## 项目概述

### 项目目标

OBBDemo 是一个基于 ZeroMQ 的实时 3D 数据可视化系统，用于演示 OBB (Oriented Bounding Box) 数据的传输和渲染。

**核心功能**:
- 实时数据传输（使用 ZeroMQ PUB/SUB 模式）
- 3D 数据可视化（使用 PyOpenGL）
- 支持数据压缩传输（zlib）
- 支持点云数据渲染
- 跨平台支持（Linux/Windows）
- **LCPS 观测和调试工具**（新增 2025-12-24）

**应用场景**:
- 3D 物体检测结果可视化
- 实时传感器数据监控
- 机器人感知系统调试
- 多模态数据融合展示
- **LCPS 安全系统的实时观测和问题诊断**（新增）

---

## 技术架构

### 系统架构

```
┌─────────────────┐         ZMQ PUB/SUB          ┌──────────────────┐
│  Sender (C++)   │ ──────── tcp://6555 ────────>│  Receiver (Py)   │
│                 │                               │                  │
│ - 生成 OBB 数据  │                               │ - 接收 OBB 数据   │
│ - JSON 序列化   │                               │ - 解析数据       │
│ - ZMQ 发布      │                               │ - OpenGL 渲染    │
└─────────────────┘                               └──────────────────┘
                                                          │
                                                          v
                                                  ┌──────────────────┐
                                                  │  LCPSViewer (Py) │
                                                  │  - 增强版查看器   │
                                                  └──────────────────┘
```

**数据流**:
1. Sender 生成 OBB 数据（type, position, rotation, size）
2. 数据序列化为 JSON 格式
3. 通过 ZMQ PUB socket 发布
4. Receiver 通过 ZMQ SUB socket 订阅
5. 支持三种接收模式：
   - Normal: 直接接收 JSON
   - Compressed: 接收 zlib 压缩的 BSON
   - Compressed OBB: 仅压缩 OBB 数据
6. OpenGL 渲染 3D 线框立方体

### 多线程架构（2025-12-22）

**状态**: ✅ 已实现（2025-12-22）

**接收和渲染分离设计**:

为解决 ZMQ 接收阻塞导致的渲染帧率不稳定问题，接收端（recvOBB.py）采用多线程架构：

```
主线程（Main Thread）          接收线程（Receiver Thread）
══════════════════════         ════════════════════════════
Pygame 主循环                  threading.Thread(daemon=True)
  ↓                               ↓
检查 Queue (非阻塞)             while not stop_event.is_set():
  ↓                               ↓
更新 OBB 列表                   ZMQ recv() + 解析数据
  ↓                               ↓
OpenGL 渲染（60 FPS）          queue.put(data, block=False)
  ↓                               ↓
处理事件和交互                  异常处理和重试
  ↓
pygame.display.flip()
```

**核心组件**:
- **Queue**: `queue.Queue(maxsize=10)` - 线程安全的数据缓冲
- **Event**: `threading.Event()` - 优雅退出信号
- **主线程**: Pygame 主循环 + OpenGL 渲染（保持 60 FPS）
- **接收线程**: ZMQ 数据接收和解析（I/O 操作不阻塞渲染）

**关键技术决策**:
1. **线程模型**: threading.Thread（而非 multiprocessing）
   - 理由：OpenGL 上下文必须在创建它的线程（主线程）中使用
   - ZMQ recv() 是 I/O 操作，threading 足够（GIL 会释放）

2. **同步机制**:
   - Queue 大小限制为 10（保留最新数据，避免内存无限增长）
   - 非阻塞操作：`queue.get_nowait()` 和 `queue.put(block=False)`
   - 如果 Queue 满，清空最旧数据，放入最新数据

3. **退出机制**:
   - 使用 `threading.Event()` 信号通知接收线程停止
   - 主线程退出前调用 `receiver_thread.join(timeout=2)`
   - 优雅退出，避免线程泄漏

**性能目标**:
- 渲染帧率：稳定 60 FPS（不受接收阻塞影响）✅
- 最大延迟：10 帧（Queue maxsize=10）✅
- CPU 开销：略微增加（多一个 I/O 线程）✅

**实现细节**:
- **接收线程**: `_receiver_thread_func()` - daemon 线程，循环接收 ZMQ 数据
- **数据传递**: `queue.Queue(maxsize=10)` - 线程安全，非阻塞操作
- **退出机制**: `threading.Event()` + `join(timeout=2)` - 优雅退出
- **主循环**: Pygame 主循环 + OpenGL 渲染（60 FPS），从 Queue 获取数据

**架构决策**: 详见 [ADR 2025-12-22: Threading + Queue 架构](#adr-2025-12-22-threading--queue-架构)

### LCPS 观测和调试工具架构（2025-12-24）

**状态**: 📋 规划中

**设计目标**:
- 实时观测 LCPS 防护状态（点云、OBB、系统状态、图像）
- 问题定位和调试（漏报、误报检测）
- 数据录制和回放（完整场景恢复）
- 可扩展性（插件化架构，不修改代码即可扩展观测维度）
- 非侵入性设计（不影响 LCPS 主功能）

**完整 ADR 文档**: [ADR v2.0: LCPS 观测和调试工具架构设计](../adr/2025-12-24-lcps-tool-architecture-v2.md)

#### 4 层分层架构设计

基于 ADR-001 的决策，采用分层架构模式（Layered Architecture Pattern）：

```
                    ZMQ PUB/SUB (多端口)
LCPS System ──────────────────────────────┐
  │ :6555 OBB (always)                    │
  │ :6556 PointCloud (downsampled)        │
  │ :6557 Status                          │
  │ :6558 Image (optional)                │
                                          │
                                          v
              ┌───────────────────────────────────┐
              │  Layer 1: Data Acquisition        │
              │  - MultiChannelReceiver           │
              │  - OBB/PC/Status/Image Channels   │
              └─────────────┬─────────────────────┘
                            │
                            v
              ┌───────────────────────────────────┐
              │  Layer 2: Data Processing         │
              │  - DataSynchronizer               │
              │  - DataRecorder (HDF5)            │
              │  - DataReplayer                   │
              └─────────────┬─────────────────────┘
                            │
                            v
              ┌───────────────────────────────────┐
              │  Layer 3: Analysis & Detection    │
              │  - AnomalyDetector (插件化)        │
              │  - PerformanceAnalyzer            │
              └─────────────┬─────────────────────┘
                            │
                            v
              ┌───────────────────────────────────┐
              │  Layer 4: Visualization & UI      │
              │  - Visualizer3D (OpenGL)          │
              │  - HUDManager (ImGui)             │
              └───────────────────────────────────┘
```

**层次职责**:
- **Layer 1 (数据采集)**: 从多个 ZMQ 端口接收数据，数据解析和初步验证
- **Layer 2 (数据处理)**: 时间戳同步、数据录制、回放控制
- **Layer 3 (分析检测)**: 异常检测、性能分析、报告生成（插件化）
- **Layer 4 (可视化)**: 3D 渲染、HUD 显示、用户交互

#### 插件化架构设计

基于 ADR-005 的决策，采用插件化架构（Plugin Architecture Pattern）+ 配置文件驱动：

**插件分类**（4 类）:
1. **DataChannelPlugin**: 扩展数据源（新增 ZMQ 端口、自定义数据格式）
2. **MonitorPlugin**: 实时监控和可视化（热力图、轨迹预测等）
3. **AnalyzerPlugin**: 异常检测和分析（漏报/误报检测、性能分析）
4. **ExporterPlugin**: 数据导出和格式转换（ML 数据集、KITTI 格式等）

**内置插件** (8 个):
- OBBChannel, PointCloudChannel, StatusChannel, ImageChannel（数据通道）
- LiveMonitor, LifecycleMonitor（监控）
- MissedAlertDetector, FalseAlarmDetector（分析）
- HDF5Recorder, MLDatasetExporter（导出）

**配置驱动**: 使用 `plugin_config.yaml` 控制插件启用/禁用和参数配置

详细的插件开发指南见：[LCPS 插件架构指南](../design/LCPS_PLUGIN_ARCHITECTURE.md)

#### 核心模块

1. **MultiChannelReceiver（多通道接收器）** - Layer 1
   - 复用 recvOBB.py 的多线程架构
   - 每个数据源独立线程（OBB、PointCloud、Status、Image）
   - 通过 Queue 传递到主线程
   - 非阻塞发送（zmq.NOBLOCK）确保非侵入性

2. **DataRecorder（数据录制器）** - Layer 2
   - 格式：HDF5 + zstd 压缩（压缩率 ~74%）
   - 文件结构：obb_data/, pointcloud_data/, status_data/, image_data/, metadata
   - 随机访问：支持跳转到任意时间点（< 100ms）
   - 异步写入：批量提交，定期 flush（每 100 帧）

3. **AnomalyDetector（异常检测器）** - Layer 3（插件化）
   - 漏报检测：MissedAlertDetector（检测应报警未报警场景）
   - 误报检测：FalseAlarmDetector（检测不应报警但报警场景）
   - 生命周期监控：LifecycleMonitor（状态机异常检测）
   - 可配置规则：danger_zones, threshold 等参数

4. **Visualizer3D（3D 可视化器）** - Layer 4
   - OBB 渲染：线框立方体 + 颜色编码（类型、状态）
   - 点云渲染：VBO 优化（支持 100,000+ 点/帧）
   - 相机控制：FPS 相机、轨道相机
   - 性能目标：稳定 30 FPS

5. **PluginManager（插件管理器）** - Layer 3
   - 插件加载：根据 plugin_config.yaml 自动加载
   - 生命周期管理：on_init, on_enable, on_disable, on_destroy
   - 热加载：运行时加载/卸载插件（无需重启）
   - 事件总线：插件间解耦通信

#### 技术决策链接

完整的决策背景、量化数据、Ultrathink 评分、替代方案分析和实施细节请参考：

- [ADR-001: 4 层分层架构设计](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-1-分层架构设计)
- [ADR-002: HDF5 数据格式](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-2-hdf5-数据格式)
- [ADR-003: 点云下采样策略](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-3-点云下采样策略)
- [ADR-004: Python 先行策略](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-4-python-先行策略)
- [ADR-005: 插件化架构设计](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计)

#### 实现路线图

- **Phase 1 (MVP, 2 周)**: 4 层架构实现 + OBB/点云/状态接收 + HDF5 录制
- **Phase 2 (完整功能, 3 周)**: 插件系统 + 异常检测 + 回放和分析
- **Phase 3 (高级功能, 3 周)**: 图像支持 + 多视图 + 自动化报告
- **Phase 4 (C++ 迁移, 6 周)**: 高性能 C++ QT 版本

---

## 技术栈

### 编程语言

| 语言 | 版本 | 用途 | 比例 |
|------|------|------|------|
| **Python** | 3.x | 接收端、可视化 | 83% |
| **C++** | C++11 | 发送端 | 17% |

### 核心依赖

#### Python 依赖

**OBBDemo 基础功能**:

| 库 | 版本 | 用途 |
|---|------|------|
| **pyzmq** | 27.1.0+ | ZeroMQ Python 绑定 |
| **pygame** | 2.6.1+ | 窗口管理和事件循环 |
| **PyOpenGL** | 3.1.10+ | OpenGL 3D 渲染 |
| **numpy** | 2.4.0+ | 数值计算 |
| **pymongo** | 4.15.5+ | BSON 序列化 |
| **imgui[pygame]** | 2.0.0+ | ImGui Python 绑定 |

**LCPS 观测工具扩展**:

| 库 | 版本 | 用途 | ADR 引用 |
|---|------|------|---------|
| **h5py** | latest | HDF5 文件读写 | [ADR-002](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-2-hdf5-数据格式) |
| **zstandard** | latest | zstd 压缩（74% 压缩率）| [ADR-002](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-2-hdf5-数据格式) |
| **PyYAML** | latest | 插件配置文件解析 | [ADR-005](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计) |
| **open3d** | latest（可选）| 点云处理（下采样）| [ADR-003](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-3-点云下采样策略) |

#### C++ 依赖

| 库 | 版本 | 用途 |
|---|------|------|
| **libzmq** | 3+ | ZeroMQ 核心库 |
| **cppzmq** | latest | ZeroMQ C++ 头文件封装 |
| **nlohmann/json** | 3+ | JSON 序列化 |
| **Intel TBB** | latest | 并行计算（可选）|

#### 构建工具

| 工具 | 用途 |
|------|------|
| **CMake** | C++ 项目构建 |
| **PyInstaller** | Python 打包（LCPSViewer.spec）|

---

## 开发工作流

### Python 先行策略

基于 [ADR-004](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-4-python-先行策略) 的决策：

**Phase 1-3: Python 版本**（8 周）
- 快速验证架构可行性
- 复用现有 OBBViewer 代码（减少 50% 开发量）
- 获得早期用户反馈
- 性能满足调试需求

**Phase 4: C++ QT 迁移**（6 周）
- 渐进迁移：核心模块优先，UI 最后
- Python 版本作为参考实现
- 数据格式和通信协议保持一致
- 性能提升 ≥ 5 倍

**迁移顺序**:
1. MultiChannelReceiver → C++ ZMQ 模块
2. DataRecorder (HDF5) → C++ HDF5 模块
3. 插件系统 → C++ 插件框架
4. Visualizer → Qt3D/VTK
5. 部署打包 → CMake + CPack

### 构建和测试

**Python 开发**:
```bash
# 安装依赖（推荐使用 uv）
uv sync

# 运行 OBBViewer
uv run python LCPSViewer.py -a localhost:6555 -m n

# 运行测试（待实现）
uv run pytest tests/
```

**C++ 开发**:
```bash
# 构建
mkdir build && cd build
cmake ..
make

# 运行发送端
./sender
```

**集成测试**:
- 端到端测试：sender → receiver → 数据验证
- 性能测试：帧率、延迟、带宽测试
- 压力测试：大量 OBB、高频发送

### 部署流程

**Python 打包**（PyInstaller）:
```bash
uv sync --group dev
uv run pyinstaller LCPSViewer.spec
```

**C++ 打包**（CMake + CPack，待实现）:
```bash
cd build
cpack
```

---

## 代码标准

### 代码规范

**Python**:
- 遵循 PEP 8 风格指南
- 类名使用 CamelCase（如 `OBB`, `DataRecorder`）
- 函数名使用 snake_case（如 `draw_wire_cube`, `sync_frames`）
- 使用类型注解（推荐，特别是公共 API）
- 文档字符串：使用 Google 风格

**C++**:
- 遵循 C++11/17 标准
- 使用现代 C++ 特性（智能指针、lambda、auto 等）
- 变量名使用 camelCase
- 类名使用 PascalCase
- 避免裸指针，优先使用 `std::unique_ptr` / `std::shared_ptr`

### 插件开发规范

基于 [ADR-005](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计)：

**插件接口**:
```python
from abc import ABC, abstractmethod

class IPlugin(ABC):
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据（名称、版本、依赖）"""
        pass

    @abstractmethod
    def on_init(self, config: Dict[str, Any]):
        """初始化插件（传入配置）"""
        pass

    # ... 其他生命周期方法
```

**插件命名**:
- 文件名：`{category}_{name}.py`（如 `monitor_heatmap.py`）
- 类名：`{Name}{Category}`（如 `HeatmapMonitor`）
- 配置：`plugin_config.yaml`

**插件文档**:
- 必须提供 `get_metadata()` 返回描述信息
- README.md 说明用途、配置参数、依赖
- 代码注释清晰

详细的插件开发 SDK 和示例见：[LCPS 插件架构指南](../design/LCPS_PLUGIN_ARCHITECTURE.md)

### 配置管理

**网络配置**:
- 默认端口：6555 (OBB), 6556 (PointCloud), 6557 (Status), 6558 (Image)
  - **注**: 使用 6555-6558 以匹配 LCPS Server 实际端口配置
  - LCPS Server 使用 6555-6558 避免与其他服务冲突
- 默认协议：TCP
- ZMQ 模式：PUB/SUB
- 地址格式：`IP:PORT`（如 `localhost:6555`）

**渲染配置**:
- 默认分辨率：800x600
- 支持窗口缩放：✅
- 双缓冲：✅
- 透视投影：FOV 45°, near 0.1, far 50.0
- 目标帧率：60 FPS (OBBViewer), 30 FPS (LCPS Tool)

**HDF5 配置**:
- 压缩算法：zstd（Python: gzip, C++: zstd）
- 压缩级别：3（平衡速度和压缩率）
- 分块大小：(1, K, 3) 按帧分块
- Flush 频率：每 100 帧

---

## 测试策略

### 单元测试

**Python**:
- 框架：pytest
- 覆盖率目标：≥ 80%
- 关键模块：DataRecorder, DataSynchronizer, PluginManager

**C++**（待实现）:
- 框架：Google Test
- 覆盖率目标：≥ 70%

### 集成测试

**端到端测试**:
- sender → receiver → 数据验证
- 录制 → 回放 → 数据一致性检查
- 插件加载 → 运行 → 卸载

**性能测试**:
- 帧率稳定性（60 FPS @ OBBViewer）
- 延迟测试（< 100ms）
- 内存泄漏检测（长时间运行）

### 验证标准

基于 ADR v2.0 的验证标准：

**Layer 1（数据采集）**:
- [ ] 延迟 < 100ms
- [ ] 支持 4 个数据通道同时接收
- [ ] 非阻塞发送不影响 LCPS

**Layer 2（数据处理）**:
- [ ] HDF5 录制不影响 Layer 1 帧率
- [ ] 压缩率 ≥ 70%
- [ ] 支持跳转到任意时间点（延迟 < 100ms）

**Layer 3（分析检测）**:
- [ ] 异常检测准确率 ≥ 90%
- [ ] 插件故障隔离（一个插件崩溃不影响其他）

**Layer 4（可视化）**:
- [ ] 渲染稳定 30 FPS（LCPS Tool）
- [ ] 60 FPS（OBBViewer）

---

## 性能目标

### LCPS 观测工具性能指标

基于 [ADR v2.0 性能测试结果](../adr/2025-12-24-lcps-tool-architecture-v2.md#性能测试结果)：

**实时性**:
- 端到端延迟：< 100ms
- 渲染帧率：30 FPS（稳定）
- 数据接收频率：30 Hz

**带宽优化**:
- 点云下采样：90% 带宽节省（36 MB/s → 3.6 MB/s）
- HDF5 压缩：74% 压缩率（1 小时录制：86GB → 22GB）

**数据处理**:
- HDF5 写入延迟：< 10ms/帧（不影响实时渲染）
- HDF5 读取延迟：< 5ms/帧
- 时间轴跳转：< 100ms

**资源占用**:
- 内存使用：< 2GB（不含录制数据）
- CPU 使用：< 50%（单核）
- GPU 使用：< 30%

### 扩展性目标

**插件系统**:
- 支持动态加载插件（无需重启）
- 插件数量：≤ 20 个同时运行
- 插件启动时间：< 1s

**数据规模**:
- OBB 数量：≤ 1000 个/帧
- 点云点数：≤ 100,000 点/帧（完整），≤ 10,000 点/帧（下采样）
- 录制时长：≤ 8 小时（单个 HDF5 文件）

---

## 架构决策记录 (ADR)

### ADR 2025-12-20: 选择 ZeroMQ 作为通信框架

**背景**:
需要实现 C++ 发送端和 Python 接收端之间的实时数据传输。

**决策**:
选择 ZeroMQ (PUB/SUB 模式) 而非其他方案（如 gRPC, ROS, 原生 Socket）。

**理由**:
- ✅ **跨语言支持**: C++ 和 Python 均有成熟绑定
- ✅ **无服务器架构**: PUB/SUB 无需中心化 broker
- ✅ **低延迟**: 适合实时数据传输
- ✅ **简单易用**: API 简洁，学习曲线平缓
- ✅ **灵活的传输模式**: 支持 TCP, IPC, inproc

**权衡**:
- ❌ 无内置服务发现（需手动配置 IP:PORT）
- ❌ 无持久化支持（需自行实现）
- ✅ 对于演示和调试场景，这些缺点可接受

### ADR 2025-12-20: 使用 PyOpenGL 而非其他 3D 库

**背景**:
需要实时渲染 3D OBB 数据。

**决策**:
选择 PyOpenGL + Pygame 而非 Matplotlib 3D, VTK, Three.js 等。

**理由**:
- ✅ **性能**: 直接使用 OpenGL，渲染效率高
- ✅ **灵活性**: 完全控制渲染流程
- ✅ **轻量**: 无需重量级框架
- ✅ **与 Pygame 集成良好**: 窗口管理简单

**权衡**:
- ❌ 需要手动实现相机控制、着色器等
- ✅ 对于线框渲染的简单场景，手动实现成本可控

### ADR 2025-12-20: 支持压缩模式

**背景**:
大量 OBB 数据传输可能导致带宽瓶颈。

**决策**:
实现三种数据模式（normal, compressed, compressed_obb）。

**理由**:
- ✅ **带宽优化**: zlib 压缩可减少 60-80% 数据量
- ✅ **灵活性**: 用户可根据网络条件选择模式
- ✅ **向后兼容**: normal 模式保持与旧版本兼容

**实现**:
- `recv_obb()`: 接收原始 JSON
- `recv_compressed_data()`: 接收 zlib 压缩的 BSON（包含 OBB + 点云）
- `recv_compressed_obb()`: 仅压缩 OBB 数据

### ADR 2025-12-21: 使用 Git Submodule 管理 cppzmq 依赖

**背景**:
原本 cppzmq 通过手动下载 tar.gz 或本地编译管理，导致版本不一致、协作困难。

**决策**:
使用 Git Submodule 管理 cppzmq 依赖，而非 CMake FetchContent 或手动安装。

**理由**:
- ✅ **版本明确**: Submodule 锁定特定 commit，确保所有开发者使用相同版本
- ✅ **协作友好**: `git submodule update --init` 自动获取依赖，新团队成员开箱即用
- ✅ **无需系统安装**: 避免依赖系统包管理器，跨平台一致性好
- ✅ **构建集成简单**: `add_subdirectory(thirdparty/cppzmq)` 直接引入，无需额外配置
- ✅ **离线可用**: 克隆后即包含依赖源码，无需网络

**权衡**:
- ❌ 需要额外的 `git submodule update` 命令（已在文档中说明）
- ❌ Submodule 管理稍复杂（但比手动管理 tar.gz 更规范）
- ✅ 相比 CMake FetchContent，构建时无需网络下载

**备选方案**:
- CMake FetchContent: 更现代化，但每次 clean build 需要重新下载
- 系统安装（find_package）: 依赖系统环境，版本不可控

**实施细节**:
- Submodule URL: `https://github.com/zeromq/cppzmq.git`
- CMakeLists.txt: `add_subdirectory(thirdparty/cppzmq)`
- 初始化命令: `git submodule update --init --recursive`

### ADR 2025-12-22: Threading + Queue 架构

**背景**:
当前 recvOBB.py 在单线程中同时执行 ZMQ 数据接收和 OpenGL 渲染，导致：
- ZMQ recv() 阻塞时渲染帧率不稳定
- 无法保持稳定的 60 FPS
- 用户体验受接收数据量影响

**决策**:
采用 threading.Thread + queue.Queue 实现接收和渲染分离。

**理由**:
- ✅ **OpenGL 上下文线程绑定**: OpenGL 上下文必须在创建它的线程（主线程）中使用，所有渲染调用必须在主线程
- ✅ **I/O 适合 threading**: ZMQ recv() 是 I/O 操作，Python GIL 会释放，threading 足够
- ✅ **queue.Queue 线程安全**: 标准库提供，无需额外依赖和复杂同步
- ✅ **简单可靠**: threading 比 multiprocessing 简单，开销小

**权衡**:
- ✅ **简单性**: threading 实现简单，代码清晰
- ✅ **性能**: 足够满足 60 FPS 渲染需求
- ✅ **兼容性**: threading 和 queue 是标准库，无需额外依赖
- ❌ **扩展性**: 无法利用多核 CPU（但渲染是 GPU 密集型，不受影响）
- ❌ **GIL 限制**: threading 无法并行计算（但此场景为 I/O + 渲染，不受影响）

**备选方案**:
1. **Multiprocessing**（被拒绝）:
   - 原因：OpenGL 上下文无法在进程间共享
   - 进程间通信开销大，需要数据序列化

2. **多 OpenGL 上下文 + 上下文共享**（被拒绝）:
   - 原因：复杂度高，只适合多窗口渲染场景
   - 对单窗口实时渲染无收益

3. **异步 I/O (asyncio)**（被拒绝）:
   - 原因：Pygame 主循环是同步的，整合复杂
   - ZMQ 的 asyncio 支持不如 threading 成熟

**实施细节**:
- Queue 大小: `maxsize=10` (保留最新 10 帧数据)
- 非阻塞操作: `queue.get_nowait()` 和 `queue.put(block=False)`
- 优雅退出: `threading.Event()` + `join(timeout=2)`
- 异常处理: 接收线程捕获 ZMQ 异常和解析错误

**验证计划**:
- 渲染帧率稳定在 60 FPS
- 不同数据接收速率下的表现
- 异常情况处理（连接断开、数据错误）
- 内存使用稳定（Queue 不无限增长）

---

## LCPS 观测工具架构决策摘要 (2025-12-24)

**完整 ADR 文档**: [ADR v2.0: LCPS 观测和调试工具架构设计](../adr/2025-12-24-lcps-tool-architecture-v2.md)

**核心决策**（5 个）:

| ADR | 决策 | 核心收益 | Ultrathink 评分 |
|-----|------|---------|----------------|
| **ADR-001** | 4 层分层架构 | 职责清晰、可测试、可扩展 | 9/10 |
| **ADR-002** | HDF5 + zstd | 74% 压缩率、随机访问 | 9/10 |
| **ADR-003** | 点云下采样 | 90% 带宽优化 | 8/10 |
| **ADR-004** | Python 先行 | 快速验证、降低风险 | 9/10 |
| **ADR-005** | 插件化架构 | 70% 效率提升、40% 成本降低 | 10/10 |

**综合评分**: 9.0/10

以下是核心决策的摘要版本。完整的决策过程、量化数据、替代方案分析和实施细节请参考上述 ADR v2.0 文档。

### ADR-001: 4 层分层架构

**决策**: 采用分层架构（Layered Architecture Pattern）

**层次**:
- Layer 1: Data Acquisition（数据采集）
- Layer 2: Data Processing（数据处理和录制）
- Layer 3: Analysis & Detection（分析检测，插件化）
- Layer 4: Visualization & UI（可视化和交互）

**核心收益**:
- 职责分离，每层功能聚焦
- 风险隔离，观测工具崩溃不影响 LCPS
- 灵活扩展，可独立升级各层

**详细文档**: [ADR-001 完整决策](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-1-分层架构设计)

### ADR-002: HDF5 数据格式

**决策**: 选择 HDF5 + zstd 压缩作为数据录制格式

**关键指标**:
- 压缩率：~74%（1 小时录制：86GB → 22GB）
- 写入延迟：< 10ms/帧
- 随机访问：跳转延迟 < 100ms

**文件结构**:
```
lcps_recording.h5
├─ obb_data/        (timestamps, positions, rotations, sizes, types)
├─ pointcloud_data/ (timestamps, points, intensities)
├─ status_data/     (timestamps, state, metrics)
├─ image_data/      (timestamps, images) [可选]
└─ metadata/        (recording_date, lcps_version, etc.)
```

**详细文档**:
- [ADR-002 完整决策](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-2-hdf5-数据格式)
- [HDF5 格式规范](../design/LCPS_HDF5_FORMAT.md)

### ADR-003: 点云下采样策略

**决策**: 实时观测使用下采样点云 + 本地录制完整点云

**两模式策略**:
- **实时观测模式**: Voxel Grid 下采样（~90% 数据减少）
- **本地录制模式**: 完整点云存储到 HDF5

**关键指标**:
- 带宽优化：36 MB/s → 3.6 MB/s（90% 节省）
- 下采样算法：Voxel Grid（体素大小 0.1m）
- 非阻塞发送：zmq.NOBLOCK 确保非侵入性

**详细文档**:
- [ADR-003 完整决策](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-3-点云下采样策略)
- [数据协议规范](../design/LCPS_DATA_PROTOCOL.md)

### ADR-004: Python 先行策略

**决策**: 先实现 Python MVP，验证后迁移到 C++ QT

**时间线**:
- Phase 1-3: Python 版本（8 周）- 快速验证架构
- Phase 4: C++ QT 迁移（6 周）- 高性能生产版本

**核心收益**:
- 开发速度 ~3x C++
- 复用现有代码（减少 50% 开发量）
- 架构验证后迁移，降低风险

**详细文档**:
- [ADR-004 完整决策](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-4-python-先行策略)
- [实施计划](../design/LCPS_IMPLEMENTATION_PLAN.md)

### ADR-005: 插件化架构设计

**决策**: 采用插件化架构 + 配置文件驱动

**插件分类**（4 类）:
1. DataChannelPlugin - 扩展数据源
2. MonitorPlugin - 实时监控和可视化
3. AnalyzerPlugin - 异常检测和分析
4. ExporterPlugin - 数据导出和格式转换

**核心收益**:
- 开发效率提升 70%（新功能从 7 天 → 2 天）
- 维护成本降低 40%（插件隔离降低回归测试负担）
- 用户可自定义扩展（不修改核心代码）

**内置插件**（8 个）:
- OBBChannel, PointCloudChannel, StatusChannel, ImageChannel
- LiveMonitor, LifecycleMonitor
- MissedAlertDetector, FalseAlarmDetector
- HDF5Recorder, MLDatasetExporter

**详细文档**:
- [ADR-005 完整决策](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计)
- [插件架构指南](../design/LCPS_PLUGIN_ARCHITECTURE.md)

---

## 功能路线图

### 已完成功能 ✅

- [x] ZMQ PUB/SUB 通信
- [x] OBB 数据结构定义
- [x] OpenGL 线框渲染
- [x] JSON 序列化/反序列化
- [x] 数据压缩支持（zlib + BSON）
- [x] 点云数据支持
- [x] 命令行参数解析（debug, mode, address）
- [x] Linux/Windows 二进制打包

### 正在开发功能 🔄

无（上一个功能已完成）

### 计划功能 📋

#### OBBViewer 基础功能
- [ ] 配置文件支持（YAML/JSON）
- [ ] 多相机视角切换
- [ ] OBB 碰撞检测可视化
- [ ] 性能统计和 FPS 显示（部分完成）

#### LCPS 观测和调试工具（2025-12-24 新增）

**Phase 1: MVP（2周）** - **优先级：高**
- [ ] PointCloudReceiver 实现（下采样点云接收）
- [ ] StatusReceiver 实现（LCPS 状态接收）
- [ ] 点云渲染（使用 VBO 优化）
- [ ] HDF5 数据录制（基础版本）
- [ ] 时间戳同步机制
- [ ] 端到端功能验证

**Phase 2: 调试功能（3周）** - **优先级：中**
- [ ] 数据回放功能（播放 HDF5 录制数据）
- [ ] 时间轴控制（暂停、播放、快进、慢放）
- [ ] 帧对比工具（并排对比两个时间点）
- [ ] 统计面板（点云密度、OBB 数量、帧率、带宽）
- [ ] 异常检测规则（可配置的漏报/误报检测）
- [ ] 数据导出功能（导出特定帧为 JSON/PLY）

**Phase 3: 高级功能（3周）** - **优先级：低**
- [ ] 图像数据接收和显示（如果 LCPS 提供）
- [ ] 多视图布局（3D 视图 + 2D 图像 + 状态面板）
- [ ] 配置系统（保存/加载观测配置）
- [ ] 自动化分析报告（生成问题分析 Markdown 文档）
- [ ] 性能优化（LOD、视锥体剔除）
- [ ] 用户手册和文档

**Phase 4: C++ QT 生产版本（6周）** - **优先级：待定**
- [ ] 架构迁移：Python → C++
- [ ] UI 迁移：ImGui → Qt Widgets
- [ ] 集成 mmtoolkit2
- [ ] 性能优化（更高帧率、更低延迟）
- [ ] 完整的单元测试和集成测试
- [ ] 打包和部署方案

---

## 部署和发布

### 支持平台

| 平台 | 状态 | 说明 |
|------|------|------|
| **Linux** | ✅ 完全支持 | Ubuntu 18.04+ 测试通过 |
| **Windows** | ✅ 完全支持 | Windows 10+ 测试通过 |
| **macOS** | ⚠️ 未测试 | 理论支持，需验证 |

### 打包方式

**Python 接收端**:
- 使用 PyInstaller 打包（LCPSViewer.spec）
- 输出目录: `dist/`
- 打包命令: `pyinstaller LCPSViewer.spec`

**C++ 发送端**:
- 使用 CMake 构建
- 输出目录: `build/`
- 构建命令:
  ```bash
  mkdir build && cd build
  cmake ..
  make
  ```

---

## 维护和支持

### 版本控制

**Git 分支策略**:
- **master**: 稳定版本
- **develop**: 开发版本（如需要）
- **feature/***:  功能分支（如需要）

**提交规范**:
```
[type] subject

详细说明（可选）
```

**类型标签**:
- `[feat]` - 新功能
- `[fix]` - Bug 修复
- `[perf]` - 性能优化
- `[chore]` - 构建/配置更新
- `[docs]` - 文档更新

---

## 性能考量

### 数据压缩效果

**测试场景**: 100 个 OBB 对象

| 模式 | 数据大小 | 压缩率 | CPU 开销 |
|------|---------|--------|---------|
| Normal (JSON) | ~10 KB | - | 低 |
| Compressed (BSON+zlib) | ~2-4 KB | 60-80% | 中等 |
| Compressed OBB | ~2 KB | 80% | 低 |

**建议**:
- 本地网络（localhost）: 使用 normal 模式
- 局域网（LAN）: 使用 compressed 模式
- 低带宽网络: 使用 compressed_obb 模式

### 渲染性能

**目标帧率**: 60 FPS（多线程架构优化后）
**当前瓶颈**:
- ~~单线程模式下 ZMQ 接收阻塞渲染~~ → 已解决（多线程架构）
- OpenGL 绘制（`glBegin`/`glEnd` 立即模式）

**多线程架构性能提升**:
- 渲染帧率：30-40 FPS → **稳定 60 FPS**
- 最大延迟：~100ms → **~167ms（10 帧 @ 60 FPS）**
- CPU 使用：单核 80% → **单核 85%（多一个 I/O 线程）**
- 内存使用：稳定（Queue maxsize=10 限制）

**进一步优化方向**:
- 使用 VBO (Vertex Buffer Object) 替代立即模式
- 批量绘制（减少 draw call）
- 视锥剔除（不渲染视野外 OBB）
- Shader 加速（顶点着色器）

---

## 安全指南

### 安全性考量

**LCPS 作为安全关键系统的要求**:
- ✅ **非侵入性设计**: 观测工具崩溃不影响 LCPS 主功能（zmq.NOBLOCK）
- ✅ **故障隔离**: Layer 1-4 独立，单层失败不传播
- ✅ **插件隔离**: 插件故障不影响核心系统
- ⚠️ **性能保证**: 录制/分析不影响实时观测（< 100ms 延迟）

### 数据安全

**当前状态**:
- ❌ 无认证机制
- ❌ 无加密传输
- ❌ 无访问控制

**适用场景**:
- ✅ 本地调试（localhost）
- ✅ 可信网络环境（内网）
- ❌ 公网部署（不推荐）

**改进方向**:
- 添加 ZMQ CurveZMQ 加密（公钥/私钥认证）
- 实现简单的 token 认证
- 限制绑定地址（不使用 `*`，明确指定 IP）
- HDF5 文件加密（可选，使用 AES）

### 代码安全

**插件安全**:
- 插件代码审查（用户自定义插件需审查）
- 沙箱执行（未来 C++ 版本考虑）
- 资源限制（内存、CPU 使用限制）

**依赖安全**:
- 定期更新依赖库版本
- 使用 `uv` 或 `pip-audit` 检查漏洞
- 固定依赖版本（pyproject.toml）

---

## 参考资料

### 官方文档

**通信和数据**:
- [ZeroMQ Guide](https://zguide.zeromq.org/) - ZMQ 完整指南
- [HDF5 User Guide](https://docs.hdfgroup.org/) - HDF5 官方文档
- [zstd Documentation](https://facebook.github.io/zstd/) - zstd 压缩库

**渲染和 UI**:
- [PyOpenGL Documentation](http://pyopengl.sourceforge.net/) - OpenGL Python 绑定
- [Pygame Documentation](https://www.pygame.org/docs/) - 游戏开发库
- [Dear ImGui](https://github.com/ocornut/imgui) - 即时模式 GUI

**点云处理**:
- [Open3D Documentation](http://www.open3d.org/docs/) - 点云处理库
- [PCL (Point Cloud Library)](https://pointclouds.org/) - C++ 点云库

### 相关项目

**OBBDemo 依赖**:
- [cppzmq](https://github.com/zeromq/cppzmq) - ZeroMQ C++ 头文件封装
- [nlohmann/json](https://github.com/nlohmann/json) - Modern JSON for C++
- [pyimgui](https://github.com/pyimgui/pyimgui) - ImGui Python 绑定

**LCPS 工具参考**:
- [ROS Bag](http://wiki.ros.org/rosbag) - ROS 数据录制工具（对比参考）
- [PlotJuggler](https://github.com/facontidavide/PlotJuggler) - 时序数据可视化
- [CloudCompare](https://www.cloudcompare.org/) - 点云查看和处理

### 设计模式和架构

- [Layered Architecture Pattern](https://martinfowler.com/bliki/PresentationDomainDataLayering.html) - Martin Fowler
- [Plugin Architecture Pattern](https://www.enterpriseintegrationpatterns.com/) - 企业集成模式
- [Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html) - 事件驱动架构

---

## 相关文档索引

### 管理文档（docs/management/）

- **PLANNING.md**（本文档）- 项目架构和开发标准
- [TASK.md](TASK.md) - 任务追踪和功能路线图
- [CONTEXT.md](CONTEXT.md) - 会话上下文和工作进度
- [KNOWLEDGE.md](../../KNOWLEDGE.md) - 知识库和文档索引

### 架构决策记录（docs/adr/）

- [ADR v2.0: LCPS 观测和调试工具架构设计](../adr/2025-12-24-lcps-tool-architecture-v2.md) - 5 个核心架构决策

### 设计文档（docs/design/）

**LCPS 观测工具设计**:
- [LCPS 综合设计方案](../design/LCPS_COMPREHENSIVE_DESIGN.md) - 完整设计方案
- [LCPS 插件架构指南](../design/LCPS_PLUGIN_ARCHITECTURE.md) - 插件开发 SDK
- [LCPS 异常检测规范](../design/LCPS_ANOMALY_DETECTION.md) - 漏报/误报检测规则
- [LCPS HDF5 格式规范](../design/LCPS_HDF5_FORMAT.md) - 数据存储格式
- [LCPS 数据协议规范](../design/LCPS_DATA_PROTOCOL.md) - ZMQ 通信协议
- [LCPS 实施计划](../design/LCPS_IMPLEMENTATION_PLAN.md) - Phase 1-4 实施细节

### 技术文档（docs/）

- [系统架构](../architecture/system-design.md) - OBBDemo 整体架构
- [数据格式](../api/data-format.md) - OBB 数据结构
- [开发指南](../development/setup.md) - 环境配置和构建
- [用户手册](../usage/quick-start.md) - 安装和使用
- [部署指南](../deployment/binary-release.md) - PyInstaller 打包

---

## 文档维护

**此文档应在以下情况更新**:
- 添加新的技术栈或依赖
- 做出重大架构决策（新增 ADR）
- 更新功能路线图
- 修改开发规范
- 性能目标调整
- 安全策略变更

**更新频率**:
- 每次重大功能完成后
- 每个 Phase 结束后
- 重要架构决策后（同步更新 ADR）

**文档所有者**: 架构团队

**最后更新**: 2025-12-24（LCPS 观测工具架构设计集成）
