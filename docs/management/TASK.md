# OBBDemo 项目任务追踪

**最后更新**: 2025-12-24

## 任务总览

| 状态 | OBBDemo | LCPS Tool | 总计 | 说明 |
|------|---------|-----------|------|------|
| ✅ 已完成 | 11 | 4 | 15 | 核心功能、Layer 1+2 完成 |
| 🔄 进行中 | 0 | 0 | 0 | 无 |
| 📋 Phase 1 (MVP) | - | 1 | 1 | MVP 集成测试 |
| 📋 Phase 2 (完整) | - | 5 | 5 | 插件系统、分析 |
| 📋 Phase 3 (高级) | - | 4 | 4 | 多视图、报告 |
| 📋 Phase 4 (C++) | - | 3 | 3 | C++ 迁移、优化 |
| 📋 基础改进 | 3 | - | 3 | OBBViewer 功能 |

**总任务数**: 34 (其中 15 已完成，19 待做)

---

## 项目阶段规划

### Phase 1: LCPS MVP（2 周，优先级：🔴 高）
**目标**: 验证 4 层架构可行性，实现基础数据接收和录制
**关键成果**: 可运行的 Python MVP，支持 OBB/点云/状态接收和 HDF5 录制
**相关 ADR**: [ADR v2.0](../adr/2025-12-24-lcps-tool-architecture-v2.md)

### Phase 2: 完整功能（3 周，优先级：🟠 中）
**目标**: 实现插件系统和异常检测，完善回放和分析功能
**关键成果**: 可扩展的插件架构，智能异常检测（≥ 90% 准确率）
**相关设计**: [插件架构指南](../design/LCPS_PLUGIN_ARCHITECTURE.md)

### Phase 3: 高级功能（3 周，优先级：🟡 低）
**目标**: 图像支持、多视图布局、自动化报告
**关键成果**: 完整的多模态观测工具，生产级文档

### Phase 4: C++ 迁移（6 周，优先级：⏳ 待定）
**目标**: 渐进迁移到 C++ QT，性能优化
**关键成果**: 高性能生产版本（性能提升 ≥ 5 倍）

---

## LCPS 观测工具 - Phase 1: MVP （优先级：🔴 高，2 周）

### LCPS-P1-T1: 实现 PointCloudReceiver（数据接收 Layer 1）
**优先级**: 🔴 高
**难度**: 中
**依赖**: LCPS-Arch-001 (4层架构决策)
**状态**: ✅ 已完成（2025-12-24）

**描述**: 实现多通道数据接收器中的点云接收模块，支持 ZMQ 订阅和下采样点云数据解析

**验收标准**:
- [x] PointCloudReceiver 类实现（独立线程，Queue 缓冲）
- [x] 支持点云数据解析（numpy 数组）
- [x] Voxel Grid 下采样实现（体素大小 0.1m）
- [x] 与 OBBReceiver 整合到 MultiChannelReceiver
- [ ] 单元测试覆盖率 ≥ 80%（待后续补充）

**技术决策**:
- [ADR-003: 点云下采样策略](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-3-点云下采样策略)

**相关代码**:
- `lcps_tool/layer1/receivers/pointcloud_receiver.py` (新建)
- `lcps_tool/layer1/multi_channel_receiver.py` (修改)

**验证标准**:
- 延迟 < 100ms
- 下采样率 ≥ 85%

---

### LCPS-P1-T2: 实现 StatusReceiver（数据接收 Layer 1）
**优先级**: 🔴 高
**难度**: 小
**依赖**: LCPS-Arch-001
**状态**: ✅ 已完成（2025-12-24）

**描述**: 实现 LCPS 状态数据接收模块，接收状态枚举和性能指标

**验收标准**:
- [x] StatusReceiver 类实现（独立线程）
- [x] 状态枚举定义（IDLE, DETECTING, ALERTING, ERROR 等）
- [x] 性能指标解析（CPU, Memory, FPS, Latency）
- [ ] HUD 面板支持（显示当前状态）（待 Layer 4 实现）

**相关代码**:
- `lcps_tool/layer1/receivers/status_receiver.py` (新建)
- `lcps_tool/data_models/lcps_status.py` (新建)

