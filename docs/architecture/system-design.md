---
title: "OBBDemo 系统架构设计"
description: "OBBDemo 的整体架构、模块关系、数据流和通信机制"
type: "架构决策"
status: "完成"
priority: "高"
created_date: "2025-12-20"
last_updated: "2025-12-20"
related_documents:
  - "docs/api/data-format.md"
  - "docs/development/setup.md"
related_code:
  - "sender.cpp"
  - "recv.py"
  - "LCPSViewer.py"
---

# OBBDemo 系统架构设计

## 概述

OBBDemo 是一个基于 ZeroMQ 的实时 3D 数据可视化系统，采用典型的**生产者-消费者架构**，通过发布-订阅（PUB/SUB）模式实现 C++ 发送端和 Python 接收端之间的解耦通信。

**核心特性**:
- **低延迟通信**: 使用 ZeroMQ 实现毫秒级数据传输
- **跨语言互操作**: C++ 生成数据，Python 可视化
- **灵活的数据模式**: 支持普通和压缩两种传输模式
- **实时3D渲染**: 基于 OpenGL 的高性能渲染

---

## 系统架构图

### 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         OBBDemo 系统                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐         Network Layer        ┌────────────┐ │
│  │  Sender (C++)   │────── ZMQ PUB/SUB (TCP) ────>│ Receiver   │ │
│  │                 │      Port: 5555              │ (Python)   │ │
│  │  ┌───────────┐  │                              │            │ │
│  │  │ OBB Gen   │  │                              │ ┌────────┐ │ │
│  │  └─────┬─────┘  │                              │ │ Parser │ │ │
│  │        │        │                              │ └────┬───┘ │ │
│  │  ┌─────▼─────┐  │                              │      │     │ │
│  │  │ JSON      │  │                              │ ┌────▼───┐ │ │
│  │  │ Serialize │  │                              │ │ OpenGL │ │ │
│  │  └─────┬─────┘  │                              │ │ Render │ │ │
│  │        │        │                              │ └────────┘ │ │
│  │  ┌─────▼─────┐  │                              │            │ │
│  │  │ ZMQ Pub   │  │                              │            │ │
│  │  └───────────┘  │                              │            │ │
│  └─────────────────┘                              └────────────┘ │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 模块关系图

```
Sender Module (sender.cpp)
├── OBB Generator
│   └── generateRandomOBBs()
├── JSON Serializer
│   └── nlohmann::json
└── ZMQ Publisher
    └── zmq::socket_t (PUB)

Receiver Module (recv.py / LCPSViewer.py)
├── ZMQ Subscriber
│   └── zmq.Context, zmq.SUB
├── Data Parser
│   ├── recv_obb() [Normal JSON]
│   ├── recv_compressed_data() [zlib + BSON]
│   └── recv_compressed_obb() [zlib + BSON (OBB only)]
├── Data Model
│   └── OBB Class (type, position, rotation, size, color, collision)
└── Rendering Engine
    ├── OpenGL Initialization (Pygame)
    ├── draw_obb()
    ├── draw_wire_cube()
    └── quaternion_to_matrix()
```

---

## 数据流

### 正常模式（Normal Mode）

```
[Sender]                                  [Receiver]

OBB Data (struct)
    │
    ▼
JSON Serialization
{"type": "A", "position": [...], ...}
    │
    ▼
ZMQ Send (tcp://5555)
    │
    ├──────── Network (TCP) ──────────>  ZMQ Recv
    │                                        │
    │                                        ▼
    │                                   JSON Parse
    │                                        │
    │                                        ▼
    │                                   OBB Objects
    │                                        │
    │                                        ▼
    │                                   OpenGL Render
    │                                        │
    │                                        ▼
    │                                   Display (800x600)
```

### 压缩模式（Compressed Mode）

```
[Sender]                                  [Receiver]

OBB Data + Points Data
    │
    ▼
BSON Serialization
    │
    ▼
zlib Compression (60-80% reduction)
    │
    ▼
ZMQ Send (tcp://5555)
    │
    ├──────── Network (TCP) ──────────>  ZMQ Recv
    │                                        │
    │                                        ▼
    │                                   zlib Decompress
    │                                        │
    │                                        ▼
    │                                   BSON Parse
    │                                        │
    │                                        ▼
    │                                   OBB Objects + Points
    │                                        │
    │                                        ▼
    │                                   OpenGL Render
    │                                        │
    │                                        ▼
    │                                   Display (800x600)
```

---

## 核心模块设计

### 1. Sender 模块 (sender.cpp)

**职责**: 生成 OBB 数据并通过 ZMQ 发布

**关键类/函数**:
```cpp
struct OBB {
    std::string type;                    // OBB 类型（A/B）
    std::array<double, 3> position;      // 位置 (x, y, z)
    std::array<double, 3> rotation;      // 旋转（欧拉角或四元数）
    std::array<double, 3> size;          // 尺寸 (width, height, depth)
};

std::vector<OBB> generateRandomOBBs(int count);
```

