# LCPS 协同开发需求文档

**文档版本**: 1.0
**创建日期**: 2025-12-24
**负责人**: Architecture Team
**关联 ADR**: docs/adr/2025-12-24-lcps-plugin-architecture-v2.md
**关联 PRD**: docs/management/PRD_LCPS工具咨询.md

---

## 📋 文档目的

本文档定义 LCPS 安全系统和观测工具之间的协同开发需求，确保：
1. **数据接口一致性**：LCPS 端和工具端的数据格式对齐
2. **时间戳同步方案**：解决多数据源时间戳对齐问题
3. **生命周期状态定义**：统一 LCPS 状态机模型
4. **实施优先级**：明确协同开发的优先级和时间表

---

## 🎯 协同开发背景

### PRD 强调

PRD L30 重复强调：
> "整个功能需要 icrane LCPS 以及观测工具协同开发，共同体改满足设计需求"

### 核心挑战

| 挑战 | 描述 | 影响 |
|------|------|------|
| **数据格式对齐** | LCPS 和工具需要统一数据结构 | 数据解析错误、兼容性问题 |
| **时间戳同步** | 多数据源（OBB/点云/状态）时间戳不一致 | 回放数据不同步、误导调试 |
| **生命周期状态** | LCPS 状态转换需要观测工具理解 | 无法监控异常状态转换 |
| **带宽限制** | 完整点云传输会影响 LCPS 性能 | 需要下采样策略 |

---

## 🔴 优先级 P0：时间戳同步方案

### 问题描述

**现状**：
- LCPS 各模块（OBB 生成、点云处理、状态更新）独立运行
- 每个模块使用自己的时间戳（可能不同步）
- ZMQ 发布时间不一致（±50ms 误差）

**后果**：
```
示例场景：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
时间 T0: LCPS 生成 OBB（时间戳 T0）
时间 T0+30ms: LCPS 发布点云（时间戳 T0+30ms）
时间 T0+50ms: LCPS 发布状态（时间戳 T0+50ms）

观测工具回放时：
  - T0 显示 OBB
  - T0+30ms 显示点云（可能已经切换到下一帧）
  - T0+50ms 显示状态（OBB 和点云不匹配）

结果：误导调试，无法准确复现问题场景
```

### 方案 A：LCPS 端统一时间戳（推荐）⭐

**设计**：
```cpp
// LCPS 端伪代码

class LCPSCore {
private:
    // 统一时钟
    std::chrono::steady_clock::time_point base_time_;

public:
    void ProcessFrame() {
        // 1. 获取当前帧的统一时间戳
        Timestamp frame_timestamp = GetCurrentFrameTimestamp();

        // 2. 点云处理
        PointCloud pointcloud = ProcessPointCloud();

        // 3. OBB 生成
        std::vector<OBB> obbs = GenerateOBBs(pointcloud);

        // 4. 状态更新
        SystemStatus status = UpdateStatus();

        // 5. 使用同一时间戳发布所有数据
        PublishPointCloud(pointcloud, frame_timestamp);
        PublishOBBs(obbs, frame_timestamp);
        PublishStatus(status, frame_timestamp);
    }

    Timestamp GetCurrentFrameTimestamp() {
        // 使用系统单调时钟
        auto now = std::chrono::steady_clock::now();
        auto duration = now - base_time_;
        return std::chrono::duration_cast<std::chrono::microseconds>(duration).count();
    }
};
```

**数据格式**：
```json
// OBB 消息
{
  "timestamp": 1234567890.123456,  // 统一时间戳（微秒精度）
  "frame_id": 12345,               // 帧 ID
  "obbs": [...]
}

// PointCloud 消息
{
  "timestamp": 1234567890.123456,  // 同一时间戳
  "frame_id": 12345,               // 同一帧 ID
  "points": [...]
}

// Status 消息
{
  "timestamp": 1234567890.123456,  // 同一时间戳
  "frame_id": 12345,               // 同一帧 ID
  "lifecycle_state": "ENABLED",
  ...
}
```

**优点**：
- ✅ **精度高**：同步误差 <1ms
- ✅ **可靠**：单一时钟源，无漂移
- ✅ **简单**：观测工具端无需复杂对齐逻辑

**缺点**：
- ❌ **需要修改 LCPS**：需要改动 LCPS 核心循环
- ⚠️ **测试成本**：需要回归测试 LCPS 功能

**实施步骤**：
1. Week 1-2: LCPS 端实现统一时间戳
2. Week 2: 观测工具端验证时间戳同步
3. Week 3: 集成测试和验证

### 方案 B：工具端软同步（降级方案）