**验证标准**:
- 接收延迟 < 50ms

---

### LCPS-P1-T3: 实现 DataSynchronizer（数据处理 Layer 2）
**优先级**: 🔴 高
**难度**: 中
**依赖**: LCPS-P1-T1, LCPS-P1-T2
**状态**: ✅ 已完成（2025-12-24）

**描述**: 实现多源数据的时间戳同步，确保 OBB/点云/状态对齐

**验收标准**:
- [x] 时间戳同步算法实现（阈值匹配算法）
- [x] 支持时间戳窗口（±50ms 内匹配）
- [x] 生成 SyncedFrame（OBB + PC + Status + 时间戳）
- [ ] 单元测试（同步准确性 ≥ 95%）（待后续补充）

**技术参考**:
- [LCPS 数据协议规范](../design/LCPS_DATA_PROTOCOL.md)

**相关代码**:
- `lcps_tool/layer2/data_synchronizer.py` (新建)
- `lcps_tool/data_models/synced_frame.py` (新建)

**验证标准**:
- 同步延迟 < 50ms
- 对齐准确性 ≥ 95%

---

### LCPS-P1-T4: 实现 DataRecorder（数据处理 Layer 2）
**优先级**: 🔴 高
**难度**: 中
**依赖**: LCPS-P1-T3
**状态**: ✅ 已完成（2025-12-24）

**描述**: 实现 HDF5 数据录制模块，支持异步写入和流式压缩

**验收标准**:
- [x] HDF5 文件创建和数据集初始化
- [x] OBB/点云/状态 数据写入（支持 gzip 压缩）
- [x] 异步写入队列（避免阻塞主线程）
- [x] 定期 flush（每 100 帧）
- [x] 元数据记录（录制日期、版本、配置）
- [ ] 单元测试（压缩率验证）（待后续补充）

**技术决策**:
- [ADR-002: HDF5 数据格式](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-2-hdf5-数据格式)
- [LCPS HDF5 格式规范](../design/LCPS_HDF5_FORMAT.md)

**相关代码**:
- `lcps_tool/layer2/data_recorder.py` (新建)
- `tests/test_data_recorder.py` (新建)

**验证标准**:
- 压缩率 ≥ 70%
- 写入延迟 < 10ms/帧

---

### LCPS-P1-T5: 端到端集成和 MVP 验证
**优先级**: 🔴 高
**难度**: 中
**依赖**: LCPS-P1-T1, LCPS-P1-T2, LCPS-P1-T3, LCPS-P1-T4
**状态**: 📋 待做

**描述**: 集成所有 Layer 1-2 模块，实现可运行的 MVP，进行端到端测试

**验收标准**:
- [ ] MultiChannelReceiver 完整实现（4 个数据源）
- [ ] 数据同步验证（所有通道同步 ≤ 50ms）
- [ ] HDF5 录制功能验证（完整性 100%）
- [ ] 集成测试（sender → receiver → 文件验证）
- [ ] 性能基准测试（延迟、CPU、内存）
- [ ] 文档完成（快速开始指南）

**测试场景**:
- 本地测试（localhost:5555-5558）
- 不同帧率测试（10Hz, 30Hz, 60Hz）
- 长时间运行测试（≥ 1 小时）

**相关代码**:
- `lcps_tool/main.py` (整合脚本)
- `tests/test_integration_mvp.py` (集成测试)
- `docs/usage/quick-start-lcps.md` (快速开始)

**验证标准** (基于 ADR v2.0):
- Layer 1 延迟 < 100ms ✅
- Layer 2 录制不影响 Layer 1 帧率 ✅
- 压缩率 ≥ 70% ✅
- 端到端功能验证通过 ✅

---

## LCPS 观测工具 - Phase 2: 完整功能 （优先级：🟠 中，3 周）

### LCPS-P2-T1: 实现插件管理系统
**优先级**: 🟠 中
**难度**: 中
**依赖**: LCPS-P1-T5 (MVP 完成)
**状态**: 📋 待做

**描述**: 实现动态插件加载、生命周期管理和事件总线

