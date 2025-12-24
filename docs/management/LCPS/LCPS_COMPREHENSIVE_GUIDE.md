# LCPS（防打保龄系统）完整实现指南

**版本**: 1.0
**最后更新**: 2025-12-08
**系统**: 基于实时LiDAR检测的起升防打保龄系统

---

# 目录

1. [系统概述](#系统概述)
2. [核心架构](#核心架构)
3. [关键模块详解](#关键模块详解)
4. [数据流与处理流程](#数据流与处理流程)
5. [状态机与生命周期](#状态机与生命周期)
6. [安全监控机制](#安全监控机制)
7. [配置与参数](#配置与参数)
8. [集成点与接口](#集成点与接口)

---

# Reference
* [RTG基本介绍](../../basic/RTG.md)

# 系统概述

## 什么是LCPS？

港口领域中，LCPS往往是Load Collision Prevention System，负载防碰撞系统（业内往往叫做防打保龄）的缩写
。不仅仅包括集装箱作业时下降、起升时 的防碰撞，还包括小车方向防碰撞、大车防撞防碰撞等。
但是在Autane系统中， 其LCPS仅表示Land/Lift Load Collision Prevention System，保护起升、下降过程自动化作业的安全。

该套方案是一套基于**实时LiDAR检测**的防碰撞保护系统，专门为集装箱起升作业设计。其核心目的是：

* **防止集装箱与周围障碍物碰撞** - 通过实时检测障碍物并计算安全距离
* **保护吊具（Spreader）或者吊具所带集装箱装置** - 在起升过程中动态规避障碍（主要是集装箱）
* **支持多种作业模式** - 适应码头、卡车等多种场景

目前硬件上为4个面阵激光Livox AVIA（70 * 70度），成矩形中心分布与小车（即司机驾驶室）下方，对称安装。
左右距离3.4米，前后距离2.8米。另外，对角对称2个16线激光（禾赛或者robosense），扫描方向平行于小车前
后运行方向。设备安装高度一般在20米左右，面阵激光向下方扫描。

思路就是通过4（面阵激光） + 2(16线激光)六个激光全面覆盖正下方的堆场场景/集卡侧场景，基于外参校准、
合并后的点云以及集装箱的平面假设等，构建障碍物（使用OBB表示）。同时，从吊具位姿检测系统会以10hz的
频率上报吊具位姿，基于吊具位姿和吊具几何尺寸（可动态伸缩为20尺、40尺长度）可以构建吊具OBB。利用
吊具OBB和障碍物OBB的几何关系判断是否发生碰撞来进行碰撞检测。当然，考虑到吊具的上下运动以及其速度，
OBB按照速度以及速度方向会动态扩大，扩大的基础是利用速度、加速度获取距离的方式来进行。

另外，在小车（RTG 司机驾驶舱的另一种说法），位于RTG的大梁上，可以从大梁一侧运行到另一侧。

目前LCPS存在以下问题

1. 由于整个系统依赖于实时扫描的结果，而非建图结果。存在两个问题:
问题1: 有可能障碍物被吊具自身遮挡，从而点云缺失，导致构建障碍物OBB缺失，造成碰撞。
问题2: 由于基于实时结果，导致检测受限。

它不仅是简单的测距停车，而是一个在高噪音、大惯量、柔性连接环境下运行的实时决策系统。

核心矛盾（开发难点）

1. 惯性 vs 实时：吊具重达数十吨，刹车距离随速度非线性变化。静态包围盒在高速下会导致撞车，在低速下会导致误停。
2. 噪点 vs 可用性：港口环境充满干扰（雨雾、钢丝绳、大梁反光）。一次误报即会导致自动化中断，一次漏报即会导致事故。

3. 柔性 vs 精度：吊具是软连接，存在摇摆；大车轨道不平导致整机震动。传感器数据（激光雷达）与执行机构（PLC编码器）之间永远存在动态偏差。

## 工作原理

```
LiDAR实时感知 → PlanarCntrDetector识别 → LCPS碰撞检测 → LCPSStateMachine管理 → DetectorKicker监控
     ↓              ↓                      ↓                ↓                    ↓
  点云数据      障碍物特征提取      安全判决       生命周期控制        外部系统协调
```

## 关键特征

| 特征 | 说明 |
|------|------|
| **实时性** | 每帧点云处理延迟 < 100ms |
| **多源融合** | 位置融合（编码器/GNSS/SLAM） |
| **场景自适应** | 支持码头、卡车等多种场景 |
| **故障容错** | 异常状态下安全降级 |
| **监控完备** | 看门狗、状态追踪、异常处理 |

---

# 核心架构

## 四层系统架构

```
┌─────────────────────────────────────────┐
│    LCPSStateMachine (状态管理层)        │ ← 生命周期控制、状态转换
└────────────────┬────────────────────────┘
                 │
        ┌────────┴────────┐
        ↓                 ↓
┌──────────────┐  ┌──────────────────┐
│    LCPS      │  │ PlanarCntrDetector│ ← 实时障碍识别
│   (决策层)   │  │   (感知层)       │
└──┬───────┬──┘  └────────┬─────────┘
   │       │               │
   │   ┌───┴───────────────┤
   │   ↓                   ↓
   │  ◆─────────────────────◆
   │  障碍物信息、相对位置、碰撞判决
   │
   ↓
┌──────────────────────┐
│  DetectorKicker      │ ← 监控和协调
│  (集成与监控层)      │   - LCPS状态监控
│                      │   - 其他传感器管理
│                      │   - 安全联动
└──────────────────────┘
```

## 主要组件

### 1. **LCPS 类** (`src/service/LCPS/LCPS.hpp`)

* **角色**: 大脑
* **职责**: 核心碰撞检测和安全决策, 接收障碍物，结合吊具实时速度和位置，计算动态碰撞风险，向 PLC 发送控制指令。
* **主要方法**:
  * `processFrame()` - 每帧处理入口
  * `collisionCheck()` - 碰撞检测算法
  * `safetyDecision()` - 安全决策逻辑
  * `onObstacleReady()` - 接收障碍物信息
  * `onPoseReady()` - 接收位置信息
* **状态管理**:
  * 内部多线程运行
  * 看门狗心跳 (`watchdogHeartThread`)
  * 异常处理与恢复

### 2. **PlanarCntrDetector 类** (`src/detector/perception/planarCntrDetector/PlanarCntrDetector.hpp`)

* **角色**: 眼睛
* **职责**: 处理激光雷达点云，滤除背景（吊具、钢丝绳、雨雾），分割并聚类出障碍物 (Obstacle OBB)。
* **处理流程**:
     1. 点云预处理 (`filterCloud`) - 去除干扰、异常值
     2. 分类 (`classifyCloud`) - 分离地面、保龄、障碍物
     3. 分割 (`segmentToLines`) - 分割成线特征
     4. 转换为OBB (`cloudToBB`) - 生成有向包围盒
     5. 自适应滤波 (`filterAdaptively`) - 根据场景优化
* **输出**: `ObstaclePtr` 列表（带位置、大小、置信度）

### 3. **LCPSStateMachine 类** (`src/app/LCPSStateMachine.cpp`)

* **角色**: 开关
* **职责**: LCPS生命周期和状态管理, 决定 LCPS 什么时候该启动，什么时候该休眠。防止在非作业区域（如过街跑车时）误触发防撞。
* **状态集合**:

     ```
     UNINITIALIZED → NON_OPERATION ↔ IN_OPERATION → EXCEPTION
     ```

* **关键方法**:
  * `startLiftLCPS()` - 启动起升防碰撞
  * `startLandLCPS()` - 启动落地防碰撞
  * `stopLCPS()` - 正常停止
  * `lifeCycleLogic()` - 生命周期主逻辑
  * `switchState()` - 状态转换处理

### 4. **DetectorKicker 类** (`src/service/DetectorKicker/DetectorKicker.cpp`)

* **职责**: LCPS监控和系统协调
* **监控职能**:
  * `operateLCPS()` - 监控LCPS运行状态
    * 检查VFS/PFS（下降信号）和VRS/PRS（上升信号）有效性
    * 验证LCPS与Spreader运动同步
    * 异常报警处理
  * `watchdogHeartThread()` - 定期心跳检测
* **协调职能**:
  * 启停其他传感器（THCP、LinearIT等）
  * 安全联动通知
  * 位置补偿（GNSS角度补偿）

---

# 关键模块详解

## 模块1: LCPS核心处理

### 类结构概览

```cpp
class LCPS {
public:
    // 生命周期
    int Init(...);
    int Close();
    int Reset();

    // 主处理
    void processFrame(...);        // 每帧处理
    void preProcessFrame(...);     // 预处理
    void envProcessFrame(...);     // 环境处理
    void processPreObsFrame(...);  // 预防碰撞处理

    // 安全决策
    void collisionCheck(...);      // 碰撞检测
    void safetyDecision(...);      // 安全决策
    void exceptionHandler(...);    // 异常处理

    // 信息接口
    void onObstacleReady(...);     // 障碍物回调
    void onPoseReady(...);         // 位置回调
    void onOdometryPoseReady(...); // 里程计位置回调
    void onSprSwingStatus(...);    // 吊具摇晃状态回调
};
```

### 处理流程详解

**`processFrame()` 核心逻辑** (Line 1851):

```
输入:
  - craneState      (起重机状态: 位置、速度、吊具状态)
  - mSrvState       (LCPS内部状态)
  - motionMode      (运动模式: LIFT/LAND)
  - sprPose         (吊具位姿)
  - sprTargetPose   (吊具目标位姿)

处理步骤:
1. 验证输入有效性
   └─ 检查起重机状态、位置有效性

2. 构建吊具边界框 (Spreader OBB)
   ├─ Upper Spreader OBB (上吊具)
   ├─ Lower Spreader OBB (下吊具)
   └─ Cntr OBB (集装箱)

3. 过滤障碍物列表
   ├─ 空间范围过滤
   ├─ 高度层过滤
   └─ 置信度过滤

4. 执行碰撞检测
   └─ collisionCheck(吊具位姿, 障碍物OBB)
      返回: 碰撞状态位图 (4方向: SAFE/FRONT/BACK/LEFT/RIGHT)

5. 安全决策
   └─ safetyDecision(运动模式, 碰撞状态)
      ├─ STOP: 完全停止
      ├─ WARNING: 降速警告
      └─ SAFE: 安全继续

6. 通知外部系统
   └─ notifyController()  (通知控制器)
   └─ notifyServer()      (通知TOS服务器)

输出:
  - 安全决策 (STOP/WARNING/SAFE)
  - 碰撞方向 (FRONT/BACK/LEFT/RIGHT)
  - 相对距离
```

**状态管理** (LCPS_SRV_STATE):

```cpp
struct LCPS_SRV_STATE {
    LCPS_CRANE_STATE    craneState;      // 当前起重机状态
    bool                bPosSet;         // 位置是否已设置
    bool                bWait;           // 是否等待就位
    bool                bWaitDone;       // 等待是否完成
    uint8_t             tReadyCnt;       // 就位计数
    bool                bLastTInPlace;   // 上次T是否就位
    uint8_t             sceneType;       // 场景类型 (CY/CYM/IT/ET)
    uint8_t             opsType;         // 操作类型 (LOAD/UNLOAD)
    bool                bMoveTrolleySwitch;  // 移动小车开关
    uint8_t             targetCntr;      // 目标集装箱号
    bool                bCheckColliAhead;    // 是否提前检查碰撞
};
```

### 1.3 核心逻辑

#### 动态包围盒（Dynamic Expansion）- 核心安全逻辑

这是 LCPS 的灵魂，也是最危险的参数调整区。

* 代码位置: LCPS::updateExpandSize
* 数学原理 (Why):
$$D_{stop} = \frac{v^2}{2a} + v \cdot t_{delay} + D_{safe}$$
静态包围盒在高速时刹不住，低速时效率低。
* 实现 (How): 根据 speed (吊具速度)，计算 stopDis。

```cpp
// LCPS.cpp 示例逻辑
float stopDis = 0.5 * (speed / mfSpreaderDeceleration) * speed + speed + 0.2;
// 根据速度分级调整膨胀系数
if (speed > 0.75) scale = FullSpeedScale;
else if (speed > 0.5) scale = HighSpeedScale;
// ...
```

* 危险警告: mfSpreaderDeceleration (减速度) 必须小于等于实际物理刹车能力。如果软件设为 1.0m/s²，而实际刹车只有 0.5m/s²，必然撞车。

另外，在非起升方向，基于小车前后方向制动距离，构建三级包围盒，基于制动距离，构建 Normal, Warning, Stop 三级 OBB。Stop Box: 紧急停止范围。Warning Box: 减速范围。

#### 重力补偿与坐标系 (Gravity Transform)

* 现象: 岸桥大梁有挠度，且作业时吊具会有 Pitch/Roll 倾斜。如果不处理，平坦的地面在雷达看来是斜坡，会被误判为障碍物。
* 代码: LCPS::detectPreColli 中的 mGravityTransform 。
* How: 使用 EuclidTransform 将点云校正到重力垂直方向。
* 注意: 在 service_config.yaml 中配置 gravity_transform 矩阵。

#### 多源定位融合 (Sensor Fusion)

* 问题: 编码器有累积误差，GPS 更新频率低。为了解决单一传感器误差，LCPS 实现了多源定位融合 (refinePosition)。

* 输入源:
  * Encoder: 编码器 (高频，但有累积误差)。
  * GNSS: 全球导航卫星系统 (绝对位置)。
  * SLAM: 激光定位 (相对精度高)。
* 融合逻辑 (posFusion):
  * 计算各传感器相对于基准位置 (StartPos) 的 Offset。
  * 计算各传感器 Offset 的统计特征 (均值、方差)。
  * 若方差 (stdVariance) 小于阈值，认为数据一致，进行加权融合。
  * 若方差过大，降级处理或报错。
  * 输出: 修正后的大车/小车位置 (pos) 及波动半径 (fluctuateRadius)。
* 代码: LCPS::refinePosition

#### 碰撞检测与安全决策 (Decision Making)

1. OBB 碰撞测试: collisionCheck 函数使用 IsBoxInBox 判定障碍物是否进入 Stop/Warning 框 。
2. 时序投票 (Safety Decision):

* 代码: LCPS::safetyDecision 。
* 逻辑: 维护一个容量为 5 的 Circular Buffer mCandiResultCb。
* 规则:
  * Stop 信号：只要窗口内 > 1 帧，立即 Stop（安全优先，响应快）。
  * Warning 信号：需要窗口内 > 50% 的帧数确认（防止误报闪烁）。
* 危险: 随意增大 Buffer 容量会增加系统延迟，导致刹车不及时。

### 关键参数配置

```yaml
LCPS:
  # 扩展参数 (吊具外扩尺寸, 用于安全边界)
  spr_expand_s: 0.3        # 前后方向外扩 (米)
  spr_expand_w: 0.25       # 左右方向外扩 (米)
  spr_expand_s_t: 0.5      # 集装箱前后外扩
  spr_expand_w_t: 0.5      # 集装箱左右外扩

  # 距离阈值
  colli_distance_thresh: 0.2    # 碰撞判决距离 (米)
  dual_cntr_safe_thresh: 0.05   # 双集装箱安全距离

  # 高度限制
  max_layer_height: 35.0        # 最大层高
  spr_safe_min_height: 2.0      # 吊具安全最低高度

  # LCPS特性
  enable_pre_obs_avoid: true        # 启用预防碰撞避让
  pre_obs_avoid_expand: 0.5         # 预防碰撞外扩
  obs_avoid_move_thresh: [0.1, 0.2]  # 避让移动阈值
  obs_avoid_min_gap: [0.5, 0.3]      # 避让最小间隙
```

## 模块2: PlanarCntrDetector点云处理

### 2.1 为什么点云处理如此繁琐？ (Pre-processing Pipeline)

在 PlanarCntrDetector.cpp 的 processFrame 中，你不会看到直接的检测，而是大量的 Filter。

* 多帧融合 (Merge Frames) mergeFrames
  * How: 维护一个 mvDataCb (Circular Buffer) 滑动窗口。
  * Why: 单帧激光雷达线束稀疏，容易漏检细小物体。多帧叠加能提高密度，但副作用是引入运动拖影（这也是为什么需要 timestamp 同步的原因）。
* 平面分割 (Plane Filtering) classifyCloud
  * How: 调用 PlaneFilter 将点云分为 Horizon (箱顶) 和 Vertical (箱壁/大梁)。
  * Why: 岸桥环境下，只有“横平竖直”的点是有意义的。斜率过大的点通常是噪点或干扰。

### 2.2 关键过滤逻辑 (危险代码区)

以下函数若改动不当，会导致严重的漏报或误报：

1. ROI 裁剪 (filterAABB):

* 基于 CraneStatus 提供的作业位置，动态生成感兴趣区域 (ROI)。
* 剔除 ROI 之外的所有点云。

1. 自身滤除 (Spreader Outlier) filterSprOutlier

* 逻辑：根据 sprPose (吊具位姿) 生成一个比实际吊具稍大的 Box，剔除 Box 内的点。
* 风险：如果 Box 设得太小，吊具自身会被当成障碍物（误报）；如果设得太大，会滤除紧贴吊具的集装箱（漏报，导致撞箱）。代码中 mLandHorizonSprOutlierExpand 等参数  必须严格校准。

1. 钢丝绳过滤 (Wire Filter) filterWire

* 逻辑：检测吊具上方特定区域的细长垂直特征。
* Why：钢丝绳在雷达里是噪点，不滤除会导致起升时误停。

1. 雨雾过滤 (Rain Filter) filterRain

* 逻辑：利用 intensity (反射强度) 和 RadiusOutlier (密度)。雨滴强度低且稀疏。
* 代码位置：initCommonFilter 中配置。

2.3 历史障碍物机制 (The Safety Net)
代码中大量出现 bHistoryObs 。
Why: 当雷达被遮挡、数据丢包或者检测算法在某一帧失效时，不能认为环境是空的。
How: 系统会保留上一帧的障碍物列表 (mObstacleInfoHistoryMap)，直到新的可靠数据到来。
注意: 在 LCPS::updateObsOBB 中，即使是历史障碍物，也会根据大车/小车的移动 delta 进行位置推算，保证其坐标在当前时刻是准确的 。

### 2.3 处理管线

```
LiDAR点云 (XYZI)
    ↓
1. 云分类 (classifyCloud)
   ├─ 地面点 (Ground)
   ├─ 吊具点 (Spreader)
   └─ 障碍物点 (Obstacle)
    ↓
2. 预处理滤波 (filterCloud)
   ├─ 条件滤波 (removeNaN, 范围限制)
   ├─ 统计滤波 (去异常值)
   ├─ 体素滤波 (下采样)
   ├─ 半径滤波 (平滑)
   └─ AABB滤波 (ROI提取)
    ↓
3. 自适应滤波 (adaptiveFilter)
   ├─ 雨水干扰滤波
   ├─ 电线干扰滤波
   └─ 条件自适应调整
    ↓
4. 线特征分割 (segmentToLines)
   ├─ 聚类 (DBSCAN/欧几里得)
   └─ 拟合直线/平面
    ↓
5. 包围盒构建 (cloudToBB)
   ├─ 主成分分析 (PCA) - 找主轴
   ├─ 计算OBB尺寸 (长宽高)
   └─ 计算OBB朝向 (四元数)
    ↓
6. 特征辅助处理 (featCloudToBB)
   └─ 使用线特征优化OBB
    ↓
7. 场景自适应转换 (adaptObsToLCPS)
   ├─ 起升场景转换
   ├─ 落地场景转换
   └─ 卡车场景转换
    ↓
输出: Obstacle 列表
  ├─ 位置 (x, y, z)
  ├─ 尺寸 (宽, 深, 高)
  ├─ 朝向 (四元数)
  ├─ 置信度
  └─ 来源类型 (LINEAR/VIRTUAL/NONE)
```

#### classifyCloud利用PlaneFilter将点云划分为平面型点云和垂直型点云

符合港口堆场场景下都是集装箱障碍物的情况。集装箱都是箱面，包括上箱面、侧箱面，都是平面。

* Code: classifyCloud -> mpPlaneFilter->Filter。
* How: 利用 PlaneFilter 算法（基于投影图的霍夫变换）将点云分为两类：
* Horizon: 水平点云（箱顶、地面）。
* Vertical: 垂直点云（箱壁、大梁、轮胎）。
* Why: 只有“横平竖直”的点在岸桥场景下有意义。斜率过大的点通常是钢丝绳、雨线或噪点

平面分割流程 (PlaneFilter)

1. 双向投影: 将 3D 点云分别向 XZ 平面（侧视图）和 YZ 平面（正视图）投影，生成 2D 密度图。
2. 图像处理:
    * 网格化与归一化: 将点云映射到像素网格，进行 Min-Max 归一化和直方图均衡，增强对比度 。
    * 二值化: 根据点数阈值（<4 置0，>80 置80）生成二值图像 。
3. 直线检测: 使用 Hough 变换检测直线，分离出水平线段（箱顶）和竖直线段（箱壁）。
4. 反向投影: 将检测到的直线映射回 3D 空间，提取目标点云（Horizon Cloud / Vertical Cloud）。

使用以上假设和方案的原因是可以快速在点云中识别出需要的点云（对于10万个点以下在10ms以下能够完成）。
但是不适于一些非横平竖直场景的点，导致某些必要点被滤除。比如集装箱箱门打开的情况下，箱门不是横平竖直的。
比如一些非集装箱的对象，那么该系统会失效。

#### 聚类与OBB构建

* FEC 聚类: 使用 mm::FEC (Fast Euclidean Clustering) 对分割后的点云进行聚类。
* OBB 拟合: 对每个聚类簇，计算其主方向（PCA），并根据先验知识（集装箱尺寸）修正旋转角度（refineObsPose），确保包围盒轴线与世界坐标系或大车坐标系对齐。

利用 ObstacleParser (基于 FEC 算法) 进行欧式聚类。
refineObsPose: 修正 OBB 旋转角度。计算主方向 (PCA)，若角度偏差过大，强制校正为与坐标轴平行 (利用先验知识)。

#### 环境过滤 (filterCloud 系列)

* filterAABB: 根据作业区域（ROI）裁剪点云。
* filterSprOutlier: 滤除吊具自身的点云（基于吊具实时位置和尺寸膨胀）。
* filterRain: 基于强度（Intensity）滤除雨雾噪点 。
* filterWire: 滤除吊具钢丝绳。

#### 障碍物生成（cloudToBB）

* Land Mode (堆场下降):
  * 先处理 Gantry 方向点云 (landGantryCloudToObs)。
  * 再处理 Trolley 方向点云 (landTrolleyCloudToObs)，并结合 Gantry 障碍物进行位置修正。
  * 集卡作业特殊逻辑: 检测车道侧障碍物 (processTruckYardObs)。
* Lift Mode (堆场上升):
  * 重点检测竖直方向障碍物 (liftCloudToObs)，防止起升挂舱。

### 2.4 关键处理参数

```yaml
PlanarCntrDetector:
  # 点云源配置
  lidar_type: "quanergy_M8"        # LiDAR型号
  horizontal_angle: 25.0           # 水平扫描角
  vertical_angle: 7.5              # 竖直扫描范围

  # 分类参数
  plane_filter:
    leaf_size: 0.05                # 体素大小
    curvature_thresh: 0.01         # 曲率阈值
    avg_dis_thresh: 0.05           # 平均距离阈值

  # 过滤参数
  radius_filter: 0.1               # 半径滤波半径
  min_neighbors: 5                 # 最小邻近点数
  statistics_filter:
    mean_k: 20                     # 统计滤波K值
    stddev_mul: 1.0                # 标准差倍数

  # 聚类参数
  cluster_type: "EUCLIDEAN"        # 聚类类型
  distance_tolerance: 0.1          # 距离容忍度
  v_distance_tolerance: 0.05       # 竖直距离容忍度
  min_cluster_size: 10             # 最小聚类大小

  # 吊具检测
  lift_inlier_expand: 0.1          # 起升内层扩展
  spr_outlier_expand: 0.2          # 吊具异常值扩展
  upper_spr_outlier_expand: 0.3    # 上吊具扩展

  # 雨水/电线滤波
  rain_intensity_range: [0, 50]    # 雨水强度范围
  enable_wire_filter: true         # 启用电线滤波
  wire_thresh: [0.02, 0.05]        # 电线阈值
```

## 模块3: 状态机与生命周期

### 状态转换图

```
                    ┌──────────────────┐
                    │ UNINITIALIZED    │
                    │  (未初始化)       │
                    └────────┬─────────┘
                             │ Init()
                             ↓
                    ┌──────────────────┐
                    │ NON_OPERATION    │
                    │ (非运行状态)     │
                    └────────┬─────────┘
                    ┌────────┴──────────┐
         startLift()│                   │startLand()
                    ↓                   ↓
        ┌──────────────────────────────────────┐
        │      IN_OPERATION (运行中)          │
        │  ├─ CHECK: 检查启动条件              │
        │  ├─ READY: 等待就位                 │
        │  ├─ ACTIVE: 实时防碰撞              │
        │  └─ FINISH: 完成操作                │
        └──────────┬──────────────────────────┘
                   │ stopLCPS()
                   │ 或异常
                   ↓
        ┌──────────────────┐
        │ EXCEPTION        │
        │ (异常状态)       │
        └────────┬─────────┘
                 │ resetException()
                 ↓
        ┌──────────────────┐
        │ NON_OPERATION    │
        └──────────────────┘
```

### 生命周期逻辑 (lifeCycleLogic)

```cpp
void LCPSStateMachine::lifeCycleLogic() {
    switch (current_state) {
        case UNINITIALIZED:
            // 初始化LCPS服务
            // 加载配置文件
            // 启动内部线程
            break;

        case NON_OPERATION:
            // 空闲状态，等待启动命令
            // 定期健康检查
            // 清理内部状态
            break;

        case IN_OPERATION:
            // 防碰撞活跃阶段
            // 实时处理每一帧数据
            // 检测碰撞并做出安全决策
            // 与控制系统交互
            break;

        case EXCEPTION:
            // 异常恢复
            // 尝试自恢复或等待手动复位
            // 记录异常日志
            break;
    }
}
```

### 关键状态转换

| 转换 | 条件 | 动作 |
|------|------|------|
| UNINIT → NON_OP | Init()成功 | 初始化资源，启动线程 |
| NON_OP → IN_OP | startLift/Land() | 验证条件，启动处理 |
| IN_OP → EXCEPTION | 异常检测 | 记录日志，停止决策 |
| EXCEPTION → NON_OP | resetException() | 清理状态，恢复资源 |
| IN_OP → NON_OP | stopLCPS() | 正常停止，保存上下文 |

---

# 数据流与处理流程

## 端到端数据流

```
┌─────────────────────────────────────────────────────────────┐
│ 1. 传感器输入 (每帧~10Hz或更高)                            │
├─────────────────────────────────────────────────────────────┤
│ LiDAR点云 (XYZ)  →  PlanarCntrDetector                      │
│ 位置编码器       →  LCPS (融合位置)                         │
│ 吊具上安装的IMU  →  LCPS (吊具状态)                         │
│ PLC状态          →  LCPS (起重机状态)                       │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. 感知处理 (PlanarCntrDetector)                            │
├─────────────────────────────────────────────────────────────┤
│ 点云预处理 → 分类 → 分割 → OBB构建 → 自适应滤波           │
│ 输出: Obstacle列表 (位置、尺寸、置信度)                    │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 决策处理 (LCPS)                                          │
├─────────────────────────────────────────────────────────────┤
│ 构建OBB → 过滤障碍物 → 碰撞检测 → 安全决策                 │
│ 输出: 安全状态 (SAFE/WARNING/STOP)                         │
└──────────────────┬──────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. 执行层 (DetectorKicker + PLC)                            │
├─────────────────────────────────────────────────────────────┤
│ 通知控制器 → 调整运动 → 反馈状态                           │
└─────────────────────────────────────────────────────────────┘
```

## 关键回调接口

```cpp
// 1. 障碍物信息回调 (from PlanarCntrDetector)
void LCPS::onObstacleReady(const std::vector<ObstaclePtr>& obstacles);
  └─ 保存障碍物列表到mObstacleMap
  └─ 更新mvObsOBB (障碍物OBB)
  └─ 触发帧处理

// 2. 位置信息回调 (from SLAM/GNSS/Encoder)
void LCPS::onPoseReady(MM_SPR_POSE& pose, ...);
  └─ 更新吊具位姿 (mSprPose, mSprCntrPose)
  └─ 更新mShowSprUpperPose/mShowSprLowerPose
  └─ 检查碰撞预测 (detectPreColli)

// 3. 里程计位置回调
void LCPS::onOdometryPoseReady(const MM_POSE& pose);
  └─ 融合位置信息
  └─ 用于位置精化 (refinePosition)

// 4. 吊具摇晃状态回调
void LCPS::onSprSwingStatus(const SPREADER_SWING_STATUS& status);
  └─ 调整OBB以补偿摇晃
  └─ 更新安全边界
```

## 碰撞检测算法 (collisionCheck)

```
输入:
  - sprTargetCenter: 吊具目标中心位置
  - vObsOBB: 障碍物OBB列表
  - mvSprUpperOBB: 上吊具OBB
  - mvSprLowerOBB: 下吊具OBB
  - mvSprCntrOBB: 集装箱OBB

处理:
for each obstacle OBB {
    // 1. 计算相对距离
    distance = calculateDistance(
        spreader_OBB,
        obstacle_OBB
    );

    // 2. 判断碰撞方向
    if (distance < collision_threshold) {
        direction = determineDirection(
            obstacle_position,
            spreader_position
        );
        collision_status |= direction_bit;
    }

    // 3. 考虑扩展边界 (安全边界)
    expanded_obstacle = expandOBB(
        obstacle_OBB,
        spr_expand_params
    );
}

输出:
  collision_status: 4位掩码
    bit0: FRONT (前方碰撞)
    bit1: BACK  (后方碰撞)
    bit2: LEFT  (左侧碰撞)
    bit3: RIGHT (右侧碰撞)

  relative_offset: 最近碰撞距离
  collision_direction: 主要碰撞方向
```

## 安全决策算法 (safetyDecision)

```cpp
void safetyDecision(
    int8_t motionMode,           // LIFT/LAND
    uint8_t curCollisionStatus,  // 当前碰撞状态
    uint8_t& finalSafetyStatus   // 输出安全状态
) {
    // 1. 根据运动模式选择参考坐标系
    if (motionMode == LIFT) {
        // 起升模式: 检查下方障碍
        check_bottom_obs = true;
        check_above_obs = false;
    } else {
        // 落地模式: 检查四周
        check_all_directions = true;
    }

    // 2. 计算碰撞严重程度
    severity = calculateSeverity(
        collision_distance,
        spreader_speed,
        obstacle_size
    );

    // 3. 根据严重程度决策
    if (severity > CRITICAL_THRESHOLD) {
        finalSafetyStatus = SAFETY_STATUS_STOP;     // 紧急停止
        notifyController(STOP_ACTION);
    } else if (severity > WARNING_THRESHOLD) {
        finalSafetyStatus = SAFETY_STATUS_WARNING;  // 降速警告
        notifyController(DECELERATE_ACTION);
    } else {
        finalSafetyStatus = SAFETY_STATUS_SAFE;     // 安全继续
        notifyController(NORMAL_ACTION);
    }

    // 4. 记录异常日志
    if (severity > WARNING_THRESHOLD) {
        logWarning(collision_info);
    }
}
```

---

# 状态机与生命周期

## LCPSStateMachine核心方法

### `startLiftLCPS()` - 启动起升防碰撞

```cpp
void LCPSStateMachine::startLiftLCPS() {
    // 1. 验证前置条件
    //    ├─ LCPS已初始化
    //    ├─ 当前状态为NON_OPERATION
    //    └─ 起重机状态有效

    // 2. 设置运动模式为LIFT
    mpLCPS->setMotionMode(LIFT_MOTION);

    // 3. 启动LCPS处理线程
    mpLCPS->Init();

    // 4. 状态转换
    setState(IN_OPERATION);

    // 5. 初始化内部状态
    //    ├─ 清空障碍物缓冲
    //    ├─ 重置碰撞历史
    //    └─ 设置起升特定参数
}
```

### `startLandLCPS()` - 启动落地防碰撞

```cpp
void LCPSStateMachine::startLandLCPS() {
    // 1. 验证前置条件 (同上)

    // 2. 设置运动模式为LAND
    mpLCPS->setMotionMode(LAND_MOTION);

    // 3. 加载落地特定配置
    //    ├─ 调整碰撞检测参数
    //    ├─ 启用地面障碍检测
    //    └─ 启用吊具下降防护

    // 4. 启动LCPS
    // 5. 状态转换
}
```

### `stopLCPS()` - 正常停止

```cpp
void LCPSStateMachine::stopLCPS() {
    // 1. 设置停止标志
    mbLCPSRunning = false;

    // 2. 等待处理线程退出
    //    └─ 最多等待timeout毫秒

    // 3. 清理资源
    //    ├─ 清空缓冲
    //    ├─ 关闭线程
    //    └─ 释放内存

    // 4. 状态转换到NON_OPERATION
    setState(NON_OPERATION);

    // 5. 通知系统已停止
    NOTIFY_CLIENTS(onLCPSStopped);
}
```

## 异常处理机制

### 异常类型与处理

```cpp
enum class LCPSException {
    EXC_SPR_POSE,        // 吊具位姿异常
    EXC_SPR_TIMEOUT,     // 吊具数据超时
    EXC_CRANE_INFO,      // 起重机信息异常
    EXC_SYSTEM_INFO,     // 系统信息异常
    EXC_CRANE_SPEED,     // 起重机速度异常
};

void LCPS::exceptionHandler(LCPSException exc_type) {
    // 1. 记录异常
    logException(exc_type);

    // 2. 评估严重程度
    severity = assessSeverity(exc_type);

    // 3. 采取行动
    if (severity == CRITICAL) {
        // 紧急停止
        triggerEmergencyStop();
        setState(EXCEPTION);
    } else if (severity == WARNING) {
        // 记录警告，继续运行
        logWarning(exc_type);
    }

    // 4. 尝试自恢复
    if (canAutoRecover(exc_type)) {
        recovery_thread.launch();
    }
}
```

---

# 安全监控机制

## DetectorKicker的LCPS监控

### `operateLCPS()` - 核心监控逻辑

```cpp
void DetectorKicker::operateLCPS(const LIFE_CYCLE_DATA_T& data) {
    // 1. 获取LCPS状态
    LCPSSMState lcps_state = mpLCPSSM->state();

    // 2. 检查Spreader信号有效性
    bool VFS_valid = checkSignalTimeout(VFSSignal, timeout=1000ms);
    bool VRS_valid = checkSignalTimeout(VRSSignal, timeout=1000ms);

    // 3. 下降信号检查 (VFS/PFS)
    if ((VFS_valid || PFS_valid) && isValid()) {
        // 吊具正在下降
        if (spreader_speed < 1e-5) {
            // 吊具应该在动，但实际上没动
            if (lcps_state != IN_OPERATION) {
                // LCPS没有启动，异常！
                MM_ERROR("[LCPS] Spreader falling but LCPS not in operation");
                notifySafety("_LCPS", SAFETY_STATUS_STOP, AL_SPR_DOWN);
                mvLCPSException.first = true;
            }
        }
    }

    // 4. 上升信号检查 (VRS/PRS)
    if ((VRS_valid || PRS_valid) && isValid()) {
        // 吊具正在上升
        if (spreader_speed > -1e-5) {
            // 吊具应该在动，但实际上没动
            if (lcps_state == NON_OPERATION || lcps_state == UNINITIALIZED) {
                // LCPS没有启动，异常！
                MM_ERROR("[LCPS] Spreader rising but LCPS not running");
                notifySafety("_LCPS", SAFETY_STATUS_STOP, AL_SPR_UP);
                mvLCPSException.second = true;
            } else if (!mpLCPSSM->isLCPSStart()) {
                // LCPS在正确状态但没有启动
                MM_ERROR("[LCPS] Valid state but not started");
                notifySafety("_LCPS", SAFETY_STATUS_STOP, AL_SPR_UP);
                mvLCPSException.second = true;
            }
        }
    }

    // 5. 异常恢复
    if (spreader_speed < -0.05 || spreader_up) {
        if (mvLCPSException.second) {
            // 清除上升异常
            notifySafety("_LCPS", SAFETY_STATUS_SAFE, AL_SPR_UP);
            mvLCPSException.second = false;
        }
    }

    // 6. 状态变化通知
    if (lcps_state != mLastLCPSState) {
        MM_INFO("[LCPS] State changed: %s → %s",
            getStateStr(mLastLCPSState),
            getStateStr(lcps_state));
        mLastLCPSState = lcps_state;
    }
}
```

### 信号同步机制

```
Spreader摇晃过程中的信号时序:

时间轴:
t=0: VFS/VRS信号产生 (Spreader开始下降/上升)
     └─ 记录信号时间戳: signal_time = t0

t=200ms: LCPS内部延迟处理完成

t=500ms: 可靠的运动指示
         └─ 此时检查LCPS状态: 应为 IN_OPERATION

t=1000ms: 信号超期
         └─ 如果超过此时间仍无效，视为信号丢失

监控逻辑:
  if (signal_valid && (now - signal_time) > 200ms) {
      if ((now - signal_time) < 1000ms) {
          // 可靠判断期
          check_lcps_state();
      }
  }
```

### 安全通知机制

```cpp
void DetectorKicker::notifySafety(
    const std::string& info,        // 信息标签
    uint8_t safetyStatus,           // STOP/WARNING/SAFE
    uint8_t action                  // AL_SPR_UP/AL_SPR_DOWN
) {
    MM_CRANE_SAFETY safety;
    safety.serName = "DetectorKicker" + info;
    safety.actionAllow = AL_ALL;
    safety.highSpeedAllow = AL_ALL;

    if (safetyStatus == SAFETY_STATUS_STOP) {
        // 禁止对应动作
        safety.actionAllow &= ~action;
    } else if (safetyStatus == SAFETY_STATUS_WARNING) {
        // 禁止高速动作
        safety.highSpeedAllow &= ~action;
    } else {
        // 完全允许
        safety.actionAllow |= action;
        safety.highSpeedAllow |= action;
    }

    // 广播给所有监听者 (PLC, Controller等)
    NOTIFY_CLIENTS(onCraneSafetyChanged, safety);
}
```

## 看门狗机制 (watchdogHeartThread)

```cpp
void LCPS::watchdogHeartThread() {
    while (!mbExitViewer) {
        std::this_thread::sleep_for(
            std::chrono::milliseconds(mWatchdogHeartInterval)
        );

        // 定期心跳
        MM_INFO("[LCPS_WDG] Send watchdog heart signal");

        // 检查内部线程健康状态
        if (!detectorThreadHealthy()) {
            MM_ERROR("[LCPS_WDG] Detector thread unhealthy!");
            triggerRecovery();
        }

        // 检查数据流
        if (!hasReceivedDataRecently()) {
            MM_WARN("[LCPS_WDG] No recent data received");
        }
    }
}
```

---

# 不可忽略的保护机制（Safety Guardrails）

## Watchdog (看门狗)

* 代码: LCPS::watchdogHeartThread。
* 机制: LCPS 必须不断向外部发送心跳。如果死锁或 Crash，心跳停止，PLC 会立刻急停。
* 作用: LCPS是安全作业的重要保护机制，要能够实时保护。如果在运行过程中出现异常延时、阻塞等，将会极大的
  影响现场安全。所以需要看门狗来监控其帧率。
* 修改禁忌: 严禁在主循环中加入耗时过长的同步操作（如大文件IO），否则会由 Watchdog 触发误急停。

## 状态机保护 (Lifecycle)

* 代码: LCPSStateMachine::lifeCycleLogic。
* 逻辑: 系统只在 TARGET_IN_PLACE (小车到位) 后才完全接管。
* 目的: 防止吊具在赶往目标位的途中，因为路过高箱区而误触发防撞。

## 预碰撞检测 (Pre-Collision / Bowling)

目前该功能处于disable状态，早先引入该功能是为了当吊具在较高处时就进行粗粒度的提前避免，尽可能将吊具移动到
合适位置（没有碰撞或者尽量少的碰撞）。后来因为功能不稳定，该方案作用有限关闭了。

* 代码: LCPS::processPreObsFrame 。
* 逻辑: 在较高处将吊具以及障碍物按照Uniform z方向投影并进行碰撞判断，提前进行粗粒度的碰撞检测。
* 动作: 调用 mpPLCProcess->moveTrolleyNonBlocking 提前减速，而不是等到撞上才急停。

# 配置与参数

## 配置文件位置

```
项目根目录/
├── config/
│   ├── detector/
│   │   ├── LCPS.yaml           # LCPS核心配置
│   │   └── detector_customize.yaml  # 检测器自定义参数
│   └── service/
│       └── DetectorKicker.yaml  # DetectorKicker配置
```

## LCPS主要配置节点

```yaml
LCPS:
  # 调试选项
  show_viewer: false              # 显示可视化窗口
  debug: true                     # 调试模式
  show_image: false               # 显示图像
  record_context: false           # 记录上下文
  filter: true                    # 启用滤波

  # 处理方式
  process_type: "TYPE_PROCESS"    # 处理类型
  position_type: "TYPE_POSITION_ENCODER"  # 位置源

  # 扩展参数 (安全边界)
  spr_expand_s: 0.3               # 前后扩展
  spr_expand_w: 0.25              # 左右扩展
  spr_expand_s_t: 0.5             # 集装箱前后
  spr_expand_w_t: 0.5             # 集装箱左右

  # 距离与高度
  colli_distance_thresh: 0.2
  max_layer_height: 35.0
  spr_safe_min_height: 2.0

  # 预防碰撞
  enable_pre_obs_avoid: true
  pre_obs_avoid_expand: 0.5
  obs_avoid_move_thresh: [0.1, 0.2]
  obs_avoid_min_gap: [0.5, 0.3]

  # 时序参数
  run_wait_timeout: 1000          # ms
  obstacle_wait_timeout: 500      # ms
  watchdog_heart_interval: 100    # ms
```

## PlanarCntrDetector配置

```yaml
PlanarCntrDetector:
  # 图形化调试
  show_viewer: false
  record_context: false

  # LiDAR参数
  horizontal_angle: 25.0
  vertical_angle: 7.5

  # 过滤阈值
  bb_thresh: 0.1
  grid_size: 0.2
  distance_tolerance: 0.1
  v_distance_tolerance: 0.05

  # 聚类参数
  min_cluster_size: 10
  cluster_type: "EUCLIDEAN"

  # 吊具检测扩展
  lift_inlier_expand: 0.1
  spr_outlier_expand: 0.2

  # 自适应滤波
  enable_adaptive_filter: true
  h_statis_mean_k: 20
  h_statis_stddev_mul: 1.0
```

---

# 集成点与接口

## 与PLC的接口

```cpp
// 1. 获取起重机状态
MM_POSITION position;
MM_CRANE_SPEED speed;
MM_SPREADER_STATUS status;
plcProcess->getCurrentPosition(position);
plcProcess->getCraneSpeed(speed);
plcProcess->getSpreaderStatus(status);

// 2. 发送安全决策
MM_CRANE_SAFETY safety;
safety.actionAllow = allowed_actions;
NOTIFY_CLIENTS(onCraneSafetyChanged, safety);

// 3. 反馈错误代码
plcProcess->feedbackBitErrCode(SEC_LCPS_STOP, true);    // 停止
plcProcess->feedbackBitErrCode(SEC_LCPS_WARNING, true); // 警告
```

## 与其他模块的交互

| 模块 | 交互类型 | 内容 |
|------|---------|------|
| **CraneStatus** | 读 | 位置、速度、吊具状态、场景类型 |
| **PLCProcess** | 读/写 | 位置、安全状态、错误代码 |
| **Transformer** | 读 | 坐标变换 (G→U, L→G等) |
| **YardCS** | 读 | 场地坐标系统信息 |
| **GlobalCommonConfig** | 读 | 全局配置参数 |

## 消息回调注册

```cpp
// LCPS内部回调
MessageCallback obstacle_cb = std::bind(
    &LCPS::onObstacleReady, this, std::placeholders::_1
);
Subscribe("onObstacleReady", obstacle_cb, node_name, node_index);

MessageCallback pose_cb = std::bind(
    &LCPS::onPoseReady, this, std::placeholders::_1, ...
);
Subscribe("onPoseReady", pose_cb, node_name, node_index);

// DetectorKicker回调
MessageCallback odometry_cb = std::bind(
    &DetectorKicker::onOdometryPoseReady, this, std::placeholders::_1
);
Subscribe("onOdometryPoseReady-1", odometry_cb, node_name, 0);
```

## 线程模型

```
Main Thread (系统主线程)
    ├─ LiDAR数据帧事件
    │   └─ PlanarCntrDetector::onLidarXYZIFrameReady()
    │       └─ 触发detectThread
    │
    ├─ 位置更新事件
    │   └─ LCPS::onPoseReady()
    │       └─ 触发runThread
    │
    └─ 监控事件 (DetectorKicker)
        └─ runThread (30Hz)
            ├─ 检查LCPS状态
            ├─ 协调其他传感器
            └─ 发送安全通知

Worker Threads:
    ├─ LCPS::runThread
    │   └─ 主处理循环 (processFrame)
    │
    ├─ PlanarCntrDetector::detectorThread
    │   └─ 点云处理管线
    │
    └─ LCPS::watchdogHeartThread
        └─ 定期健康检查
```

---

# 性能指标与约束

## 实时性要求

| 指标 | 目标 | 说明 |
|------|------|------|
| **帧处理延迟** | < 100ms | LCPS单帧处理时间 |
| **点云处理** | < 50ms | PlanarCntrDetector处理延迟 |
| **决策延迟** | < 20ms | 碰撞检测到安全决策 |
| **通知延迟** | < 10ms | 决策到PLC通知 |
| **总端到端** | < 200ms | 传感器输入到执行输出 |

## 资源约束

```
内存占用:
  - LCPS类: ~200MB (点云缓冲、OBB存储)
  - PlanarCntrDetector: ~300MB (处理缓冲)
  - 总计: ~500MB (可调)

CPU占用:
  - LCPS处理: ~20-30% (单核心)
  - PlanarCntrDetector: ~40-50%
  - DetectorKicker: ~5%
  - 总计: ~60-80% (8核心系统)

网络带宽:
  - 障碍物信息: ~50KB/frame @10Hz = 500KB/s
  - 位置反馈: ~10KB/frame @50Hz = 500KB/s
```

---

# 故障排查与恢复

## 常见异常与处理

| 异常 | 症状 | 可能原因 | 处理方法 |
|------|------|--------|--------|
| **吊具位姿异常** | EXC_SPR_POSE | SLAM/IMU失效 | 切换位置源 |
| **数据超时** | EXC_SPR_TIMEOUT | 传感器连接丢失 | 尝试重连 |
| **碰撞误判** | 错误停止 | OBB参数不准 | 调整expand参数 |
| **响应慢** | 处理延迟>200ms | CPU负荷高 | 减少点云分辨率 |

## 调试技巧

```cpp
// 1. 启用详细日志
LCPS.debug = true
PlanarCntrDetector.show_viewer = true

// 2. 导出上下文
LCPS.record_context = true
// 导出: /path/to/lcps_context_*.bin

// 3. 可视化点云处理
// 使用PCL/Open3D可视化工具分析处理过程

// 4. 性能分析
std::chrono::high_resolution_clock timer;
auto start = timer.now();
// ... 处理 ...
auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
    timer.now() - start
);
MM_DEBUG("Processing time: %ldms", elapsed.count());
```

---

# 总结

LCPS是一套完整的实时防碰撞系统，通过以下关键要素实现安全保护：

1. **多层次架构**: 感知层(PlanarCntrDetector) → 决策层(LCPS) → 执行层(DetectorKicker)
2. **实时处理**: 端到端延迟<200ms，满足工业级要求
3. **完善的监控**: 状态机管理、异常处理、看门狗机制
4. **灵活的配置**: 参数化设计支持多种场景和工作模式
5. **健壮的集成**: 与PLC、控制器等系统紧密协调

通过深入理解这些组件的协作机制，可以有效维护和优化系统性能，确保货柜起升作业的安全性。

---

# 相关文件

* `src/service/LCPS/LCPS.hpp` - LCPS核心类定义
* `src/service/LCPS/LCPS.cpp` - LCPS实现 (~4500行)
* `src/service/LCPS/LCPSState.hpp` - 状态定义
* `src/detector/perception/planarCntrDetector/PlanarCntrDetector.hpp` - 检测器定义
* `src/detector/perception/planarCntrDetector/PlanarCntrDetector.cpp` - 检测器实现
* `src/app/LCPSStateMachine.cpp` - 状态机实现 (~591行)
* `src/service/DetectorKicker/DetectorKicker.hpp` - 监控类定义
* `src/service/DetectorKicker/DetectorKicker.cpp` - 监控实现 (~1880行)

---

# Reference
* 大车: 其实就是指RTG，RTG是个门字结构，能够垂直于门架方向沿车道线运动，最高速度能达到2m/s.
* 小车（RTG 司机驾驶舱的另一种说法），位于RTG的大梁上，可以从大梁一侧运行到另一侧（从电气房侧到动力房侧，或者从动力房侧到电气房侧），常见的针对6 + 1的堆场，其跨度在18.5米。


**文档完成**

本文档完整覆盖了LCPS防打保龄系统的实现细节，从架构设计、处理流程、状态管理到安全监控等各个方面。通过学习此文档，可以快速理解系统的工作原理和关键技术。
