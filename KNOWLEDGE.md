# OBBDemo 知识库

**最后更新**: 2025-12-20

本文档是项目的知识中心，索引所有架构决策、文档、设计模式和已知问题。

---

## 📚 文档索引

### 管理层文档（根目录/docs/management/）

| 主题 | 文档路径 | 说明 | 优先级 | 最后更新 |
|------|---------|------|--------|---------|
| 项目规划 | docs/management/PLANNING.md | 技术架构、开发标准、ADR | 高 | 2025-12-20 |
| 任务追踪 | docs/management/TASK.md | 任务状态、功能路线图 | 高 | 2025-12-20 |
| 会话上下文 | docs/management/CONTEXT.md | Git 状态、工作焦点（由 /wf_11_commit 管理）| 中 | - |

### 技术层文档（docs/）

| 主题 | 文档路径 | 说明 | 优先级 | 最后更新 |
|------|---------|------|--------|---------|
| 系统架构 | docs/architecture/system-design.md | 整体架构、模块关系、数据流 | 高 | 2025-12-20 |
| 数据格式 | docs/api/data-format.md | OBB 数据结构、ZMQ 消息格式 | 高 | 2025-12-20 |
| 开发环境 | docs/development/setup.md | 环境配置、依赖安装、编译 | 高 | 2025-12-20 |
| 快速开始 | docs/usage/quick-start.md | 安装、运行、基本使用 | 高 | 2025-12-20 |

### 任务-文档关联

| 任务类型 | 相关文档 |
|---------|---------|
| 添加新依赖 | docs/management/PLANNING.md § 技术栈, docs/development/setup.md |
| 修改数据格式 | docs/api/data-format.md, docs/architecture/system-design.md |
| 性能优化 | docs/management/PLANNING.md § 性能考量 |
| 部署项目 | docs/usage/quick-start.md, docs/development/setup.md |

---

## 🗂️ 架构决策记录 (ADR)

### ADR 索引

| 日期 | 标题 | 文档 | 状态 |
|------|------|------|------|
| 2025-12-20 | 选择 ZeroMQ 作为通信框架 | PLANNING.md § ADR | 已采纳 |
| 2025-12-20 | 使用 PyOpenGL 而非其他 3D 库 | PLANNING.md § ADR | 已采纳 |
| 2025-12-20 | 支持压缩模式 | PLANNING.md § ADR | 已采纳 |

### ADR 摘要

#### ADR 2025-12-20: 选择 ZeroMQ 作为通信框架

**核心决策**: 使用 ZeroMQ PUB/SUB 模式而非 gRPC、ROS 或原生 Socket

**关键理由**:
- 跨语言支持（C++ ↔ Python）
- 无服务器架构（无中心化 broker）
- 低延迟、简单易用

**权衡**:
- ✅ 适合演示和调试场景
- ❌ 无内置服务发现和持久化（可接受）

**详细文档**: PLANNING.md § ADR

---

#### ADR 2025-12-20: 使用 PyOpenGL 而非其他 3D 库

**核心决策**: 使用 PyOpenGL + Pygame 而非 Matplotlib 3D、VTK、Three.js

**关键理由**:
- 直接使用 OpenGL，性能高
- 完全控制渲染流程
- 轻量，与 Pygame 集成良好

**权衡**:
- ❌ 需手动实现相机控制、着色器
- ✅ 线框渲染场景简单，手动实现成本可控

**详细文档**: PLANNING.md § ADR

---

#### ADR 2025-12-20: 支持压缩模式

**核心决策**: 实现三种数据模式（normal, compressed, compressed_obb）

**关键理由**:
- zlib 压缩可减少 60-80% 数据量
- 用户可根据网络条件选择模式
- normal 模式保持向后兼容

**实现**:
- `recv_obb()`: 原始 JSON
- `recv_compressed_data()`: zlib + BSON (OBB + 点云)
- `recv_compressed_obb()`: 仅压缩 OBB

**详细文档**: PLANNING.md § ADR

---