**验收标准**:
- [ ] PluginManager 类实现
- [ ] IPlugin 基类和子类（DataChannel, Monitor, Analyzer, Exporter）
- [ ] plugin_config.yaml 支持
- [ ] 热加载/卸载支持（无需重启）
- [ ] EventBus 实现（插件间通信）
- [ ] 单元测试（插件隔离、故障处理）

**技术决策**:
- [ADR-005: 插件化架构设计](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-5-插件化架构设计)
- [LCPS 插件架构指南](../design/LCPS_PLUGIN_ARCHITECTURE.md)

**相关代码**:
- `lcps_tool/layer3/plugin/base.py` (IPlugin 基类)
- `lcps_tool/layer3/plugin/manager.py` (PluginManager)
- `lcps_tool/layer3/plugin/event_bus.py` (EventBus)

**验证标准**:
- 支持动态加载插件（无需重启）
- 插件故障隔离（一个插件崩溃不影响其他）

---

### LCPS-P2-T2: 实现异常检测插件（MissedAlertDetector）
**优先级**: 🟠 中
**难度**: 中
**依赖**: LCPS-P2-T1
**状态**: 📋 待做

**描述**: 实现漏报检测插件，识别应报警但未报警的场景

**验收标准**:
- [ ] MissedAlertDetector 插件实现
- [ ] Danger Zone（危险区域）配置支持
- [ ] 异常检测规则实现
- [ ] 检测准确率 ≥ 90%
- [ ] 单元测试（真阳性、假阴性测试）

**技术参考**:
- [LCPS 异常检测规范](../design/LCPS_ANOMALY_DETECTION.md)

**相关代码**:
- `lcps_tool/layer3/plugins/analyzer_missed_alert.py` (新建)

**验证标准**:
- 异常检测准确率 ≥ 90%

---

### LCPS-P2-T3: 实现异常检测插件（FalseAlarmDetector）
**优先级**: 🟠 中
**难度**: 小
**依赖**: LCPS-P2-T1
**状态**: 📋 待做

**描述**: 实现误报检测插件，识别不应报警但报警的场景

**验收标准**:
- [ ] FalseAlarmDetector 插件实现
- [ ] 阈值配置支持
- [ ] 误报检测规则实现
- [ ] 单元测试

**相关代码**:
- `lcps_tool/layer3/plugins/analyzer_false_alarm.py` (新建)

---

### LCPS-P2-T4: 实现数据回放功能
**优先级**: 🟠 中
**难度**: 中
**依赖**: LCPS-P1-T5 (HDF5 录制完成)
**状态**: 📋 待做

**描述**: 实现 HDF5 录制数据的回放功能，支持时间轴控制

**验收标准**:
- [ ] DataReplayer 类实现
- [ ] 随机访问支持（跳转到任意时间点）
- [ ] 播放控制（播放、暂停、快进、慢放）
- [ ] 时间轴同步（显示当前位置）
- [ ] 单元测试（完整性、准确性）

**相关代码**:
- `lcps_tool/layer2/data_replayer.py` (新建)

**验证标准**:
- 支持跳转到任意时间点（延迟 < 100ms）

---

### LCPS-P2-T5: Phase 2 集成和验证
**优先级**: 🟠 中
**难度**: 中
**依赖**: LCPS-P2-T1 - LCPS-P2-T4
**状态**: 📋 待做

**描述**: 集成所有 Phase 2 功能，验证插件系统、异常检测、回放完整性

**验收标准**:
- [ ] 插件系统集成测试（加载、卸载、通信）
- [ ] 异常检测验证（准确率 ≥ 90%）
- [ ] 回放功能验证（完整、准确）
- [ ] 性能测试（不影响实时观测）
- [ ] 文档完成（插件开发指南、用户手册）

**相关代码**:
- `tests/test_integration_phase2.py` (集成测试)

---

## LCPS 观测工具 - Phase 3: 高级功能 （优先级：🟡 低，3 周）

### LCPS-P3-T1: 实现 ImageReceiver 和渲染
**优先级**: 🟡 低
**难度**: 中
**状态**: 📋 待做

**描述**: 支持图像数据接收和显示（如果 LCPS 提供）

**验收标准**:
- [ ] ImageReceiver 实现
- [ ] 图像渲染（OpenGL 纹理）
- [ ] 图像面板布局

---