**发送流程**:
1. 生成 OBB 数据（`generateRandomOBBs()`）
2. 序列化为 JSON（`nlohmann::json`）
3. 创建 ZMQ 消息（`zmq::message_t`）
4. 发送（`publisher.send()`）
5. 等待 100ms（控制频率）

**配置**:
- 端口: `tcp://*:5555`
- 发送间隔: 100ms
- 默认 OBB 数量: 1 个（可调整）

**代码位置**: sender.cpp:46-73

---

### 2. Receiver 模块 (recv.py)

**职责**: 接收 ZMQ 数据并进行 3D 渲染

**关键类/函数**:

#### 2.1 数据模型
```python
class OBB:
    def __init__(self, type, position, rotation, size, collision):
        self.type = type                     # OBB 类型
        self.position = Vector3(position)    # 位置向量
        self.rotation = rotation             # 旋转矩阵（4x4）
        self.size = Vector3(size)            # 尺寸向量
        self.color = (1, 1, 1, 1)            # RGBA 颜色
        self.collision = collision           # 碰撞状态
```

#### 2.2 数据接收
```python
def recv_obb(socket, obbs):
    """接收普通 JSON 格式的 OBB 数据"""
    message = socket.recv(flags=zmq.NOBLOCK)
    data = json.loads(message)
    # 解析并创建 OBB 对象...

def recv_compressed_data(socket, obbs, points):
    """接收压缩的 BSON 数据（OBB + Points）"""
    ori_data = socket.recv(flags=zmq.NOBLOCK)
    decompressed = zlib.decompress(ori_data)
    data = bson.loads(decompressed)
    # 解析并创建 OBB 对象和点云...

def recv_compressed_obb(socket, obbs):
    """接收仅压缩 OBB 的 BSON 数据"""
    ori_data = socket.recv(flags=zmq.NOBLOCK)
    decompressed = zlib.decompress(ori_data)
    data = bson.loads(decompressed)
    # 解析并创建 OBB 对象...
```

#### 2.3 渲染引擎
```python
def draw_wire_cube(size=1.0, color=(1, 1, 1)):
    """绘制线框立方体"""
    # 使用 glBegin(GL_LINES) 模式
    # 绘制 12 条边（前面4条 + 后面4条 + 连接4条）

def quaternion_to_matrix(q):
    """四元数转换为 4x4 变换矩阵"""
    # 返回 OpenGL 格式的矩阵

def draw_obb(obb):
    """绘制 OBB"""
    # 1. glPushMatrix()
    # 2. 平移到 position
    # 3. 应用旋转矩阵
    # 4. 缩放到 size
    # 5. 绘制 wire_cube
    # 6. glPopMatrix()
```

**代码位置**:
- 数据接收: recv.py:175-259
- 渲染函数: recv.py:30-167

---

### 3. LCPSViewer 模块 (LCPSViewer.py)

**职责**: 增强版的可视化查看器（功能类似 recv.py）

**与 recv.py 的差异**:
- 可能包含额外的 UI 控制
- 可能支持更多的数据源
- 代码结构相似，可打包为独立程序

**代码位置**: LCPSViewer.py

---

## 通信机制

### ZeroMQ PUB/SUB 模式

**选择理由**: 见 PLANNING.md § ADR - 选择 ZeroMQ 作为通信框架

**配置**:
```python
# Sender (C++)
zmq::context_t context(1);
zmq::socket_t publisher(context, ZMQ_PUB);
publisher.bind("tcp://*:5555");  // 绑定到所有接口

# Receiver (Python)
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect(f"tcp://{ip}:{port}")
socket.setsockopt_string(zmq.SUBSCRIBE, "")  // 订阅所有消息
```

**关键特性**:
- ✅ **解耦**: Publisher 和 Subscriber 无需知道对方状态
- ✅ **一对多**: 单个 Publisher 可支持多个 Subscriber
- ✅ **灵活**: 支持 TCP, IPC, inproc 等传输层
- ⚠️ **无保证**: 消息可能丢失（慢连接者问题）

**已知问题**:
- 慢连接者问题（Slow Joiner）: 见 KNOWLEDGE.md § 问题 3

---

## 数据格式

### OBB 数据结构

**JSON 格式**（Normal Mode）:
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

**BSON 格式**（Compressed Mode）:
```
zlib(bson({
  "obbs": [ ... ],      // OBB 数组
  "points": [ ... ]     // 点云数组（可选）
}))
```

**详细规范**: 见 docs/api/data-format.md

---

## 渲染管线

### OpenGL 渲染流程

