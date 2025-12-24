# LCPS 数据协议规范

**版本**: 1.0
**创建日期**: 2025-12-24
**父文档**: [LCPS综合设计方案](LCPS_COMPREHENSIVE_DESIGN.md)
**状态**: 设计完成

## 目的

定义LCPS系统与观测工具之间的数据通信协议，包括消息格式、数据结构和通信规范。

---

## 1. 通信架构

### 1.1 ZMQ通信模式

```
LCPS System (C++)                    Observer Tool (Python/C++)
┌──────────────┐                    ┌──────────────┐
│ PUB :5555    │ ═══════════════>  │ SUB (OBB)    │
│ PUB :5556    │ ═══════════════>  │ SUB (PC)     │
│ PUB :5557    │ ═══════════════>  │ SUB (Status) │
│ PUB :5558    │ ═══════════════>  │ SUB (Image)  │
└──────────────┘                    └──────────────┘
```

**特性**：
- 模式：PUB/SUB（发布-订阅）
- 传输：TCP
- 阻塞：非阻塞发送（`ZMQ_DONTWAIT`）
- 缓冲：高水位标记（HWM）= 100

### 1.2 端口分配

| 端口 | 数据类型 | 频率 | 优先级 | 必需 |
|------|---------|------|--------|------|
| 5555 | OBB数据 | 10-30 Hz | P0 | ✅ |
| 5556 | 点云数据 | 10 Hz | P1 | 可选 |
| 5557 | 状态数据 | 1 Hz | P0 | ✅ |
| 5558 | 图像数据 | 1-5 Hz | P2 | 可选 |

---

## 2. 消息格式

### 2.1 通用消息结构（JSON）

所有消息采用统一的JSON格式：

```json
{
  "header": {
    "version": "1.0",
    "timestamp": 1703419200.123456,
    "seq_id": 12345,
    "source": "lcps_node_1",
    "checksum": "sha256_hash_optional"
  },
  "payload": {
    // 具体数据，根据通道不同而不同
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `version` | string | 协议版本（语义化版本）| ✅ |
| `timestamp` | float64 | Unix时间戳（秒，微秒精度）| ✅ |
| `seq_id` | uint64 | 序列号（单调递增，检测丢包）| ✅ |
| `source` | string | 数据源标识符 | ✅ |
| `checksum` | string | 数据校验和（可选，用于完整性验证）| 可选 |

### 2.2 压缩传输（可选）

对于大数据（点云），支持压缩传输：

```
[4字节: 原始长度] + [压缩数据]
```

**压缩算法**：
- **zlib**（默认）：平衡压缩率和速度
- **lz4**（可选）：更快，压缩率稍低
- **zstd**（推荐）：最佳压缩率

**使用规则**：
- 数据 > 1KB：自动压缩
- 数据 < 1KB：不压缩（避免开销）

---

## 3. 数据通道详细规范

### 3.1 OBB通道（端口5555）

**用途**：传输障碍物边界框数据

**消息示例**：

```json
{
  "header": {
    "version": "1.0",
    "timestamp": 1703419200.123456,
    "seq_id": 12345,
    "source": "lcps_node_1"
  },
  "payload": {
    "type": "obb_list",
    "frame_id": "laser_frame",
    "count": 3,
    "obbs": [
      {
        "id": "obb_001",
        "type": "dynamic_obstacle",
        "position": [1.2, 3.4, 0.5],
        "rotation": [0.0, 0.0, 0.785],
        "size": [0.5, 0.5, 1.8],
        "confidence": 0.95,
        "track_id": 42,
        "velocity": [0.1, 0.0, 0.0]
      },
      {
        "id": "obb_002",
        "type": "static_obstacle",
        "position": [-2.0, 1.0, 0.0],
        "rotation": [0.0, 0.0, 1.57],
        "size": [1.0, 1.0, 2.0],
        "confidence": 0.99,
        "track_id": null,
        "velocity": null
      }
    ]
  }
}
```

**OBB对象字段**：

| 字段 | 类型 | 单位 | 说明 | 必需 |
|------|------|------|------|------|
| `id` | string | - | 唯一标识符 | ✅ |
| `type` | enum | - | `dynamic_obstacle`, `static_obstacle`, `unknown` | ✅ |
| `position` | float[3] | 米 | [x, y, z]，相对于laser_frame | ✅ |
| `rotation` | float[3] | 弧度 | [roll, pitch, yaw]，欧拉角 | ✅ |
| `size` | float[3] | 米 | [length, width, height] | ✅ |
| `confidence` | float | - | 置信度 [0.0, 1.0] | ✅ |
| `track_id` | int/null | - | 跟踪ID（null表示未跟踪）| 可选 |
| `velocity` | float[3]/null | m/s | [vx, vy, vz]（静态障碍物为null）| 可选 |

**频率**：10-30 Hz（根据LCPS处理速度）

---

### 3.2 点云通道（端口5556）

**用途**：传输激光点云数据（可选下采样）

**消息示例**：

```json
{
  "header": {...},
  "payload": {
    "type": "pointcloud",
    "frame_id": "laser_frame",
    "downsampled": true,
    "downsample_ratio": 0.1,
    "format": "xyzi",
    "compression": "zlib",
    "point_count": 12345,
    "points_base64": "eJzt3UFu2zAQheG..."
  }
}
```

**字段说明**：

| 字段 | 类型 | 说明 | 必需 |
|------|------|------|------|
| `frame_id` | string | 坐标系标识 | ✅ |
| `downsampled` | bool | 是否下采样 | ✅ |
| `downsample_ratio` | float | 下采样比例（1.0=全部，0.1=10%）| 条件 |
| `format` | enum | `xyz`, `xyzi`（带强度）| ✅ |
| `compression` | enum | `none`, `zlib`, `lz4`, `zstd` | ✅ |
| `point_count` | uint32 | 点数 | ✅ |
| `points_base64` | string | Base64编码的点云数据 | ✅ |

**点云数据格式**（解码后）：

```c
// format="xyz"
struct Point {
    float x, y, z;
};