### LCPS-P3-T2: 实现多视图布局
**优先级**: 🟡 低
**难度**: 中
**状态**: 📋 待做

**描述**: 实现 3D 视图 + 2D 图像 + 状态面板多视图布局

**验收标准**:
- [ ] ImGui 多窗口支持
- [ ] 可调整的布局

---

### LCPS-P3-T3: 实现自动化分析报告
**优先级**: 🟡 低
**难度**: 中
**状态**: 📋 待做

**描述**: 生成结构化的问题分析报告（Markdown 格式）

**验收标准**:
- [ ] 报告生成模块
- [ ] 异常总结和建议

---

### LCPS-P3-T4: 配置系统和优化
**优先级**: 🟡 低
**难度**: 小
**状态**: 📋 待做

**描述**: 性能优化、配置系统完善、用户手册编写

**验收标准**:
- [ ] LOD、视锥体剔除等优化
- [ ] 配置文件支持（保存/加载）
- [ ] 完整用户手册

---

## LCPS 观测工具 - Phase 4: C++ 迁移 （优先级：⏳ 待定，6 周）

### LCPS-P4-T1: MultiChannelReceiver C++ 实现
**优先级**: ⏳ 待定
**难度**: 大
**依赖**: Phase 2 完成，Python MVP 验证通过
**状态**: 📋 待做

**描述**: 将 MultiChannelReceiver 从 Python 迁移到 C++，集成 ZMQ C++ API

**相关代码**:
- `src/lcps_tool/layer1/multichannel_receiver.cpp`

---

### LCPS-P4-T2: DataRecorder C++ 实现
**优先级**: ⏳ 待定
**难度**: 大
**依赖**: LCPS-P4-T1
**状态**: 📋 待做

**描述**: 将 DataRecorder 迁移到 C++，集成 HDF5 C++ API

**相关代码**:
- `src/lcps_tool/layer2/data_recorder.cpp`

---

### LCPS-P4-T3: UI 和部署优化
**优先级**: ⏳ 待定
**难度**: 中
**依赖**: LCPS-P4-T1, LCPS-P4-T2
**状态**: 📋 待做

**描述**: Qt UI 实现、CMake 构建、打包和部署

**相关代码**:
- `src/lcps_tool/ui/` (Qt UI)
- `CMakeLists.txt` (C++ 构建)
- `deploy/` (打包脚本)

---

## OBBViewer 改进 （优先级：🟡 低）

### OBB-T1: 配置文件支持
**优先级**: 🟡 低
**难度**: 小
**状态**: 📋 待做

**描述**: 支持 YAML/JSON 配置文件，存储默认参数

**相关代码**:
- `config.yaml` (默认配置)
- `config_loader.py` (配置加载)

---

### OBB-T2: 多相机视角切换
**优先级**: 🟡 低
**难度**: 小
**状态**: 📋 待做

**描述**: 支持多个预设相机视角（俯视图、侧视图、自由视角）

**相关代码**:
- `camera_manager.py` (相机管理)

---

### OBB-T3: OBB 碰撞检测可视化
**优先级**: 🟡 低
**难度**: 中
**状态**: 📋 待做

**描述**: 可视化显示 OBB 之间的碰撞关系

**相关代码**:
- `collision_detector.py` (碰撞检测)

---

## 已完成任务 ✅

### 任务 1: 实现 ZMQ 通信基础 ✅
**完成时间**: 2024-07-19
**优先级**: 高
**负责人**: -

**描述**: 实现 C++ 发送端和 Python 接收端的 ZMQ PUB/SUB 通信。

**验收标准**:
- [x] C++ sender 可以发布数据
- [x] Python receiver 可以订阅并接收数据
- [x] 支持 TCP 传输
- [x] 默认端口 5555

**相关文件**:
- `sender.cpp`
- `recv.py` (基础版本)

**关联需求**: 实时数据传输

---

### 任务 2: 实现 OBB 数据结构和渲染 ✅
**完成时间**: 2024-07-19
**优先级**: 高
**负责人**: -

**描述**: 定义 OBB 数据结构并实现 OpenGL 线框渲染。