## 🎨 设计模式和最佳实践

### 数据传输模式

**模式**: ZeroMQ PUB/SUB（发布-订阅）

**应用场景**:
- sender.cpp 作为 Publisher
- recv.py 作为 Subscriber
- 支持一对多广播

**代码示例**:
```cpp
// Publisher (sender.cpp)
zmq::context_t context(1);
zmq::socket_t publisher(context, ZMQ_PUB);
publisher.bind("tcp://*:5555");
publisher.send(zmq_msg, zmq::send_flags::dontwait);
```

```python
# Subscriber (recv.py)
context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect(f"tcp://{ip}:{port}")
socket.setsockopt_string(zmq.SUBSCRIBE, "")
message = socket.recv(flags=zmq.NOBLOCK)
```

**最佳实践**:
- ✅ 使用 `NOBLOCK` 模式避免阻塞渲染
- ✅ Publisher 使用 `bind()`，Subscriber 使用 `connect()`
- ✅ 设置合理的发送频率（当前 100ms）

**相关文档**: docs/architecture/system-design.md

---

### 3D 渲染模式

**模式**: 立即模式渲染（Immediate Mode）

**实现**:
```python
def draw_wire_cube(size=1.0, color=(1, 1, 1)):
    glBegin(GL_LINES)
    glColor3f(*color)
    # 绘制顶点...
    glEnd()
```

**适用场景**:
- 简单的线框渲染
- OBB 数量 < 1000

**已知限制**:
- ❌ 性能瓶颈：大量 OBB（>1000）时帧率下降
- ❌ 使用过时的 OpenGL API（glBegin/glEnd）

**优化方向** (见 TASK.md § 任务 13):
- 改用 VBO (Vertex Buffer Object)
- 批量绘制
- 视锥剔除

**相关文档**: docs/architecture/system-design.md

---

### 数据序列化模式

**模式**: JSON 序列化（C++）+ JSON/BSON 反序列化（Python）

**C++ 端**:
```cpp
// nlohmann/json
json j;
j.push_back({{"type", obb.type}, {"position", obb.position}, ...});
std::string msg = j.dump();
```

**Python 端**:
```python
# Normal mode
data = json.loads(message)

# Compressed mode
decompressed = zlib.decompress(ori_data)
data = bson.loads(decompressed)
```

**权衡**:
- ✅ JSON: 人类可读，调试方便
- ❌ JSON: 数据量大
- ✅ BSON + zlib: 数据量小（60-80% 压缩率）
- ❌ BSON + zlib: CPU 开销增加

**相关文档**: docs/api/data-format.md

---

## ❓ 已知问题和解决方案

### 问题 1: 大量 OBB 时帧率下降 ⚠️

**症状**:
- OBB 数量 > 1000 时，FPS 降至 10 以下
- CPU 占用高

**根本原因**:
- 使用立即模式渲染（`glBegin`/`glEnd`）
- 每个 OBB 独立绘制，无批量优化

**临时解决方案**:
- 限制 OBB 数量
- 使用压缩模式减少网络延迟

**长期解决方案**（见 TASK.md § 任务 13）:
- 改用 VBO (Vertex Buffer Object)
- 实现视锥剔除
- 批量绘制

**相关文档**: PLANNING.md § 性能考量

---

### 问题 2: Windows 下 PyInstaller 打包失败 🔧

**症状**:
- `pyinstaller LCPSViewer.spec` 报错：找不到 OpenGL.dll

**根本原因**:
- PyOpenGL 依赖系统 OpenGL 库
- PyInstaller 未自动打包 OpenGL.dll

**解决方案**:
1. 在 LCPSViewer.spec 中添加 hidden imports:
   ```python
   hiddenimports=['OpenGL.GL', 'OpenGL.GLU', 'pygame']
   ```

2. 手动复制 OpenGL.dll 到 dist/ 目录

3. 使用 `--collect-all PyOpenGL` 参数:
   ```bash
   pyinstaller --collect-all PyOpenGL LCPSViewer.spec
   ```