// format="xyzi"
struct PointI {
    float x, y, z, intensity;
};
```

**下采样策略**（基于ADR-003）：

| 场景 | 下采样比例 | 带宽节省 | 用途 |
|------|----------|---------|------|
| 实时观测 | 0.1 (10%) | 90% | 快速预览 |
| 调试分析 | 0.3 (30%) | 70% | 详细分析 |
| 完整录制 | 1.0 (100%) | 0% | 离线回放 |

**频率**：10 Hz（降低带宽压力）

---

### 3.3 状态通道（端口5557）

**用途**：传输LCPS系统状态和诊断信息

**消息示例**：

```json
{
  "header": {...},
  "payload": {
    "type": "system_status",
    "lcps_state": "active",
    "protection_zone": {
      "zone_id": "zone_001",
      "is_triggered": true,
      "trigger_count": 3
    },
    "alerts": [
      {
        "alert_id": "alert_001",
        "timestamp": 1703419200.5,
        "type": "collision_risk",
        "severity": "high",
        "message": "障碍物进入危险区"
      }
    ],
    "metrics": {
      "fps": 28.5,
      "pointcloud_count": 45678,
      "obb_count": 3,
      "cpu_usage": 45.2,
      "memory_mb": 512
    },
    "lifecycle": {
      "uptime_sec": 3600,
      "last_restart": 1703415600.0,
      "restart_count": 2
    }
  }
}
```

**LCPS状态枚举**：

| 状态 | 说明 |
|------|------|
| `inactive` | 未激活（待机） |
| `active` | 激活（正常工作） |
| `warning` | 警告状态（部分功能降级） |
| `error` | 错误状态（功能异常） |
| `emergency_stop` | 紧急停止 |

**频率**：1 Hz

---

### 3.4 图像通道（端口5558，可选）

**用途**：传输相机图像（用于场景回放）

**消息示例**：

```json
{
  "header": {...},
  "payload": {
    "type": "camera_image",
    "camera_id": "cam_001",
    "format": "jpeg",
    "width": 1920,
    "height": 1080,
    "compression_quality": 85,
    "image_base64": "iVBORw0KGgo..."
  }
}
```

**支持格式**：
- `jpeg`：高压缩率，有损
- `png`：无损，文件大
- `webp`：现代格式，平衡压缩率和质量

**频率**：1-5 Hz（根据需要）

---

## 4. 数据同步

### 4.1 时间戳同步

**要求**：
- 所有数据源使用统一时钟（NTP同步）
- 时间戳精度：微秒（10^-6秒）
- 最大时钟偏差：< 10ms

**同步策略**：

```python
class DataSynchronizer:
    def __init__(self, tolerance_ms=50):
        self.tolerance = tolerance_ms / 1000.0  # 转换为秒
        self.buffers = {}  # 每个通道的缓冲

    def add_frame(self, channel: str, frame: DataFrame):
        """添加数据帧到对应通道缓冲"""
        self.buffers[channel].append(frame)

    def get_synchronized_frame(self) -> Optional[SyncedFrame]:
        """获取时间戳对齐的数据帧"""
        # 1. 找到所有通道中最早的时间戳
        min_ts = min(buf[0].timestamp for buf in self.buffers.values() if buf)

        # 2. 在容忍度内收集所有通道的数据
        synced = {}
        for channel, buf in self.buffers.items():
            for frame in buf:
                if abs(frame.timestamp - min_ts) <= self.tolerance:
                    synced[channel] = frame
                    buf.remove(frame)
                    break

        # 3. 确保关键通道都有数据
        if 'obb' in synced and 'status' in synced:
            return SyncedFrame(timestamp=min_ts, data=synced)

        return None
