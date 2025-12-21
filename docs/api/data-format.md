---
title: "OBBDemo 数据格式规范"
description: "OBB 数据结构、ZMQ 消息格式和序列化方式的完整规范"
type: "API参考"
status: "完成"
priority: "高"
created_date: "2025-12-20"
last_updated: "2025-12-21"
related_documents:
  - "docs/architecture/system-design.md"
  - "docs/usage/quick-start.md"
related_code:
  - "sender.cpp:12-17"
  - "sender.cpp:45-70"
  - "recv.py:19-27"
  - "recv.py:203-227"
---

# OBBDemo 数据格式规范

## OBB 数据结构

### C++ 结构定义

```cpp
struct OBB
{
    std::string type;                    // OBB 类型标识
    std::array<double, 3> position;      // 3D 位置 (x, y, z)
    std::array<double, 3> rotation;      // 旋转（欧拉角）(rx, ry, rz)
    std::array<double, 3> size;          // 尺寸 (width, height, depth)
};
```

**代码位置**: sender.cpp:12-17

### Python 类定义

```python
class OBB:
    def __init__(self, type, position, rotation, size, collision):
        self.type = type                     # str - OBB 类型
        self.position = Vector3(position)    # Vector3 - 位置向量
        self.rotation = rotation             # np.array(4,4) - 旋转矩阵
        self.size = Vector3(size)            # Vector3 - 尺寸向量
        self.color = (1, 1, 1, 1)            # tuple - RGBA 颜色
        self.collision = collision           # bool - 碰撞状态
```

**代码位置**: recv.py:19-27

---

## 字段说明

### type（类型）

**类型**: `string`
**必需**: ✅ 是

**说明**: OBB 对象的类型标识，用于区分不同类别的物体。

**可能的值**:
- `"A"`: A 类 OBB（通常是主要对象，如地面、墙壁）
- `"B"`: B 类 OBB（通常是次要对象，如障碍物、物品）
- 可扩展为其他类型（如 `"C"`, `"D"` 等）

**示例**:
```json
"type": "A"
```

---

### position（位置）

**类型**: `array<double, 3>`
**必需**: ✅ 是

**说明**: OBB 在 3D 空间中的中心位置坐标。

**坐标系**: 右手坐标系
- X 轴: 右方向
- Y 轴: 上方向
- Z 轴: 向外方向

**单位**: 米（或无单位，取决于应用场景）

**格式**: `[x, y, z]`

**示例**:
```json
"position": [2.5, 1.0, -3.0]
```

**有效范围**: `-∞ ~ +∞`（理论上）
**推荐范围**: `-50.0 ~ +50.0`（受相机 far plane 限制）

---

### rotation（旋转）

**类型**: `array<double, 3>`
**必需**: ✅ 是

**说明**: OBB 的旋转，使用欧拉角表示（在 C++ sender 端）。在 Python receiver 端会被转换为 4x4 旋转矩阵。

**格式**: `[rx, ry, rz]`（欧拉角，单位：弧度）
- `rx`: 绕 X 轴旋转
- `ry`: 绕 Y 轴旋转
- `rz`: 绕 Z 轴旋转

**示例**:
```json
"rotation": [0.0, 1.57, 0.0]  // 绕 Y 轴旋转 90°
```

**注意**:
- 当前 sender.cpp 实现中，rotation 字段被设置为 `[0.0, 0.0, 0.0]`（无旋转）
- 如需支持任意旋转，建议改用**四元数**（避免万向锁问题）

**有效范围**: `0.0 ~ 2π` (0° ~ 360°)

---

### size（尺寸）

**类型**: `array<double, 3>`
**必需**: ✅ 是

**说明**: OBB 在三个轴向上的尺寸（宽度、高度、深度）。

**格式**: `[width, height, depth]`

**示例**:
```json
"size": [5.0, 5.0, 5.0]  // 5x5x5 的立方体
```

