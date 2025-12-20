# OBBDemo

基于 ZeroMQ 的实时 3D 数据可视化系统，用于演示 OBB (Oriented Bounding Box) 数据的传输和渲染。

## 特性

- **实时通信**: 使用 ZeroMQ PUB/SUB 模式实现低延迟数据传输
- **跨语言**: C++ 发送端 + Python 接收端
- **3D 可视化**: 基于 PyOpenGL 的实时 3D 渲染
- **数据压缩**: 支持 zlib + BSON 压缩，节省 60-80% 带宽
- **跨平台**: 支持 Linux 和 Windows

## 快速开始

### 安装依赖

**Python 接收端**:
```bash
pip install pyzmq pygame PyOpenGL numpy bson
```

**C++ 发送端**:
```bash
# Ubuntu
sudo apt-get install libzmq3-dev nlohmann-json3-dev
```

详细安装指南见 [开发环境配置](docs/development/setup.md)。

### 运行示例

**Step 1: 启动发送端**
```bash
g++ -std=c++11 sender.cpp -o sender -lzmq
./sender
```

**Step 2: 启动接收端**
```bash
python3 recv.py -a localhost:5555 -m n
```

完整的快速开始指南见 [快速开始](docs/usage/quick-start.md)。

## 项目文档

### 管理文档
- [项目规划](docs/management/PLANNING.md) - 技术架构、开发标准和架构决策记录
- [任务追踪](docs/management/TASK.md) - 功能路线图和任务状态
- [知识库](KNOWLEDGE.md) - 文档索引、设计模式和已知问题

### 技术文档
- [系统架构](docs/architecture/system-design.md) - 整体架构、模块关系和数据流
- [数据格式](docs/api/data-format.md) - OBB 数据结构和 ZMQ 消息格式
- [开发指南](docs/development/setup.md) - 环境配置、依赖安装和构建
- [用户手册](docs/usage/quick-start.md) - 安装、运行和基本使用

## 架构概览

```
┌─────────────────┐         ZMQ PUB/SUB          ┌──────────────────┐
│  Sender (C++)   │ ──────── tcp://5555 ────────>│  Receiver (Py)   │
│                 │                               │                  │
│ - 生成 OBB 数据  │                               │ - 接收 OBB 数据   │
│ - JSON 序列化   │                               │ - 解析数据       │
│ - ZMQ 发布      │                               │ - OpenGL 渲染    │
└─────────────────┘                               └──────────────────┘
```

详细的系统设计见 [系统架构文档](docs/architecture/system-design.md)。

## 命令行参数

### recv.py

```bash
python3 recv.py -a <IP:PORT> [-m <MODE>] [-d]
```

| 参数 | 说明 | 示例 |
|------|------|------|
| `-a / --address` | 连接地址（必需）| `localhost:5555` |
| `-m / --mode` | 数据模式（可选）| `n` (normal) 或 `c` (compressed) |
| `-d / --debug` | 调试模式（可选）| - |

## 技术栈

| 组件 | 技术 |
|------|------|
| **通信** | ZeroMQ (pyzmq / libzmq) |
| **序列化** | JSON (nlohmann/json), BSON |
| **压缩** | zlib |
| **渲染** | PyOpenGL, Pygame |
| **构建** | CMake, PyInstaller |

## 性能

| OBB 数量 | FPS | 数据大小 (Normal) | 数据大小 (Compressed) |
|---------|-----|------------------|---------------------|
| 10      | 60  | ~1 KB            | ~0.3 KB             |
| 100     | 60  | ~10 KB           | ~2-4 KB             |
| 1000    | 20  | ~100 KB          | ~20-30 KB           |

## 开发

### 构建 C++ 发送端

```bash
mkdir build && cd build
cmake ..
make
```

### 打包 Python 接收端

```bash
pyinstaller LCPSViewer.spec
```

输出目录: `dist/LCPSViewer`

## 贡献

查看 [TASK.md](docs/management/TASK.md) 了解计划功能和待办任务。

## License

MIT License

## 相关资源

- [ZeroMQ 官方指南](https://zguide.zeromq.org/)
- [PyOpenGL 文档](http://pyopengl.sourceforge.net/)
- [LearnOpenGL 教程](https://learnopengl.com/)
