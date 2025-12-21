# OBBDemo 知识库

**最后更新**: 2025-12-21

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
| 部署指南 | docs/deployment/binary-release.md | PyInstaller 打包、二进制发布 | 中 | 2025-12-21 |

### 任务-文档关联

| 任务类型 | 相关文档 |
|---------|---------|
| 添加新依赖 | docs/management/PLANNING.md § 技术栈, docs/development/setup.md |
| 修改数据格式 | docs/api/data-format.md, docs/architecture/system-design.md |
| 性能优化 | docs/management/PLANNING.md § 性能考量 |
| 部署项目 | docs/deployment/binary-release.md, docs/usage/quick-start.md |
| 故障排查 | KNOWLEDGE.md § 常见问题, docs/development/setup.md |

---

## 🗂️ 架构决策记录 (ADR)

### ADR 索引

| 日期 | 标题 | 文档 | 状态 |
|------|------|------|------|
| 2025-12-20 | 选择 ZeroMQ 作为通信框架 | PLANNING.md § ADR | 已采纳 |
| 2025-12-20 | 使用 PyOpenGL 而非其他 3D 库 | PLANNING.md § ADR | 已采纳 |
| 2025-12-20 | 支持压缩模式 | PLANNING.md § ADR | 已采纳 |
| 2025-12-21 | 使用 Git Submodule 管理 cppzmq 依赖 | PLANNING.md § ADR | 已采纳 |

### ADR 摘要

#### ADR 2025-12-20: 选择 ZeroMQ 作为通信框架

**决策**: 使用 ZeroMQ PUB/SUB 而非 gRPC、ROS 或原生 Socket

**理由**: 跨语言支持、无服务器架构、低延迟、简单易用

**权衡**: ✅ 适合演示调试场景 | ❌ 无内置服务发现（可接受）

**详细文档**: PLANNING.md § ADR

---

#### ADR 2025-12-20: 使用 PyOpenGL 而非其他 3D 库

**决策**: 使用 PyOpenGL + Pygame 而非 Matplotlib 3D、VTK、Three.js

**理由**: 直接使用 OpenGL 性能高、完全控制渲染流程、轻量

**权衡**: ❌ 需手动实现相机控制 | ✅ 线框渲染场景简单，成本可控

**详细文档**: PLANNING.md § ADR

---

#### ADR 2025-12-20: 支持压缩模式

**决策**: 实现三种数据模式（normal, compressed, compressed_obb）

**理由**: zlib 压缩可减少 60-80% 数据量，用户可根据网络条件选择

**详细文档**: PLANNING.md § ADR

---

#### ADR 2025-12-21: 文件管理和依赖现代化

**决策**: 恢复 LCPSViewer.py、清理冗余文件、采用 uv 依赖管理

**理由**: ✅ 恢复项目打包功能 | ✅ 采用行业标准 | ✅ 简化依赖管理

**验证**: ✅ 可执行文件打包成功 (40MB) | ✅ 所有依赖正确导入

**详细文档**: PLANNING.md § ADR

---

#### ADR 2025-12-21: 使用 Git Submodule 管理 cppzmq 依赖

**决策**: 使用 Git Submodule 管理 cppzmq，而非 CMake FetchContent 或手动安装

**理由**: ✅ 版本明确 | ✅ 协作友好 | ✅ 无需系统安装 | ✅ 离线可用

**权衡**: ❌ 需额外 submodule update 命令 | ✅ 比手动管理 tar.gz 更规范

**备选方案**: CMake FetchContent (每次 clean build 需下载)、系统安装 (版本不可控)

**详细文档**: PLANNING.md § ADR

---

## 🎨 设计模式和最佳实践

| 模式 | 说明 | 详细文档 |
|------|------|---------|
| **ZeroMQ PUB/SUB** | 发布-订阅模式，一对多广播 | docs/architecture/system-design.md § 通信机制 |
| **立即模式渲染** | OpenGL 立即模式，适合简单线框（<1000 OBB）| docs/architecture/system-design.md § 渲染流程 |
| **JSON/BSON 序列化** | 支持普通和压缩模式，60-80% 压缩率 | docs/api/data-format.md § 序列化方式 |

---

## ❓ 已知问题和解决方案

| 问题 | 状态 | 严重性 | 解决方案文档 |
|------|------|--------|-------------|
| **大量 OBB 时帧率下降** | ⚠️ 已知 | 中 | PLANNING.md § 性能考量, TASK.md § 任务 13 |
| **Windows 下 PyInstaller 打包** | ✅ 已解决 | 低 | docs/development/setup.md § 打包说明 |
| **ZMQ 消息丢失（慢连接者）** | ⚠️ 已知 | 低 | docs/architecture/system-design.md § 通信机制 |
| **Git 仓库体积过大** | ✅ 已解决 | 低 | .gitignore 规则已添加 |

**详细解决方案**: 见对应文档或 TASK.md 中的相关任务

### 常见问题 (FAQ)

**Q1: 如何快速验证 ZMQ 通信是否正常？**
- 先启动 sender: `./sender`
- 再启动 receiver: `python3 recv.py -a localhost:5555 -m n`
- 检查是否有 OBB 数据显示在窗口中

**Q2: 为什么接收器显示窗口是黑屏？**
- 检查 sender 是否正在发送数据
- 确认端口和 IP 地址是否正确（默认 localhost:5555）
- 使用 `-d` 调试模式查看详细日志

**Q3: 如何切换到压缩模式？**
- 使用 `-m compressed` 参数: `python3 recv.py -m compressed`
- Sender 端需要支持压缩模式发送

**Q4: OpenGL 相关错误如何解决？**
- Ubuntu: `sudo apt-get install python3-opengl`
- Windows: 确保安装了图形驱动
- 检查 OpenGL 版本: 运行 `glxinfo | grep OpenGL`（Linux）

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

| 主题 | 推荐资源 | 重点章节 |
|------|---------|---------|
| **ZeroMQ** | [ZGuide](https://zguide.zeromq.org/) | Ch2: Sockets and Patterns |
| **OpenGL** | [LearnOpenGL](https://learnopengl.com/) | Coordinate Systems, Transformations |
| **PyOpenGL** | [PyOpenGL Guide](http://pyopengl.sourceforge.net/documentation/) | Getting Started |

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