**有效范围**: `> 0`（必须为正数）
**推荐范围**: `0.1 ~ 20.0`

---

### collision（碰撞状态）

**类型**: `bool`
**必需**: ❌ 否（仅 Python 端）

**说明**: 标记 OBB 是否处于碰撞状态（用于可视化）。

**可能的值**:
- `true`: 发生碰撞（可能显示为红色）
- `false`: 无碰撞（默认颜色）

**注意**: 此字段仅在 Python 端使用，C++ sender 不包含此字段。

---

## 消息格式

### 模式 1: Normal (普通 JSON)

**适用场景**: 本地网络、调试

**格式**: JSON 数组

**示例**:
```json
[
  {
    "type": "A",
    "position": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0],
    "size": [5.0, 5.0, 5.0]
  },
  {
    "type": "B",
    "position": [2.0, 2.0, 2.0],
    "rotation": [0.0, 0.0, 0.0],
    "size": [1.0, 1.0, 1.0]
  }
]
```

**ZMQ 传输**:
```python
# Sender (C++)
std::string msg = j.dump();  // JSON 序列化
zmq::message_t zmq_msg(msg.size());
memcpy(zmq_msg.data(), msg.data(), msg.size());
publisher.send(zmq_msg, zmq::send_flags::dontwait);

# Receiver (Python)
message = socket.recv(flags=zmq.NOBLOCK)
data = json.loads(message)  // JSON 反序列化
```

**数据大小**（100 个 OBB）: ~10 KB

---

### 模式 2: Compressed (压缩 JSON)

**适用场景**: 带宽受限、大量数据

**格式**: 4字节原始大小（big-endian）+ zlib 压缩的 JSON

**二进制格式**:
```
[4 bytes: original_size (big-endian)] [N bytes: zlib compressed JSON data]
```

**示例**（解压后的 JSON）:
```json
{
  "data": [
    {
      "type": "A",
      "position": [0.0, 0.0, 0.0],
      "rotation": [1.0, 0.0, 0.0, 0.0],
      "size": [5.0, 5.0, 5.0],
      "collision_status": 0
    },
    ...
  ],
  "points": [  // 可选：点云数据
    [x1, y1, z1],
    [x2, y2, z2],
    ...
  ]
}
```

**ZMQ 传输**:
```cpp
// Sender (C++)
json j = {{"data", obbs_array}};
std::string json_str = j.dump();

// 创建 4字节 size prefix (big-endian) + 压缩数据
std::vector<uint8_t> compressed(4);
uint32_t orig_size = json_str.size();
compressed[0] = (orig_size >> 24) & 0xFF;
compressed[1] = (orig_size >> 16) & 0xFF;
compressed[2] = (orig_size >> 8) & 0xFF;
compressed[3] = orig_size & 0xFF;

// zlib 压缩
uLongf compressed_size = compressBound(json_str.size());
compressed.resize(compressed_size + 4);
compress(compressed.data() + 4, &compressed_size,
         (const uint8_t*)json_str.data(), json_str.size());
compressed.resize(compressed_size + 4);

socket.send(zmq::message_t(compressed.data(), compressed.size()));
```

```python
# Receiver (Python)
ori_data = socket.recv(flags=zmq.NOBLOCK)

# 解析前4字节（原始大小）
original_size = int.from_bytes(ori_data[:4], byteorder="big")

# 解压数据（跳过前4字节）
decompressed_json = zlib.decompress(ori_data[4:])

# 验证大小
assert len(decompressed_json) == original_size

# 解析 JSON
data = json.loads(decompressed_json)
obbs = data["data"]
```

**数据大小**:
- 原始 JSON: ~228 bytes (单个 OBB)
- 压缩后: ~113 bytes (单个 OBB)
- 压缩率: ~50%

**数据大小**（100 个 OBB）: ~2-4 KB（压缩率 60-80%）