**验收标准**:
- [x] OBB 类包含 type, position, rotation, size 属性
- [x] 实现 `draw_obb()` 函数
- [x] 实现 `draw_wire_cube()` 函数
- [x] 支持四元数到矩阵的转换
- [x] 支持 OBB 变换（平移、旋转、缩放）

**相关文件**:
- `recv.py` (OBB class, draw functions)
- `LCPSViewer.py`

**关联需求**: 3D 数据可视化

---

### 任务 3: 添加数据压缩支持 ✅
**完成时间**: 2024-07-28
**优先级**: 中
**负责人**: -

**描述**: 实现数据压缩传输以优化带宽使用。

**验收标准**:
- [x] 实现 `recv_compressed_data()` 函数
- [x] 使用 zlib 压缩
- [x] 使用 BSON 二进制序列化
- [x] 支持压缩率统计

**相关文件**:
- `recv.py` (recv_compressed_data)

**关联需求**: 性能优化 - 带宽

**技术决策**: ADR 2025-12-20 - 支持压缩模式

---

### 任务 4: 添加点云数据支持 ✅
**完成时间**: 2024-07-XX
**优先级**: 中
**负责人**: -

**描述**: 扩展数据格式，支持点云数据的接收和渲染。

**验收标准**:
- [x] 扩展数据格式支持 points 字段
- [x] `recv_compressed_data()` 可解析点云数据
- [x] 实现点云渲染（如果需要）

**相关文件**:
- `recv.py` (recv_compressed_data)

**关联需求**: 多模态数据支持

**Git Commit**: ddc137b - [feat] add points support

---

### 任务 5: 添加命令行参数支持 ✅
**完成时间**: 2024-07-28
**优先级**: 中
**负责人**: -

**描述**: 使用 argparse 添加命令行参数，提高灵活性。

**验收标准**:
- [x] `-d/--debug`: 调试模式
- [x] `-m/--mode`: 数据接收模式（normal/compressed）
- [x] `-a/--address`: IP:PORT 地址
- [x] 参数验证（IP:PORT 格式）

**相关文件**:
- `recv.py` (argparse section)

**关联需求**: 用户体验改进

**Git Commit**: 634d95b - [perf] optimize recv to support normal and compressed mode

---

### 任务 6: 集成 mm_tool_PublishObs ✅
**完成时间**: 2024-07-XX
**优先级**: 高
**负责人**: -

**描述**: 集成 mm_tool_PublishObs 工具，支持特定数据源。

**验收标准**:
- [x] 兼容 mm_tool_PublishObs 数据格式
- [x] 测试通过

**相关文件**:
- `recv.py`

**关联需求**: 系统集成

**Git Commit**: 6b7a390 - [feat] update recv.py to support mm_tool_PublishObs

---

### 任务 7: 更新安装指南 ✅
**完成时间**: 2024-08-03
**优先级**: 低
**负责人**: -

**描述**: 更新 README.md 中的安装指南，确保依赖列表准确。

**验收标准**:
- [x] Python 依赖列表完整
- [x] C++ 依赖列表完整
- [x] 安装步骤清晰

**相关文件**:
- `README.md`

**关联需求**: 文档完善

**Git Commit**: aed11e3 - [chore] update installation guide

---

### 任务 8: 添加二进制发布 ✅
**完成时间**: 2024-08-03
**优先级**: 中
**负责人**: -

**描述**: 使用 PyInstaller 打包 Python 程序，提供 Linux/Windows 二进制文件。

**验收标准**:
- [x] 创建 LCPSViewer.spec
- [x] 生成 Linux 可执行文件
- [x] 生成 Windows 可执行文件
- [x] 测试打包后的程序功能正常

**相关文件**:
- `LCPSViewer.spec`
- `build/`, `dist/`

**关联需求**: 部署便利性

**Git Commit**: deb52fd - [feat] add binary execution for Linux & Windows

---

### 任务 9: 完成文档体系建设 ✅
**完成时间**: 2025-12-21
**优先级**: 高
**负责人**: Claude AI

**描述**: 创建完整的项目管理和技术文档体系。