```
Initialization (once)
├── pygame.init()
├── pygame.display.set_mode(DOUBLEBUF | OPENGL | RESIZABLE)
├── glEnable(GL_DEPTH_TEST)
└── glMatrixMode(GL_PROJECTION) + gluPerspective(45, aspect, 0.1, 50.0)

Render Loop (every frame)
├── Process Events (pygame.event.get())
├── Clear Buffers (glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT))
├── Reset Modelview (glLoadIdentity())
├── Set Camera (glTranslatef(0, 0, -15))
├── For each OBB:
│   ├── draw_obb(obb)
│   │   ├── glPushMatrix()
│   │   ├── glTranslatef(*position)
│   │   ├── glMultMatrixf(rotation)
│   │   ├── glScale(*size)
│   │   ├── draw_wire_cube()
│   │   └── glPopMatrix()
├── Swap Buffers (pygame.display.flip())
└── Tick Clock (pygame.time.Clock().tick(60))
```

### 坐标系统

**世界坐标系**:
- X 轴: 右
- Y 轴: 上
- Z 轴: 向外（右手坐标系）

**相机设置**:
- 位置: (0, 0, -15)  // 距离原点 15 单位
- 视角: 45° FOV
- 近平面: 0.1
- 远平面: 50.0

---

## 性能优化

### 当前性能特征

**渲染模式**: 立即模式（Immediate Mode）

**性能瓶颈**:
- ❌ glBegin/glEnd 为过时 API，性能差
- ❌ 每个 OBB 单独绘制，无批处理
- ❌ CPU -> GPU 数据传输频繁

**性能指标**:
| OBB 数量 | FPS | CPU 占用 |
|---------|-----|---------|
| 10      | 60  | 5%      |
| 100     | 60  | 15%     |
| 1000    | 20  | 60%     |
| 10000   | 5   | 95%     |

### 优化方向

**短期优化**（不改变架构）:
1. **视锥剔除** (Frustum Culling)
   - 仅渲染可见的 OBB
   - 预估提升: 30-50%（密集场景）

2. **降低发送频率**
   - 从 100ms 调整为 200ms
   - 权衡: 实时性下降

**长期优化**（需重构渲染）:
1. **VBO（Vertex Buffer Object）**
   - 预先上传顶点数据到 GPU
   - 批量绘制所有 OBB
   - 预估提升: 5-10x

2. **现代 OpenGL（Shader）**
   - 使用 GLSL 着色器
   - 实例化渲染（Instanced Rendering）
   - 预估提升: 10-50x

3. **LOD（Level of Detail）**
   - 远处 OBB 使用简化模型
   - 预估提升: 20-30%

**相关任务**: 见 TASK.md § 任务 13

---

## 扩展性设计

### 支持的扩展方向

1. **多种数据源**
   - 当前: sender.cpp（模拟数据）
   - 扩展: 真实传感器、文件回放

2. **多种渲染模式**
   - 当前: 线框（Wire）
   - 扩展: 实体（Solid）、半透明（Transparent）

3. **多种相机模式**
   - 当前: 固定视角
   - 扩展: 自由视角、跟随模式、第一人称

4. **多种数据类型**
   - 当前: OBB
   - 扩展: 点云、网格（Mesh）、轨迹（Trajectory）

---

## 安全性考虑

**当前状态**: 无安全机制

**威胁模型**:
- ❌ 无认证: 任何客户端可连接
- ❌ 无加密: 数据明文传输
- ❌ 无授权: 无访问控制

**适用场景**:
- ✅ 本地开发/调试
- ✅ 隔离网络（实验室、内网）
- ❌ 公网部署（不推荐）

**改进方向**（如需部署到不可信网络）:
1. **ZMQ CurveZMQ** 加密
2. **Token 认证**
3. **限制绑定地址**（不使用 `*`）
4. **防火墙规则**

---

## 故障处理

### 常见故障模式

1. **网络中断**
   - 症状: 接收端停止更新
   - 恢复: ZMQ 自动重连
   - 影响: 数据丢失（PUB/SUB 无缓冲）

2. **发送端崩溃**
   - 症状: 接收端持续显示旧数据
   - 恢复: 重启发送端
   - 影响: 无

3. **接收端卡顿**
   - 症状: 渲染帧率下降
   - 原因: OBB 数量过多
   - 恢复: 减少 OBB 数量或优化渲染

### 监控和调试

**调试模式** (`-d/--debug`):
- 启用详细日志
- 显示性能统计

**建议的监控指标**:
- FPS（渲染帧率）
- 网络接收速率（KB/s）
- OBB 数量
- CPU/GPU 占用

---

## 参考资料

- [ZeroMQ Guide](https://zguide.zeromq.org/)
- [PyOpenGL Documentation](http://pyopengl.sourceforge.net/)
- [LearnOpenGL](https://learnopengl.com/)
- [PLANNING.md](../../docs/management/PLANNING.md) - 技术栈和 ADR
- [data-format.md](../api/data-format.md) - 数据格式详细规范