**设计**：
```python
# 观测工具端伪代码

class DataSynchronizer:
    def __init__(self, time_window_ms=50):
        self.time_window = time_window_ms / 1000.0  # 50ms
        self.obb_queue = []
        self.pointcloud_queue = []
        self.status_queue = []

    def align_data(self):
        """时间窗口对齐算法"""
        aligned_frames = []

        for obb in self.obb_queue:
            obb_timestamp = obb['timestamp']

            # 在时间窗口内查找最接近的点云
            pc = self._find_closest(
                self.pointcloud_queue,
                obb_timestamp,
                self.time_window
            )

            # 在时间窗口内查找最接近的状态
            status = self._find_closest(
                self.status_queue,
                obb_timestamp,
                self.time_window
            )

            if pc and status:
                aligned_frames.append({
                    'obb': obb,
                    'pointcloud': pc,
                    'status': status,
                    'sync_timestamp': obb_timestamp
                })

        return aligned_frames

    def _find_closest(self, queue, target_timestamp, window):
        """查找时间窗口内最接近的数据"""
        candidates = [
            item for item in queue
            if abs(item['timestamp'] - target_timestamp) <= window
        ]

        if not candidates:
            return None

        return min(candidates, key=lambda x: abs(x['timestamp'] - target_timestamp))
```

**优点**：
- ✅ **无需修改 LCPS**：观测工具独立实现
- ✅ **快速上线**：2-3 天实现

**缺点**：
- ❌ **精度低**：同步误差 ~50ms
- ❌ **复杂逻辑**：需要队列管理和窗口匹配
- ⚠️ **可能丢数据**：窗口外的数据会被丢弃

**适用场景**：
- LCPS 端短期内无法修改
- 临时解决方案
- 非关键场景（允许 50ms 误差）

### 决策和实施计划

| 方案 | 优先级 | 实施时间 | 责任方 |
|------|--------|---------|--------|
| **方案 A**（推荐） | 🔴 P0 | Week 1-3 | LCPS 团队 + 观测工具团队 |
| **方案 B**（降级） | 🟡 P1 | Week 2 | 观测工具团队 |

**实施策略**：
1. **Week 1**: 同时启动方案 A 和方案 B 开发
2. **Week 2**: 方案 B 先上线（临时方案）
3. **Week 3**: 方案 A 完成后替换方案 B

---

## 🔴 优先级 P0：生命周期状态定义

### 问题描述

**PRD 需求**：
- L24："观测数据（点云、OBB、状态、图像）、生命周期等等"
- 痛点 P2："LCPS 未按预期开启、关闭等等生命周期问题"

**现状**：
- LCPS 没有明确的生命周期状态枚举
- 观测工具无法监控状态转换
- 异常状态转换无法检测

### 状态机定义

**LCPS 生命周期状态枚举**（需要 LCPS 端实现）：

```cpp
// LCPS 端代码

/**
 * LCPS 生命周期状态
 *
 * 状态转换顺序：
 * UNINITIALIZED → INITIALIZED → ENABLED ↔ DISABLED → SHUTDOWN
 *                                 ↓
 *                              ERROR
 */
enum class LCPSLifecycleState : uint8_t {
    /**
     * 未初始化状态
     *
     * 说明：LCPS 模块尚未初始化
     * 合法转换：→ INITIALIZED
     */
    UNINITIALIZED = 0,

    /**
     * 已初始化状态
     *
     * 说明：LCPS 模块已初始化，但未启用
     * 合法转换：→ ENABLED
     */
    INITIALIZED = 1,

    /**
     * 已启用状态
     *
     * 说明：LCPS 正在运行，执行防撞检测
     * 合法转换：→ DISABLED, → SHUTDOWN, → ERROR
     */
    ENABLED = 2,

    /**
     * 已禁用状态
     *
     * 说明：LCPS 已暂停，不执行防撞检测
     * 合法转换：→ ENABLED, → SHUTDOWN
     */
    DISABLED = 3,

    /**
     * 已关闭状态
     *
     * 说明：LCPS 已关闭，释放资源
     * 合法转换：无（终态）
     */
    SHUTDOWN = 4,

    /**
     * 错误状态
     *
     * 说明：LCPS 遇到致命错误
     * 合法转换：→ SHUTDOWN
     */
    ERROR = 99
};

/**
 * 状态消息结构
 */
struct LCPSStatusMessage {
    Timestamp timestamp;            // 时间戳（微秒）
    uint32_t frame_id;              // 帧 ID
    LCPSLifecycleState state;       // 当前状态

    // 可选：状态附加信息
    struct {
        uint32_t uptime_seconds;    // 运行时间（秒）
        uint32_t processed_frames;  // 已处理帧数
        float cpu_usage;            // CPU 使用率（%）
        uint32_t error_code;        // 错误码（ERROR 状态时有效）
    } details;
};
```

### 合法状态转换表