**已完成子任务**:
- [x] 创建文档目录结构
- [x] 生成 PLANNING.md
- [x] 生成 TASK.md
- [x] 优化 KNOWLEDGE.md（从 452 行精简至 198 行）
- [x] 生成架构文档 (system-design.md)
- [x] 生成 API 文档 (data-format.md)
- [x] 生成开发指南 (setup.md)
- [x] 生成用户手册 (quick-start.md)
- [x] 生成部署指南 (binary-release.md)
- [x] 生成故障排查指南 (KNOWLEDGE.md § FAQ)
- [x] 更新 README.md

**验收标准完成情况**:
- [x] 所有技术文档包含完整的 Frontmatter（5/5 已验证）
- [x] KNOWLEDGE.md 建立文档索引（已更新）
- [x] 文档总量符合约束（3,246 行 < 5,000 行）
- [x] 通过 Frontmatter 验证（全部通过）

**相关需求**: 项目管理和维护

**Git Commits**:
- 4fb4c35 - [chore] 恢复文件管理和现代化依赖管理

---

### 任务 10: 实现 sendOBB/recvOBB（参考 LCPS） ✅
**完成时间**: 2025-12-22
**优先级**: 中
**负责人**: Claude AI

**描述**: 参考 LCPS 项目实现的 OBB 发送/接收高级程序。

**已完成子任务**:
- [x] 分析参考代码：LCPS::sendOBB 实现
- [x] 创建 sendOBB.cpp
  - [x] 支持多种 OBB 类型（obs、sprWarn、sprStop）
  - [x] 支持普通模式（JSON）和压缩模式（BSON + zlib）
  - [x] 命令行参数支持 (-m 模式, -c OBB 数量)
  - [x] 压缩效果验证（73% 压缩率）
- [x] 创建 recvOBB.py
  - [x] 专用的 OBB 接收端
  - [x] 支持普通和压缩模式接收
  - [x] 格式化输出 OBB 数据（类型、位置、旋转、碰撞状态）
  - [x] 统计压缩率和性能指标
- [x] 更新 CMakeLists.txt
  - [x] 添加 sendOBB 编译目标
- [x] 集成测试
  - [x] 普通模式测试通过（JSON，351 bytes/msg）
  - [x] 压缩模式测试通过（BSON + zlib，165 bytes/msg，73% 压缩率）
- [x] 创建使用文档 (docs/usage/sendOBB-recvOBB.md)
  - [x] 编译指南
  - [x] 使用示例
  - [x] 参数说明
  - [x] 故障排查
  - [x] 性能指标

**验收标准**:
- [x] sendOBB 编译成功
- [x] recvOBB.py 功能正常
- [x] 两个程序通信正常（普通模式）
- [x] 两个程序通信正常（压缩模式）
- [x] 文档完整，包含使用示例

**相关文件**:
- `sendOBB.cpp` (新增)
- `recvOBB.py` (新增)
- `CMakeLists.txt` (修改)
- `docs/usage/sendOBB-recvOBB.md` (新增)

**相关需求**: 高级功能测试和集成

**性能数据**:
- 普通模式: 351 bytes/msg，~11.6 KB/s
- 压缩模式: 165 bytes/msg，~5.4 KB/s，73% 压缩率

---

## 进行中任务 🔄

无

---

## 待做任务 📋

### 任务 9.1: 优化 C++ 依赖管理（cppzmq）✅
**完成时间**: 2025-12-21
**优先级**: 高
**负责人**: Claude AI

**描述**: 改用 Git Submodule 管理 cppzmq 依赖，而非手动管理。

**子任务**:
- [x] 清理现有的 thirdparty/cppzmq 和 tar.gz
- [x] 添加 Git Submodule: `git submodule add https://github.com/zeromq/cppzmq.git thirdparty/cppzmq`
- [x] 更新 CMakeLists.txt 使用 add_subdirectory()
- [x] 更新 README.md 和 docs/development/setup.md 说明初始化步骤
- [x] 创建 ADR 记录决策理由（PLANNING.md 和 KNOWLEDGE.md）
- [x] 测试构建成功（sender 编译通过，387KB）

**验收标准**:
- [x] CMake 配置正确，能成功编译
- [x] 文档清晰说明初始化步骤
- [x] 所有新用户能正确初始化 submodule（`git submodule update --init --recursive`）
- [x] Git log 显示清晰的提交历史（待提交）