```

### 4.2 丢包检测

使用序列号（`seq_id`）检测丢包：

```python
class PacketLossDetector:
    def __init__(self):
        self.last_seq_id = {}

    def check_loss(self, channel: str, seq_id: int) -> Optional[int]:
        """返回丢失的包数量，None表示正常"""
        if channel not in self.last_seq_id:
            self.last_seq_id[channel] = seq_id
            return None

        expected = self.last_seq_id[channel] + 1
        if seq_id > expected:
            loss = seq_id - expected
            self.last_seq_id[channel] = seq_id
            return loss

        self.last_seq_id[channel] = seq_id
        return None
```

---

## 5. 错误处理

### 5.1 超时处理

| 场景 | 超时 | 处理策略 |
|------|------|---------|
| 数据接收超时 | 1秒 | 重新订阅 |
| 连接超时 | 5秒 | 重新连接（最多3次）|
| 心跳超时 | 5秒 | 标记数据源为离线 |

### 5.2 数据验证

```python
def validate_message(msg: dict) -> bool:
    """验证消息格式"""
    # 1. 检查必需字段
    if 'header' not in msg or 'payload' not in msg:
        return False

    header = msg['header']
    required_fields = ['version', 'timestamp', 'seq_id', 'source']
    if not all(field in header for field in required_fields):
        return False

    # 2. 检查版本兼容性
    if not is_version_compatible(header['version']):
        return False

    # 3. 检查时间戳合理性
    now = time.time()
    if abs(header['timestamp'] - now) > 10:  # 10秒容忍度
        logger.warning(f"时间戳偏差过大: {header['timestamp']}")

    # 4. 检查校验和（如果有）
    if 'checksum' in header:
        if not verify_checksum(msg, header['checksum']):
            return False

    return True