**代码位置**:
- Sender: sender.cpp:45-70
- Receiver: recv.py:203-227

---

## 扩展字段

### 点云数据 (Points)

**类型**: `array<array<double, 3>>`
**必需**: ❌ 否

**说明**: 点云数据，每个点包含 3D 坐标。

**格式**:
```json
"points": [
  [x1, y1, z1],
  [x2, y2, z2],
  ...
]
```

**使用场景**:
- 传感器数据可视化（如 LiDAR）
- 环境地图点云

**代码位置**: recv.py:207-224（解析点云）

---

## 版本兼容性

**当前版本**: v1.0（隐式，无版本字段）

**向后兼容策略**:
- 新增字段：可选字段，旧版本忽略
- 删除字段：不建议，会破坏兼容性
- 修改字段类型：需要升级主版本号

**建议的版本管理**:
在消息中添加 `version` 字段：
```json
{
  "version": "1.0",
  "obbs": [ ... ]
}
```

---

## 性能考量

### 数据大小对比

| OBB 数量 | Normal (JSON) | Compressed (BSON+zlib) | 压缩率 |
|---------|--------------|----------------------|-------|
| 10      | ~1 KB        | ~0.3 KB              | 70%   |
| 100     | ~10 KB       | ~2-4 KB              | 60-80%|
| 1000    | ~100 KB      | ~20-30 KB            | 70-80%|

### 模式选择建议

**使用 Normal 模式**（默认）:
- ✅ 本地网络（localhost）
- ✅ 调试和开发
- ✅ OBB 数量 < 100
- ✅ 简单场景，无需优化带宽

**使用 Compressed 模式**:
- ✅ 局域网（LAN）或广域网
- ✅ OBB 数量 > 100
- ✅ 包含点云数据
- ✅ 需要节省 50% 带宽

**命令行示例**:
```bash
# 普通模式
./sender -m n          # 或 ./sender（默认）
python recv.py -a localhost:5555 -m n

# 压缩模式
./sender -m c
python recv.py -a localhost:5555 -m c
```

---

## 验证和错误处理

### 字段验证

接收端应验证以下约束：

```python
def validate_obb(data):
    assert "type" in data, "Missing 'type' field"
    assert "position" in data and len(data["position"]) == 3
    assert "rotation" in data and len(data["rotation"]) == 3
    assert "size" in data and len(data["size"]) == 3

    # 验证 size > 0
    assert all(s > 0 for s in data["size"]), "Size must be positive"

    return True
```

### 错误处理

**解析失败**:
```python
try:
    data = json.loads(message)
except json.JSONDecodeError as e:
    print(f"JSON parse error: {e}")
    # 跳过此消息
```

**字段缺失**:
```python
if "position" not in obb_data:
    print(f"Warning: Missing 'position' field, skipping OBB")
    continue
```

---

## 示例数据集

### 单个 OBB（A 类）

```json
{
  "type": "A",
  "position": [0.0, 0.0, 0.0],
  "rotation": [0.0, 0.0, 0.0],
  "size": [5.0, 5.0, 5.0]
}
```

### 多个 OBB

```json
[
  {
    "type": "A",
    "position": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0],
    "size": [5.0, 5.0, 5.0]
  },
  {
    "type": "B",
    "position": [3.0, 1.0, 2.0],
    "rotation": [0.0, 0.5, 0.0],
    "size": [1.0, 2.0, 1.0]
  },
  {
    "type": "B",
    "position": [-2.0, 0.5, -1.0],
    "rotation": [0.0, 0.0, 0.0],
    "size": [0.5, 0.5, 0.5]
  }
]
```

---

## 相关文档

- [系统架构设计](../architecture/system-design.md) - 完整的系统架构
- [快速开始](../usage/quick-start.md) - 如何运行系统
- [PLANNING.md](../../docs/management/PLANNING.md) - 技术决策和 ADR