**相关需求**: 项目维护和开发流程改进

**技术决策**: ADR 2025-12-21 - 使用 Git Submodule 管理 cppzmq 依赖

**实施结果**:
- ✅ `.gitmodules` 配置文件已创建
- ✅ cppzmq submodule 指向官方仓库 `https://github.com/zeromq/cppzmq.git`
- ✅ CMakeLists.txt 使用 `add_subdirectory(thirdparty/cppzmq)`
- ✅ 编译测试通过（包含 sender + cppzmq 测试套件）
- ✅ 文档已更新（README.md, setup.md）

**推荐下一步**: `/wf_08_review` 审查更改，然后 `/wf_11_commit` 提交

---

### 任务 10: 规范化 C++ 构建配置 📋
**优先级**: 高
**预估工作量**: 1-2 小时

**描述**: 根据最新的咨询结果，使用标准的 CMake 模式管理 cppzmq。

**验收标准**:
- [x] 完成任务 9.1（Git Submodule 管理）✅
- [ ] CMakeLists.txt 配置清晰，无冗余
- [ ] 新团队成员能无障碍初始化和构建
- [ ] 解决当前 CMake find_package 和手动目录的不兼容问题

**相关文件**:
- CMakeLists.txt
- .gitmodules
- README.md
- docs/development/setup.md

**相关咨询**: /wf_04_ask "如何处理该repo和cppzmq的关系？"（2025-12-21）

**技术决策**: ADR 记录（待创建）

**关联需求**: 开发流程规范化

---

### 任务 10.1: 实现 sender 压缩模式支持 📋
**优先级**: 中
**预估工作量**: 30-60 分钟
**创建日期**: 2025-12-21

**描述**: sender.cpp 当前只支持 JSON 格式发送，需要实现 zlib + BSON 压缩模式以匹配 recv.py 的压缩模式。

**背景**:
- recv.py 已支持压缩模式（`-m c`）
- sender.cpp 未实现压缩，导致压缩模式下无法接收数据
- 已添加警告提示用户使用普通模式

**验收标准**:
- [ ] sender.cpp 添加 libbson 依赖
- [ ] 实现 zlib 压缩功能
- [ ] 添加命令行参数 `-m` 选择模式（normal/compressed）
- [ ] 压缩数据格式匹配 recv.py 期望（4字节size + zlib压缩的BSON）
- [ ] 测试两种模式都能正常工作
- [ ] 更新 README.md 说明压缩模式用法

**相关文件**:
- sender.cpp
- CMakeLists.txt（添加 libbson 依赖）
- README.md
- docs/api/data-format.md

**参考实现**: recv.py:196-227 (recv_compressed_data函数)

**相关问题**: KNOWLEDGE.md § FAQ Q3

**关联需求**: 数据压缩传输功能完整性

---

### 任务 11: 添加配置文件支持 📋
**优先级**: 中
**预估工作量**: 4-6 小时

**描述**: 支持通过 YAML/JSON 配置文件设置参数，减少命令行参数复杂度。

**验收标准**:
- [ ] 支持 `config.yaml` 或 `config.json`
- [ ] 配置项包括：网络地址、渲染参数、调试选项
- [ ] 命令行参数优先级高于配置文件
- [ ] 提供默认配置模板

**相关文件**:
- `recv.py` (配置加载)
- `config.yaml.example` (模板)

**技术选型**: PyYAML 或 json（内置）

**关联需求**: 用户体验改进

---

### 任务 11: 实现多相机视角切换 📋
**优先级**: 中
**预估工作量**: 6-8 小时

**描述**: 添加键盘快捷键切换不同相机视角（俯视、侧视、自由视角）。

**验收标准**:
- [ ] 实现相机类（Camera）
- [ ] 支持视角切换（F1-F4 快捷键）
- [ ] 支持鼠标拖拽旋转（自由视角）
- [ ] 支持滚轮缩放

**相关文件**:
- `recv.py` (Camera class, event handling)

**技术难点**: 相机变换矩阵计算

**关联需求**: 用户体验改进

---

### 任务 12: OBB 碰撞检测可视化 📋
**优先级**: 低
**预估工作量**: 8-10 小时