```

---

## 6. 协议版本演进

### 6.1 语义化版本

版本格式：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的API变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修复

### 6.2 兼容性策略

```python
def is_version_compatible(version: str) -> bool:
    """检查版本兼容性"""
    major, minor, patch = map(int, version.split('.'))

    # 当前支持的版本范围
    MIN_VERSION = (1, 0, 0)
    MAX_VERSION = (1, 99, 99)

    return MIN_VERSION <= (major, minor, patch) <= MAX_VERSION
```

---

## 7. 性能要求

| 指标 | 要求 | 验收标准 |
|------|------|---------|
| OBB发送延迟 | < 5ms | P99 < 10ms |
| 点云压缩时间 | < 20ms | 不阻塞发送 |
| 消息序列化时间 | < 1ms | CPU占用 < 5% |
| 总带宽消耗 | < 10 Mbps | 不影响其他功能 |

---

## 8. 示例代码

### 8.1 发送端（C++）

```cpp
// OBB发送示例
json msg;
msg["header"]["version"] = "1.0";
msg["header"]["timestamp"] = get_timestamp_us();
msg["header"]["seq_id"] = seq_counter++;
msg["header"]["source"] = "lcps_node_1";

json obbs = json::array();
for (const auto& obb : obb_list) {
    obbs.push_back({
        {"id", obb.id},
        {"type", obb.type},
        {"position", {obb.x, obb.y, obb.z}},
        {"rotation", {obb.roll, obb.pitch, obb.yaw}},
        {"size", {obb.length, obb.width, obb.height}},
        {"confidence", obb.confidence}
    });
}

msg["payload"] = {
    {"type", "obb_list"},
    {"count", obbs.size()},
    {"obbs", obbs}
};

std::string serialized = msg.dump();
zmq_send(publisher, serialized.c_str(), serialized.size(), ZMQ_DONTWAIT);
```

### 8.2 接收端（Python）

```python
# OBB接收示例
class OBBChannel(DataChannel):
    def __init__(self, address="tcp://localhost:5555"):
        self.socket = zmq.Context().socket(zmq.SUB)
        self.socket.connect(address)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")

    def receive(self) -> Optional[DataFrame]:
        try:
            msg_bytes = self.socket.recv(zmq.NOBLOCK)
            msg = json.loads(msg_bytes)

            if not validate_message(msg):
                logger.error("消息验证失败")
                return None

            return self.parse_data(msg)
        except zmq.Again:
            return None

    def parse_data(self, msg: dict) -> DataFrame:
        header = msg['header']
        payload = msg['payload']

        return DataFrame(
            timestamp=header['timestamp'],
            seq_id=header['seq_id'],
            obbs=[OBB(**obb) for obb in payload['obbs']]
        )
```

---

## 9. 测试用例

### 9.1 功能测试

| 测试项 | 输入 | 预期输出 |
|--------|------|---------|
| 正常消息解析 | 标准JSON消息 | 成功解析 |
| 缺少必需字段 | 缺少`timestamp` | 验证失败 |
| 版本不兼容 | `version="2.0"` | 拒绝处理 |
| 压缩传输 | zlib压缩点云 | 正确解压 |
| 丢包检测 | seq_id跳变 | 报告丢包数量 |

### 9.2 性能测试

```python
# 性能基准测试
def benchmark_protocol():
    # 测试序列化性能
    msg = create_sample_message(obb_count=10)
    start = time.time()
    for _ in range(1000):
        serialized = json.dumps(msg)
    duration = time.time() - start
    assert duration < 1.0  # 1000次序列化 < 1秒

    # 测试压缩性能
    pointcloud = np.random.random((10000, 3)).astype(np.float32)
    start = time.time()
    compressed = zlib.compress(pointcloud.tobytes())
    duration = time.time() - start
    assert duration < 0.02  # < 20ms
```

---

## 10. 参考资料

- ZeroMQ Messaging Patterns: https://zguide.zeromq.org/
- JSON Schema: https://json-schema.org/
- Base64 Encoding: https://tools.ietf.org/html/rfc4648

---

**版本历史**：
- v1.0 (2025-12-24): 初始版本