| 从状态 | 到状态 | 是否合法 | 说明 |
|--------|--------|---------|------|
| UNINITIALIZED | INITIALIZED | ✅ | 初始化完成 |
| INITIALIZED | ENABLED | ✅ | 启用 LCPS |
| ENABLED | DISABLED | ✅ | 暂停 LCPS |
| DISABLED | ENABLED | ✅ | 恢复 LCPS |
| ENABLED | SHUTDOWN | ✅ | 关闭（直接从 ENABLED） |
| DISABLED | SHUTDOWN | ✅ | 关闭（从 DISABLED） |
| ENABLED | ERROR | ✅ | 遇到错误 |
| ERROR | SHUTDOWN | ✅ | 错误恢复后关闭 |
| **INITIALIZED** | **SHUTDOWN** | ❌ **异常** | 跳过 ENABLED |
| **ENABLED** | **UNINITIALIZED** | ❌ **异常** | 反向转换 |

### 异常检测规则

**观测工具端实现**（LifecycleMonitorPlugin）：

```python
class LifecycleMonitorPlugin:
    # 合法状态转换（与 LCPS 端保持一致）
    VALID_TRANSITIONS = {
        (LCPSLifecycleState.UNINITIALIZED, LCPSLifecycleState.INITIALIZED),
        (LCPSLifecycleState.INITIALIZED, LCPSLifecycleState.ENABLED),
        (LCPSLifecycleState.ENABLED, LCPSLifecycleState.DISABLED),
        (LCPSLifecycleState.DISABLED, LCPSLifecycleState.ENABLED),
        (LCPSLifecycleState.ENABLED, LCPSLifecycleState.SHUTDOWN),
        (LCPSLifecycleState.DISABLED, LCPSLifecycleState.SHUTDOWN),
        (LCPSLifecycleState.ENABLED, LCPSLifecycleState.ERROR),
        (LCPSLifecycleState.ERROR, LCPSLifecycleState.SHUTDOWN),
    }

    # 状态停留时间阈值（秒）
    DWELL_TIME_THRESHOLDS = {
        LCPSLifecycleState.INITIALIZED: 5,    # 不应超过 5 秒
        LCPSLifecycleState.DISABLED: 600,     # 不应超过 10 分钟
    }

    def check_state_transition(self, from_state, to_state):
        """检查状态转换是否合法"""
        if (from_state, to_state) not in self.VALID_TRANSITIONS:
            self.alert(
                severity="CRITICAL",
                message=f"Illegal state transition: {from_state.name} → {to_state.name}"
            )

    def check_dwell_time(self, state, duration):
        """检查状态停留时间"""
        threshold = self.DWELL_TIME_THRESHOLDS.get(state)
        if threshold and duration > threshold:
            self.alert(
                severity="WARNING",
                message=f"State {state.name} exceeded dwell time: {duration}s > {threshold}s"
            )
```

### 实施计划

| 任务 | 负责方 | 预估时间 | 优先级 |
|------|--------|---------|--------|
| 定义状态枚举（C++） | LCPS 团队 | 1 天 | 🔴 P0 |
| 实现状态消息发布 | LCPS 团队 | 2 天 | 🔴 P0 |
| LifecycleMonitorPlugin | 观测工具团队 | 3 天 | 🔴 P0 |
| 集成测试 | 双方 | 2 天 | 🔴 P0 |

---

## 🟡 优先级 P1：点云下采样发布

### 问题描述

**PRD 约束**：
- "crane 系统和观测工具之间的带宽有限"
- "压缩 90% 传输是一种模式（点云下采样）"

**现状**：
- LCPS 当前仅发布 OBB（压缩后）
- 不发布点云数据（带宽限制）
- 观测工具无法观测原始点云

### 解决方案

**方案 1：LCPS 端可选下采样发布**（推荐）

```cpp
// LCPS 端配置

struct LCPSConfig {
    bool publish_pointcloud;           // 是否发布点云
    float pointcloud_downsample_ratio; // 下采样比例（0.1 = 10%）
    DownsampleMethod downsample_method; // random, voxel_grid
};

// LCPS 端伪代码

void PublishPointCloud(const PointCloud& pointcloud, Timestamp timestamp) {
    if (!config_.publish_pointcloud) {
        return;  // 不发布
    }

    // 下采样
    PointCloud downsampled = Downsample(
        pointcloud,
        config_.pointcloud_downsample_ratio,
        config_.downsample_method
    );

    // 发布
    zmq_publisher_.Publish("pointcloud", downsampled, timestamp);
}
```

**方案 2：观测工具端本地录制完整点云**

- LCPS 端不发布点云
- LCPS 本地录制完整点云到 HDF5
- 观测工具事后读取 HDF5 文件回放

### 决策

| 场景 | 方案 | 说明 |
|------|------|------|
| **实时观测** | 方案 1（下采样发布） | 下采样到 10%，带宽 ~3.6 MB/s |
| **详细调试** | 方案 2（本地录制） | 完整点云，无带宽限制 |