**相关资源**:
- [PyOpenGL FAQ](http://pyopengl.sourceforge.net/documentation/faq.html)
- [PyInstaller Manual](https://pyinstaller.org/en/stable/)

**相关文档**: docs/development/setup.md § 打包

---

### 问题 3: ZMQ 消息丢失 ⚠️

**症状**:
- Receiver 偶尔接收不到消息
- 数据流不连续

**根本原因**:
- PUB/SUB 模式的"慢连接者"问题
- Subscriber 连接后，Publisher 可能已发送了部分消息

**解决方案**:
1. **临时方案**: Publisher 启动后等待 1 秒再发送数据
   ```cpp
   publisher.bind("tcp://*:5555");
   std::this_thread::sleep_for(std::chrono::seconds(1)); // 等待连接
   ```

2. **推荐方案**: 使用 REQ/REP 模式实现握手协议
   - Subscriber 连接后发送 READY 消息
   - Publisher 收到后开始发送数据

3. **备选方案**: 改用 PUSH/PULL 模式（但失去一对多能力）

**相关资源**:
- [ZMQ Guide - Slow Joiner Problem](https://zguide.zeromq.org/docs/chapter2/#Slow-Subscriber-Detection)

**相关文档**: docs/architecture/system-design.md § 通信机制

---

## 🔧 技术栈参考

### Python 生态

| 库 | 用途 | 官方文档 | 版本要求 |
|---|------|---------|---------|
| pyzmq | ZeroMQ 绑定 | https://pyzmq.readthedocs.io/ | latest |
| pygame | 窗口管理 | https://www.pygame.org/docs/ | latest |
| PyOpenGL | OpenGL 绑定 | http://pyopengl.sourceforge.net/ | latest |
| numpy | 数值计算 | https://numpy.org/doc/ | latest |

### C++ 生态

| 库 | 用途 | 官方文档 | 版本要求 |
|---|------|---------|---------|
| libzmq | ZeroMQ 核心 | https://zeromq.org/ | 3+ |
| cppzmq | C++ 头文件 | https://github.com/zeromq/cppzmq | latest |
| nlohmann/json | JSON 库 | https://json.nlohmann.me/ | 3+ |

---

## 📖 学习资源

### ZeroMQ

- **官方指南**: [ZGuide](https://zguide.zeromq.org/)
- **API 文档**: [ZMQ API Reference](https://zeromq.org/socket-api/)
- **推荐章节**:
  - Chapter 2: Sockets and Patterns
  - Chapter 4: Reliable Request-Reply

### OpenGL

- **入门教程**: [LearnOpenGL](https://learnopengl.com/)
- **PyOpenGL 文档**: [PyOpenGL Programming Guide](http://pyopengl.sourceforge.net/documentation/)
- **推荐章节**:
  - Getting Started: Hello Triangle
  - Coordinate Systems
  - Transformations

### 数据压缩

- **zlib 文档**: [zlib Manual](https://www.zlib.net/manual.html)
- **BSON 规范**: [BSON Specification](http://bsonspec.org/)

---

## 🔄 文档维护

### 更新频率

| 章节 | 更新时机 |
|------|---------|
| **文档索引** | 新增技术文档时 |
| **ADR 索引** | 做出重大技术决策时 |
| **设计模式** | 发现新的最佳实践时 |
| **已知问题** | 发现或解决问题时 |
| **学习资源** | 发现有价值的资源时 |

### 维护规则

- ✅ 每次添加技术文档时，更新文档索引
- ✅ 重大架构决策后，添加 ADR 摘要
- ✅ 解决问题后，更新已知问题章节
- ✅ 保持 KNOWLEDGE.md 行数 < 200（仅索引和摘要）

---

**文档管理**: 此文档遵循 SSOT (Single Source of Truth) 原则
- ✅ 索引和指针：存储在 KNOWLEDGE.md
- ✅ 详细内容：存储在对应的技术文档中
- ❌ 禁止重复：避免在多处维护相同内容