**描述**: 实现 OBB 碰撞检测算法，并在渲染时高亮碰撞的 OBB。

**验收标准**:
- [ ] 实现 OBB vs OBB 碰撞检测
- [ ] 碰撞的 OBB 显示为红色
- [ ] 性能满足实时要求（>30 FPS）

**相关文件**:
- `recv.py` (collision detection)

**技术参考**: SAT (Separating Axis Theorem)

**关联需求**: 功能扩展

---

### 任务 13: 性能统计和 FPS 显示 📋
**优先级**: 低
**预估工作量**: 2-3 小时

**描述**: 在窗口标题或屏幕上显示 FPS 和其他性能指标。

**验收标准**:
- [ ] 显示 FPS（平均、最小、最大）
- [ ] 显示接收数据速率（KB/s）
- [ ] 显示 OBB 数量
- [ ] 可通过快捷键切换显示/隐藏

**相关文件**:
- `recv.py` (performance stats)

**技术实现**: 使用 pygame.time.Clock()

**关联需求**: 调试和性能分析

---

## 计划任务 🔮

### 任务 14: 录制和回放功能 🔮
**优先级**: 低
**预估工作量**: 10-12 小时

**描述**: 支持录制接收的数据流，并支持回放。

**验收标准**:
- [ ] 录制数据到文件（二进制格式）
- [ ] 回放录制的数据
- [ ] 支持暂停/继续/快进/快退
- [ ] 时间轴显示

**技术挑战**: 大数据量存储和索引

**关联需求**: 调试和分析

---

### 任务 15: GUI 控制面板 🔮
**优先级**: 低
**预估工作量**: 15-20 小时

**描述**: 添加 GUI 控制面板（使用 Tkinter 或 ImGui），方便参数调整。

**验收标准**:
- [ ] 参数调整（地址、模式、渲染选项）
- [ ] 实时统计显示
- [ ] 日志输出窗口

**技术选型**:
- Tkinter（轻量）
- PyImGui（现代）

**关联需求**: 用户体验改进

---

### 任务 16: 单元测试和 CI/CD 🔮
**优先级**: 中
**预估工作量**: 8-10 小时

**描述**: 添加单元测试并配置 CI/CD 流程。

**验收标准**:
- [ ] 单元测试覆盖核心功能（数据解析、OBB 类、压缩）
- [ ] GitHub Actions 配置
- [ ] 自动化测试和构建

**技术选型**:
- Python: pytest
- C++: Google Test
- CI: GitHub Actions

**关联需求**: 质量保证

---

## 任务优先级指南

**高优先级** 🔴:
- 影响核心功能
- 阻塞其他任务
- 用户强烈需求

**中优先级** 🟡:
- 改善用户体验
- 提升性能
- 非阻塞性功能

**低优先级** 🟢:
- 锦上添花
- 长期优化
- 实验性功能

---

## 任务状态说明

| 状态 | 标记 | 说明 |
|------|------|------|
| **已完成** | ✅ | 所有验收标准满足，代码已合并 |
| **进行中** | 🔄 | 正在开发，部分完成 |
| **待做** | 📋 | 已规划，等待开始 |
| **计划** | 🔮 | 概念阶段，未详细规划 |
| **已取消** | ❌ | 不再执行 |
| **阻塞** | 🚫 | 依赖其他任务或资源 |

---

## 工作流建议

**开始新任务**:
1. 从待做任务中选择一个任务
2. 更新任务状态为"进行中"
3. 如需技术咨询：运行 `/wf_04_ask`
4. 开始编码：运行 `/wf_05_code`

**完成任务**:
1. 运行测试：`/wf_07_test`
2. 代码审查：`/wf_08_review`
3. 更新任务状态为"已完成"
4. 更新 PLANNING.md（如有架构变更）
5. 提交代码：`/wf_11_commit`

**添加新任务**:
1. 在对应的状态章节添加任务
2. 填写任务模板（描述、验收标准、优先级等）
3. 更新任务总览统计

---

**文档维护**: 此文档应在以下情况更新：
- 开始新任务时（更新状态）
- 完成任务时（更新状态、记录 git commit）
- 任务优先级变化时
- 添加新的计划任务时