**实施**：两种方案同时支持，通过配置切换。

---

## 📊 协同开发清单

### LCPS 端需要实现的功能

| 功能 | 优先级 | 预估工作量 | 依赖 |
|------|--------|-----------|------|
| **统一时间戳** | 🔴 P0 | 2-3 天 | 无 |
| **生命周期状态枚举** | 🔴 P0 | 1 天 | 无 |
| **状态消息发布** | 🔴 P0 | 2 天 | 生命周期状态枚举 |
| **点云下采样发布** | 🟡 P1 | 3-4 天 | 无 |
| **完整点云本地录制** | 🟡 P1 | 2-3 天 | HDF5 库 |

### 观测工具端需要实现的功能

| 功能 | 优先级 | 预估工作量 | 依赖 |
|------|--------|-----------|------|
| **时间戳同步验证** | 🔴 P0 | 1 天 | LCPS 统一时间戳 |
| **LifecycleMonitorPlugin** | 🔴 P0 | 3-4 天 | LCPS 状态发布 |
| **点云接收和渲染** | 🟡 P1 | 4-5 天 | LCPS 点云发布 |
| **HDF5 回放功能** | 🟡 P1 | 3-4 天 | LCPS 本地录制 |

### 接口文档

**ZMQ 消息格式规范**：

```protobuf
// 注：实际实现使用 JSON 或 BSON，此处用 Protobuf 描述语义

message OBBMessage {
    double timestamp = 1;      // 微秒精度时间戳
    uint32 frame_id = 2;       // 帧 ID
    repeated OBB obbs = 3;     // OBB 列表
}

message PointCloudMessage {
    double timestamp = 1;      // 微秒精度时间戳（与 OBBMessage 一致）
    uint32 frame_id = 2;       // 帧 ID（与 OBBMessage 一致）
    repeated Point3D points = 3; // 点云（已下采样）
}

message StatusMessage {
    double timestamp = 1;        // 微秒精度时间戳
    uint32 frame_id = 2;         // 帧 ID
    LCPSLifecycleState state = 3; // 生命周期状态
    StatusDetails details = 4;    // 状态详情
}
```

---

## 📅 协同开发时间表

### Week 1-2: 基础功能

| Week | LCPS 端 | 观测工具端 | 联合任务 |
|------|---------|-----------|---------|
| **Week 1** | 实现统一时间戳 | 实现软同步（方案 B）| 接口对齐会议 |
| **Week 2** | 实现状态枚举 + 发布 | LifecycleMonitorPlugin | 集成测试 |

### Week 3-4: 高级功能

| Week | LCPS 端 | 观测工具端 | 联合任务 |
|------|---------|-----------|---------|
| **Week 3** | 点云下采样发布 | 点云接收和渲染 | 性能测试 |
| **Week 4** | 完整点云本地录制 | HDF5 回放功能 | 端到端验证 |

---

## ✅ 验收标准

### P0 功能验收

| 功能 | 验收标准 | 测试方法 |
|------|---------|---------|
| **时间戳同步** | 同步误差 <5ms | 录制 100 帧数据，分析时间戳偏差 |
| **生命周期监控** | 100% 检测异常转换 | 注入 10 个异常状态转换，验证告警 |
| **状态历史记录** | 完整记录所有转换 | 回放 1 小时数据，验证状态完整性 |

### P1 功能验收

| 功能 | 验收标准 | 测试方法 |
|------|---------|---------|
| **点云下采样** | 带宽 <5 MB/s | 测量网络流量 |
| **点云渲染** | 稳定 60 FPS | 渲染 10,000 点稳定 60 FPS |
| **HDF5 回放** | 数据完整性 100% | 对比录制和回放数据 |

---

## 📞 联系方式和会议安排

### 责任人

| 角色 | 姓名 | 负责范围 |
|------|------|---------|
| **LCPS 架构师** | TBD | 时间戳、状态枚举、点云发布 |
| **观测工具架构师** | TBD | 插件系统、同步算法、渲染 |

### 定期会议

| 会议 | 频率 | 参与方 | 议题 |
|------|------|--------|------|
| **接口对齐会** | Week 1 | 双方架构师 | 接口定义、数据格式 |
| **集成测试会** | Week 2, 4 | 双方开发团队 | 集成测试、问题解决 |
| **每周同步会** | 每周五 | 双方团队 | 进度同步、风险识别 |

---

## 📖 参考文档

- **ADR v2**: docs/adr/2025-12-24-lcps-plugin-architecture-v2.md
- **PRD**: docs/management/PRD_LCPS工具咨询.md
- **PLANNING**: docs/management/PLANNING.md § LCPS 工具架构

---

**文档维护**：
- 接口变更需要双方确认并更新本文档
- 每次会议后更新进度和决策
- 保持与 ADR 和 PRD 的一致性
