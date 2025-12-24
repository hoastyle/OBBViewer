---
title: "LCPS核心算法详解"
description: "LCPS系统核心算法的数学模型、实现细节和参数说明"
type: "技术设计"
status: "完成"
priority: "高"
created_date: "2025-12-10"
last_updated: "2025-12-10"
related_documents:
  - "docs/architecture/lcps/01_LCPS_SYSTEM_OVERVIEW.md"
  - "docs/architecture/lcps/03_LCPS_POINTCLOUD_PIPELINE.md"
  - "docs/architecture/lcps/04_LCPS_IMPLEMENTATION_ANALYSIS.md"
related_code:
  - "src/service/LCPS/LCPS.cpp:updateExpandSize"
  - "src/service/LCPS/LCPS.cpp:refinePosition"
  - "src/service/LCPS/LCPS.cpp:collisionCheck"
  - "src/service/LCPS/LCPS.cpp:safetyDecision"
  - "src/service/LCPS/LCPS.cpp:constructSprBox"
tags: ["LCPS", "算法", "碰撞检测", "传感器融合", "决策滤波"]
authors: ["Claude"]
version: "1.0"
---

# LCPS核心算法详解

## 文档说明

本文档深入讲解LCPS系统的四大核心算法：动态边界框扩展、多源位置融合、碰撞检测和安全决策滤波。每个算法都包含数学模型、代码实现分析、参数说明和应用场景。

---

## 算法1: 动态边界框扩展（Dynamic Expansion）

### 扩展算法的设计目标

根据龙门吊小车的实时速度，动态调整吊具碰撞检测区域的大小，实现**速度越快、检测区越大**的自适应安全策略。

### 物理模型

**刹车距离公式**（基于匀减速运动）：

```
S = v² / (2a) + v + 0.2

其中：
  S = 刹车距离 (m)
  v = 当前速度 (m/s)
  a = 制动减速度 (m/s²，配置参数 mfSpreaderDeceleration)
  v = 反应时间补偿（假设1秒）
  0.2 = 机械延迟补偿（固定值）
```

**物理意义**：

* `v²/(2a)`: 匀减速运动的刹车距离
* `v`: 反应时间内的移动距离（假设反应时间为1秒）
* `0.2`: 机械系统响应延迟（制动器动作时间）

### 代码实现

**函数签名**：

```cpp
RET LCPS::updateExpandSize(float speed);
```

**实现位置**：`src/service/LCPS/LCPS.cpp:577-629`

### 扩展算法的代码实现

**核心逻辑**：

```cpp
RET LCPS::updateExpandSize(float speed) {
  // Step 1: 计算物理刹车距离
  float stopDis = 0.5 * (speed / mfSpreaderDeceleration) * speed + speed + 0.2;

  // Step 2: 计算吊具垂直方向扩展系数（sprScale）
  if (LOAD mode) {
    // 装载模式：基于刹车距离和基础扩展尺寸
    sprScale = max(base_scale, stopDis / (2 × mwExpandSize[2]));
  } else {
    // 卸载模式：考虑吊具抓手高度
    sprScale = max(base_scale, (SPR_GRIPPER_HEIGHT + stopDis) / (2 × mwExpandSize[2]));
  }

  // Step 3: 特殊情况处理
  if (LAND_MODE && !spreader_down) {
    sprScale = 0;  // 落地模式下吊具未放下，不扩展垂直方向
  }

  // Step 4: 根据速度档位选择小车方向扩展系数（trolleyScale）
  if (speed >= mvSprSpeedThres[3]) {              // >= 0.75 m/s
    trolleyScale = mvSprSpeedTroScale[3];         // 全速档
  } else if (speed >= mvSprSpeedThres[2]) {       // >= 0.5 m/s
    trolleyScale = mvSprSpeedTroScale[2];         // 高速档 + 集装箱
  } else if (speed >= mvSprSpeedThres[1]) {       // >= 0.1 m/s
    trolleyScale = mvSprSpeedTroScale[1];         // 低速档 + 集装箱
  } else if (speed >= mvSprSpeedThres[0]) {       // >= 0.035 m/s
    trolleyScale = mvSprSpeedTroScale[0];         // 极低速档
  } else {
    trolleyScale = 0;  // 速度过低，不扩展
  }

  // Step 5: 更新全局扩展尺寸变量
  // Stop zone (停止区)
  gSExpandSize = {
    msExpandSize[0] * trolleyScale,    // X: 小车方向（均匀扩展）
    msExpandSize[1] * trolleyScale,    // Y: 大车方向（均匀扩展）
    msExpandSize[2] * sprScale         // Z: 垂直方向（吊具相关）
  };

  // Warning zone (警告区)
  gWExpandSize = {
    mwExpandSize[0] * trolleyScale,    // X: 小车方向
    mwExpandSize[1] * sprScale,        // Y: 大车方向（垂直相关）
    mwExpandSize[2] * sprScale         // Z: 垂直方向
  };

  // Trolley-specific Stop zone（小车专用停止区）
  gTSExpandSize = {
    mtSExpandSize[0] * trolleyScale,
    mtSExpandSize[1] * trolleyScale,
    mtSExpandSize[2] * sprScale
  };

  // Trolley-specific Warning zone（小车专用警告区）
  gTWExpandSize = {
    mtWExpandSize[0] * trolleyScale,
    mtWExpandSize[1] * trolleyScale,
    mtWExpandSize[2] * sprScale
  };

  // Container Stop zone（集装箱停止区）
  gCntrSExpandSize = {
    mCntrStopExpandSize[0] * trolleyScale,
    mCntrStopExpandSize[1] * trolleyScale,
    mCntrStopExpandSize[2] * sprScale
  };

  // Container Warning zone（集装箱警告区）
  gCntrWExpandSize = {
    mCntrWarnExpandSize[0] * trolleyScale,
    mCntrWarnExpandSize[1] * trolleyScale,
    mCntrWarnExpandSize[2] * sprScale
  };

  return RET_NORMAL;
}
```

### 参数说明

| 参数 | 类型 | 说明 | 典型值 |
|------|------|------|--------|
| `speed` | float | 当前小车速度 (m/s) | 0 ~ 1.5 |
| `mfSpreaderDeceleration` | float | 吊具制动减速度 (m/s²) | 0.5 ~ 1.0 |
| `SPR_GRIPPER_HEIGHT` | float | 吊具抓手高度 (m) | ~0.5 |
| `mvSprSpeedThres[4]` | vector<float> | 速度阈值 [极低, 低, 高, 全速] | [0.035, 0.1, 0.5, 0.75] |
| `mvSprSpeedTroScale[4]` | vector<float> | 小车扩展系数（按档位） | [0.5, 1.0, 1.5, 2.0] |
| `msExpandSize[3]` | vector<float> | 停止区基础扩展 (X, Y, Z) | [0.2, 0.2, 0.3] |
| `mwExpandSize[3]` | vector<float> | 警告区基础扩展 (X, Y, Z) | [0.4, 0.4, 0.5] |

### 扩展策略矩阵

| 速度档位 | 速度范围 | 小车方向系数 | 垂直方向系数 | 适用场景 |
|---------|---------|------------|------------|---------|
| **档位0（极低速）** | < 0.035 m/s | 0 | 最小 | 几乎停止 |
| **档位1（低速）** | 0.035 ~ 0.1 m/s | mvSprSpeedTroScale[0] | 基于刹车距离 | 接近目标 |
| **档位2（中速）** | 0.1 ~ 0.5 m/s | mvSprSpeedTroScale[1] | 基于刹车距离 + 集装箱 | 正常移动 |
| **档位3（高速）** | 0.5 ~ 0.75 m/s | mvSprSpeedTroScale[2] | 基于刹车距离 + 集装箱 | 快速移动 |
| **档位4（全速）** | >= 0.75 m/s | mvSprSpeedTroScale[3] | 最大扩展 | 最高速度 |

### 扩展算法的应用场景

**场景1：低速接近集装箱（0.05 m/s）**

```
stopDis = 0.5 * (0.05 / 0.5) * 0.05 + 0.05 + 0.2 = 0.2525 m
trolleyScale = mvSprSpeedTroScale[0]  （假设 = 0.5）
sprScale = max(base, 0.2525 / (2 × 0.5)) = max(base, 0.253)

结果：小车方向扩展较小，垂直方向根据刹车距离计算
```

**场景2：高速移动（0.8 m/s）**

```
stopDis = 0.5 * (0.8 / 0.5) * 0.8 + 0.8 + 0.2 = 1.64 m
trolleyScale = mvSprSpeedTroScale[3]  （假设 = 2.0）
sprScale = max(base, 1.64 / (2 × 0.5)) = max(base, 1.64)

结果：小车方向和垂直方向都显著扩展，提供更大安全区
```

### 扩展算法的技术亮点

1. **物理原理支撑**：基于实际刹车距离计算，而非经验值
2. **速度档位映射**：避免扩展系数频繁抖动
3. **装载/卸载差异**：考虑吊具抓手高度的影响
4. **方向解耦**：小车方向和垂直方向独立计算

---

## 算法2: 多源位置融合（Sensor Fusion）

### 融合算法的设计目标

融合**编码器、GNSS/RTK、视觉SLAM**三种位置源，提供更鲁棒、更精确的龙门吊定位，应对单一传感器故障或不准确的情况。

### 融合架构

```
传感器优先级（可靠性排序）：
  1. 编码器 (Encoder) - 基线，始终可用，但可能有累积误差
  2. GNSS/RTK - 高精度，但可能信号丢失或多路径干扰
  3. 视觉SLAM - 连续更新，但易受光照和特征影响，存在漂移

融合策略：统计方法（均值/中位数 + 异常值检测）
```

### GNSS角度补偿数学模型

**问题**：龙门吊大车可能与坐标轴不完全对齐，导致GNSS报告的X/Y位置需要角度补偿。

**补偿公式**：

```
设：θ_current = 当前偏航角
   θ_start = 起始偏航角
   θ_avg = (θ_current + θ_start) / 2   # 平均偏航角

则：
  Δx_trolley = (x_current - x_start) / cos(θ_avg)
  Δy_gantry = (y_current - y_start) + (x_current - x_start) × tan(θ_avg)
```

**几何意义**：

* `cos(θ_avg)`: X方向投影修正
* `tan(θ_avg)`: Y方向倾斜修正
* 使用平均角度减少瞬时角度误差的影响

### 融合算法的代码实现

**函数签名**：

```cpp
int LCPS::refinePosition(MM_POSITION& pos,
                         std::map<uint8_t, MM_POSITION>& posMap,
                         bool updateRadius,
                         float& trolleyFluctuateRadius,
                         float& gantryFluctuateRadius);
```

**实现位置**：`src/service/LCPS/LCPS.cpp:955-1029`

**核心逻辑**：

```cpp
int LCPS::refinePosition(MM_POSITION& pos,
    std::map<uint8_t, MM_POSITION>& posMap,
    bool updateRadius,
    float& trolleyFluctuateRadius, float& gantryFluctuateRadius) {

  // Step 1: 获取GNSS数据
  MM_POSITION gnssPos;
  if (mpYardCS->getCurPosition(gnssPos) == 0) {
    posMap[TYPE_POSITION_GNSS] = gnssPos;
  } else {
    posMap.erase(TYPE_POSITION_GNSS);  // GNSS失效，从融合中移除
  }

  // Step 2: 获取SLAM数据（从循环缓冲区）
  if (!mPosCb.empty()) {
    MM_POSE slamPose = mPosCb.back();
    posMap[TYPE_POSITION_SLAM] = {slamPose.x, slamPose.y, slamPose.z, slamPose.yaw};
  }

  // Step 3: 编码器数据（已在pos中）
  posMap[TYPE_POSITION_ENCODER] = pos;

  // Step 4: 计算各传感器的偏移量
  std::map<uint8_t, float> validTrolleyOffsetMap;
  std::map<uint8_t, float> validGantryOffsetMap;

  for (auto& [sensorType, sensorPos] : posMap) {
    if (sensorType == TYPE_POSITION_GNSS) {
      // GNSS角度补偿
      float avgAngle = (sensorPos.yaw + mStartPosMap[sensorType].yaw) / 2.0f;
      float dx = sensorPos.x - mStartPosMap[sensorType].x;
      float dy = sensorPos.y - mStartPosMap[sensorType].y;

      validTrolleyOffsetMap[sensorType] = dx / cos(avgAngle);
      validGantryOffsetMap[sensorType] = dy + dx * tan(avgAngle);

    } else if (sensorType == TYPE_POSITION_SLAM) {
      // SLAM直接偏移
      validTrolleyOffsetMap[sensorType] = sensorPos.x - mStartPosMap[sensorType].x;
      validGantryOffsetMap[sensorType] = sensorPos.y - mStartPosMap[sensorType].y;

    } else if (sensorType == TYPE_POSITION_ENCODER) {
      // 编码器直接偏移
      validTrolleyOffsetMap[sensorType] = sensorPos.x - mStartPosMap[sensorType].x;
      validGantryOffsetMap[sensorType] = sensorPos.y - mStartPosMap[sensorType].y;
    }
  }

  // Step 5: 统计融合（小车方向）
  float fusedTrolley = mStartPosMap[TYPE_POSITION_ENCODER].x;
  if (mvEnablePositionRefine[0]) {  // 小车方向融合开关
    posFusion(validTrolleyOffsetMap, {}, updateRadius,
              mStartPosMap[TYPE_POSITION_ENCODER].x,
              fusedTrolley, trolleyFluctuateRadius);
  }

  // Step 6: 统计融合（大车方向）
  float fusedGantry = mStartPosMap[TYPE_POSITION_ENCODER].y;
  if (mvEnablePositionRefine[1]) {  // 大车方向融合开关
    posFusion(validGantryOffsetMap, {}, updateRadius,
              mStartPosMap[TYPE_POSITION_ENCODER].y,
              fusedGantry, gantryFluctuateRadius);
  }

  // Step 7: 更新输出位置
  pos.x = fusedTrolley;
  pos.y = fusedGantry;

  return 0;
}
```

### 统计融合算法（posFusion）

**函数签名**：

```cpp
int LCPS::posFusion(const std::map<uint8_t, MM_POSITION>& posMap,
                    const std::map<uint8_t, double>& offsetMap,
                    bool updateRadius,
                    float start, float& current, float& fluctuateRadius);
```

**融合策略**：

```cpp
int LCPS::posFusion(...) {
  // 1. 收集有效偏移值
  std::vector<float> offsets;
  for (auto& [type, offset] : offsetMap) {
    offsets.push_back(offset);
  }

  // 2. 异常值检测（基于标准差）
  DataVecStatistics<float> stats(offsets);
  float mean = stats.mean();
  float stdDev = stats.stdVariance();

  std::vector<float> filteredOffsets;
  for (float offset : offsets) {
    if (abs(offset - mean) <= 2.0 * stdDev) {  // 2-sigma规则
      filteredOffsets.push_back(offset);
    }
  }

  // 3. 计算融合结果（中位数或均值）
  float fusedOffset;
  if (filteredOffsets.size() > 0) {
    sort(filteredOffsets.begin(), filteredOffsets.end());
    if (filteredOffsets.size() % 2 == 1) {
      fusedOffset = filteredOffsets[filteredOffsets.size() / 2];  // 奇数：中位数
    } else {
      fusedOffset = (filteredOffsets[filteredOffsets.size() / 2 - 1] +
                     filteredOffsets[filteredOffsets.size() / 2]) / 2.0f;  // 偶数：平均中位数
    }
  } else {
    fusedOffset = 0;  // 所有传感器异常，使用起始位置
  }

  // 4. 更新波动半径（如果允许）
  if (updateRadius && filteredOffsets.size() > 1) {
    float maxDiff = 0;
    for (float offset : filteredOffsets) {
      maxDiff = max(maxDiff, abs(offset - fusedOffset));
    }
    fluctuateRadius = maxDiff;  // 波动半径 = 最大偏差
  }

  // 5. 计算最终位置
  current = start + fusedOffset;

  return 0;
}
```

### 波动半径（Fluctuation Radius）

**定义**：传感器间最大偏差，量化传感器一致性的指标。

**计算公式**：

```
fluctuateRadius = max(|offset_i - fusedOffset|)  for all i

其中：
  offset_i = 第i个传感器的偏移量
  fusedOffset = 融合后的偏移量
```

**用途**：

1. **传感器健康监测**：半径突然增大 → 某传感器异常
2. **置信度评估**：半径越小 → 传感器越一致 → 定位越可信
3. **异常值检测**：配合标准差进行传感器故障诊断

### 应用场景示例

**场景1：GNSS信号良好，SLAM正常**

```
传感器数据：
  Encoder: x=10.0, y=5.0
  GNSS (补偿后): x=10.05, y=5.02
  SLAM: x=9.98, y=4.99

统计融合：
  小车方向：[10.0, 10.05, 9.98] → 中位数 = 10.0
  大车方向：[5.0, 5.02, 4.99] → 中位数 = 5.0

波动半径：
  trolleyFluctuateRadius = max(|10.0-10.0|, |10.05-10.0|, |9.98-10.0|) = 0.05m
  gantryFluctuateRadius = 0.02m

结果：三传感器一致性好，融合结果可信
```

**场景2：GNSS信号丢失**

```
传感器数据：
  Encoder: x=10.0, y=5.0
  GNSS: 无效（从posMap中移除）
  SLAM: x=9.95, y=5.01

统计融合：
  小车方向：[10.0, 9.95] → 平均 = 9.975
  大车方向：[5.0, 5.01] → 平均 = 5.005

波动半径：
  trolleyFluctuateRadius = 0.025m
  gantryFluctuateRadius = 0.005m

结果：降级到双传感器融合，仍可正常工作
```

**场景3：SLAM漂移异常**

```
传感器数据：
  Encoder: x=10.0, y=5.0
  GNSS (补偿后): x=10.02, y=5.01
  SLAM: x=12.5, y=5.05  （明显异常）

异常值检测：
  均值 = (10.0 + 10.02 + 12.5) / 3 = 10.84
  标准差 = sqrt(((10.0-10.84)² + (10.02-10.84)² + (12.5-10.84)²) / 3) = 1.18
  2σ阈值 = 2 × 1.18 = 2.36

检查：|12.5 - 10.84| = 1.66 < 2.36 → 未被过滤（需要更严格阈值）

改进建议：使用3σ规则或固定阈值（如0.5m）
```

### 技术亮点

1. **GNSS角度补偿**：处理龙门非对齐问题
2. **中位数融合**：对异常值鲁棒
3. **波动半径**：传感器健康监测指标
4. **降级模式**：单个传感器失效时自动切换
5. **异常值检测**：2-sigma规则过滤野值

---

## 算法3: 碰撞检测算法（Collision Detection）

### 检测算法的设计目标

通过**几何相交测试**判断障碍物OBB与吊具碰撞盒是否相交，并提供**三层次检测**（Normal/Warning/Stop）和**方向感知**（前/后/左/右）的碰撞状态。

### 三层次碰撞检测

**检测区域定义**：

```
每个吊具部分（上吊具、下吊具、集装箱）都有3个等级的OBB：

Level 0 (Normal):   base_size + gSExpandSize    // 最小扩展
Level 1 (Warning):  base_size + gWExpandSize    // 中等扩展
Level 2 (Stop):     base_size + max_expansion   // 最大扩展
```

**检测优先级**：Stop > Warning > Normal

### OBB相交测试（Separating Axis Theorem）

**理论基础**：两个OBB不相交 ⇔ 存在一个分离轴，使得两个OBB在该轴上的投影不重叠。

**测试轴**：

1. OBB1的3个主轴
2. OBB2的3个主轴
3. 两个OBB主轴的叉积（9个）

**实现**：调用`IsBoxInBox(obstacle_OBB, spreader_OBB)`

### 检测算法的代码实现

**函数签名**：

```cpp
void LCPS::collisionCheck(
    const Eigen::Vector3d& sprTargetCenter,
    const std::vector<std::shared_ptr<OBBox>>& vObsOBB,
    const std::vector<std::shared_ptr<OBBox>>& vSprUpperOBB,  // 3 levels
    const std::vector<std::shared_ptr<OBBox>>& vSprLowerOBB,  // 3 levels
    const std::vector<std::shared_ptr<OBBox>>& vSprCntrOBB,   // 3 levels
    uint8_t& status,
    uint8_t& collisionStatus,
    std::vector<uint8_t>& vOBBStatus,
    std::array<uint8_t, 4>& vSprStatus,
    const uint8_t& motionMode);
```

**实现位置**：`src/service/LCPS/LCPS.cpp:850-914`

**核心逻辑**：

```cpp
void LCPS::collisionCheck(...) {
  // 初始化
  status = SPR_CTRL_SAFE;
  collisionStatus = 0x00;  // 8-bit掩码
  vOBBStatus.assign(vObsOBB.size(), SPR_CTRL_SAFE);
  vSprStatus.fill(SPR_CTRL_SAFE);

  bool bStop = false;

  // 遍历所有障碍物OBB
  for (size_t i = 0; i < vObsOBB.size(); ++i) {
    std::shared_ptr<OBBox> pObsOBB = vObsOBB[i];

    // ===== STOP级别测试 =====
    if (IsBoxInBox(pObsOBB, vSprUpperOBB[SPR_BOX_STOP]) ||
        IsBoxInBox(pObsOBB, vSprLowerOBB[SPR_BOX_STOP]) ||
        (!vSprCntrOBB.empty() && IsBoxInBox(pObsOBB, vSprCntrOBB[SPR_BOX_STOP]))) {

      bStop = true;
      vOBBStatus[i] = SPR_CTRL_STOP;
      status = SPR_CTRL_STOP;

      // 更新吊具盒状态
      if (IsBoxInBox(pObsOBB, vSprUpperOBB[SPR_BOX_STOP]))
        vSprStatus[0] = SPR_CTRL_STOP;
      if (IsBoxInBox(pObsOBB, vSprLowerOBB[SPR_BOX_STOP]))
        vSprStatus[1] = SPR_CTRL_STOP;
      if (!vSprCntrOBB.empty() && IsBoxInBox(pObsOBB, vSprCntrOBB[SPR_BOX_STOP]))
        vSprStatus[2] = SPR_CTRL_STOP;
    }

    // ===== WARNING级别测试（仅在非STOP时） =====
    if (!bStop &&
        (IsBoxInBox(pObsOBB, vSprUpperOBB[SPR_BOX_WARNING]) ||
         IsBoxInBox(pObsOBB, vSprLowerOBB[SPR_BOX_WARNING]) ||
         (!vSprCntrOBB.empty() && IsBoxInBox(pObsOBB, vSprCntrOBB[SPR_BOX_WARNING])))) {

      vOBBStatus[i] = SPR_CTRL_WARNING;
      if (status != SPR_CTRL_STOP) {
        status = SPR_CTRL_WARNING;
      }

      // ===== 方向判断 =====
      // 获取障碍物中心和吊具目标中心
      Eigen::Vector3f obsCenter = pObsOBB->center();
      Eigen::Vector3f sprCenter = sprTargetCenter.cast<float>();

      // 小车方向（X轴）偏移
      float troCenterDiff = obsCenter[0] - sprCenter[0];
      if (troCenterDiff < -0.1f) {
        collisionStatus |= (1 << PLC_BACK);   // Bit 3
      } else if (troCenterDiff > 0.1f) {
        collisionStatus |= (1 << PLC_FRONT);  // Bit 2
      }

      // 大车方向（Y轴）偏移
      float ganCenterDiff = obsCenter[1] - sprCenter[1];
      if (ganCenterDiff < -0.1f) {
        collisionStatus |= (1 << PLC_LEFT);   // Bit 6
      } else if (ganCenterDiff > 0.1f) {
        collisionStatus |= (1 << PLC_RIGHT);  // Bit 7
      }

      // 更新吊具盒状态
      if (IsBoxInBox(pObsOBB, vSprUpperOBB[SPR_BOX_WARNING]))
        vSprStatus[0] = SPR_CTRL_WARNING;
      if (IsBoxInBox(pObsOBB, vSprLowerOBB[SPR_BOX_WARNING]))
        vSprStatus[1] = SPR_CTRL_WARNING;
      if (!vSprCntrOBB.empty() && IsBoxInBox(pObsOBB, vSprCntrOBB[SPR_BOX_WARNING]))
        vSprStatus[2] = SPR_CTRL_WARNING;
    }
  }
}
```

### 方向碰撞位掩码（PLC协议）

**8位状态字节**：

```
Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0
RIGHT | LEFT  | ---   | ---   | BACK  | FRONT | ---   | ---

对应PLC_BIT枚举：
  PLC_SAFE = 0   (无碰撞)
  PLC_FRONT = 2  (前方障碍物)
  PLC_BACK = 3   (后方障碍物)
  PLC_LEFT = 6   (左侧障碍物)
  PLC_RIGHT = 7  (右侧障碍物)
```

**设置方式**：

```cpp
collisionStatus |= (1 << PLC_FRONT);  // 设置Bit 2
collisionStatus |= (1 << PLC_BACK);   // 设置Bit 3
collisionStatus |= (1 << PLC_LEFT);   // 设置Bit 6
collisionStatus |= (1 << PLC_RIGHT);  // 设置Bit 7
```

**方向判断阈值**：0.1m（中心偏移）

### 吊具碰撞盒构建

**函数签名**：

```cpp
bool LCPS::constructSprBox(
    uint8_t motionMode, const MM_SPR_POSE& pose,
    const Eigen::Vector3d& sprCntrCenter,
    const std::vector<Eigen::Vector3d>& vSprBoxSize,
    int8_t cntrHeightType, int8_t cntrLengthType,
    const MM_SPREADER_STATUS& sprStatus,
    std::vector<std::shared_ptr<OBBox>>& vSprUpperOBB,
    std::vector<std::shared_ptr<OBBox>>& vSprLowerOBB,
    std::vector<std::shared_ptr<OBBox>>& vSprCntrOBB);
```

**核心逻辑**：

```cpp
bool LCPS::constructSprBox(...) {
  // 清空输出
  vSprUpperOBB.resize(3);
  vSprLowerOBB.resize(3);
  vSprCntrOBB.resize(sprStatus.is_locked ? 3 : 0);

  // 获取变换矩阵
  EuclidTransform upperTrans = pose.Trans(MM_SPR_POSE::SCP::UPPER);
  EuclidTransform lowerTrans = pose.Trans(MM_SPR_POSE::SCP::LOWER);
  EuclidTransform cntrTrans = pose.Trans(MM_SPR_POSE::SCP::CNTR);

  // 对3个等级分别构建OBB
  for (int level = 0; level < 3; ++level) {
    // 计算扩展后的尺寸
    Eigen::Vector3d expandedSize;
    if (level == SPR_BOX_STOP) {
      expandedSize = vSprBoxSize[level] + gSExpandSize +
                     calcAsymmetricExpansion(motionMode, STOP) +
                     mvSpreaderFrameExpand;
    } else if (level == SPR_BOX_WARNING) {
      expandedSize = vSprBoxSize[level] + gWExpandSize +
                     calcAsymmetricExpansion(motionMode, WARNING) +
                     mvSpreaderFrameExpand;
    } else {
      expandedSize = vSprBoxSize[level];
    }

    // 构建上吊具OBB
    constructOBB(upperTrans.rotation(), upperTrans.translation(),
                 expandedSize / 2.0, vSprUpperOBB[level]);

    // 构建下吊具OBB
    constructOBB(lowerTrans.rotation(), lowerTrans.translation(),
                 expandedSize / 2.0, vSprLowerOBB[level]);

    // 构建集装箱OBB（如果锁箱）
    if (sprStatus.is_locked) {
      Eigen::Vector3d cntrExpandedSize;
      if (level == SPR_BOX_STOP) {
        cntrExpandedSize = vSprBoxSize[level] + gCntrSExpandSize;
      } else if (level == SPR_BOX_WARNING) {
        cntrExpandedSize = vSprBoxSize[level] + gCntrWExpandSize;
      } else {
        cntrExpandedSize = vSprBoxSize[level];
      }

      constructOBB(cntrTrans.rotation(), sprCntrCenter,
                   cntrExpandedSize / 2.0, vSprCntrOBB[level]);
    }
  }

  return true;
}
```

### 检测算法的应用场景示例

**场景1：前方出现集装箱障碍**

```
障碍物OBB：center = (10.5, 0, 0), size = (2.4, 2.4, 2.6)
吊具目标中心：sprTargetCenter = (10.0, 0, 0)

碰撞检测：
  1. STOP级别测试：IsBoxInBox(obstacle, vSprLowerOBB[STOP]) = false
  2. WARNING级别测试：IsBoxInBox(obstacle, vSprLowerOBB[WARNING]) = true

方向判断：
  troCenterDiff = 10.5 - 10.0 = 0.5 > 0.1 → 前方障碍
  collisionStatus |= (1 << 2) = 0x04

输出：
  status = SPR_CTRL_WARNING
  collisionStatus = 0x04 (Bit 2: FRONT)
```

**场景2：左侧和后方同时有障碍**

```
障碍物1：center = (9.8, -0.5, 0) → 后方+左侧
障碍物2：center = (9.7, 0.3, 0) → 后方+右侧

方向判断：
  障碍物1：
    troCenterDiff = 9.8 - 10.0 = -0.2 < -0.1 → 后方
    ganCenterDiff = -0.5 - 0 = -0.5 < -0.1 → 左侧
    collisionStatus |= (1 << 3) | (1 << 6) = 0x48

  障碍物2：
    troCenterDiff = 9.7 - 10.0 = -0.3 < -0.1 → 后方
    ganCenterDiff = 0.3 - 0 = 0.3 > 0.1 → 右侧
    collisionStatus |= (1 << 3) | (1 << 7) = 0x88

最终：collisionStatus = 0x48 | 0x88 = 0xC8 (后+左+右)
```

### 检测算法的技术亮点

1. **三层次检测**：Normal/Warning/Stop分级响应
2. **方向感知**：4方向位掩码，直接映射PLC控制
3. **几何精确**：基于OBB的精确相交测试
4. **性能优化**：Stop优先，减少不必要的Warning测试

---

## 算法4: 安全决策滤波（Safety Decision Filtering）

### 滤波算法的设计目标

通过**滑动窗口多数表决**机制，过滤传感器噪声和瞬态误检，提供稳定的安全控制指令，避免龙门吊控制系统的频繁抖动。

### 滤波算法的原理

**问题**：单帧检测结果可能受传感器噪声、短暂遮挡、边界抖动影响，导致SAFE↔WARNING↔STOP频繁切换。

**解决**：使用固定长度的循环缓冲区存储最近N帧的检测结果，通过多数表决确定最终状态。

### 多数表决逻辑

**表决规则**：

```
1. STOP阈值：stopSize > 1
   → 窗口内至少2次STOP检测 → 输出STOP
   原理：对关键碰撞快速响应
   效果：避免单帧假STOP告警

2. WARNING阈值：totalSize > capacity/2 OR warningSize > capacity/2
   → 窗口内多数为WARNING或WARNING+STOP → 输出WARNING
   原理：WARNING级威胁的多数表决
   效果：允许临时安全间隙而不清除WARNING

3. SAFE默认：未达到上述阈值 → 输出SAFE
   原理：保守策略，默认安全
   效果：慢速SAFE恢复，防止过早解除警告
```

### 滤波算法的代码实现

**函数签名**：

```cpp
void LCPS::safetyDecision(int8_t motionMode,
                          uint8_t curSafetyStatus,
                          MM_SAFETY_STATUS& filteredSafetyStatus);
```

**实现位置**：`src/service/LCPS/LCPS.cpp:1059-1126`

**核心逻辑**：

```cpp
void LCPS::safetyDecision(int8_t motionMode, uint8_t curSafetyStatus,
                          MM_SAFETY_STATUS& filteredSafetyStatus) {

  // Step 1: 将当前帧状态推入循环缓冲区
  mCandiResultCb.push_back(curSafetyStatus);

  // Step 2: 如果滤波启用且缓冲区已满，执行表决
  if (mbFilter && mCandiResultCb.full()) {

    // 统计窗口内各状态数量
    size_t warningSize = 0;
    size_t stopSize = 0;

    for (uint8_t result : mCandiResultCb) {
      if (result == SPR_CTRL_STOP) {
        stopSize++;
      } else if (result == SPR_CTRL_WARNING) {
        warningSize++;
      }
    }

    size_t totalSize = warningSize + stopSize;
    size_t capacity = mCandiResultCb.capacity();

    // Step 3: 应用表决规则
    if (stopSize > 1) {
      // 规则1：至少2次STOP → 立即STOP
      filteredSafetyStatus = SAFETY_STATUS_STOP;
    } else if (totalSize > capacity / 2 || warningSize > capacity / 2) {
      // 规则2：多数为WARNING或总非SAFE数 > 50% → WARNING
      filteredSafetyStatus = SAFETY_STATUS_WARNING;
    } else {
      // 规则3：默认SAFE
      filteredSafetyStatus = SAFETY_STATUS_SAFE;
    }

  } else if (!mbFilter) {
    // 滤波关闭：直接透传
    filteredSafetyStatus = (MM_SAFETY_STATUS)curSafetyStatus;
  } else {
    // 缓冲区未满：等待预热，透传当前状态
    filteredSafetyStatus = (MM_SAFETY_STATUS)curSafetyStatus;
  }

  // Step 4: 记录日志
  if (motionMode == LAND_MODE) {
    MM_INFO("[LCPS_FLOW_WINDOW][L: %ld] --- %d landing", mFrameIdx, filteredSafetyStatus);
  } else {
    MM_INFO("[LCPS_FLOW_WINDOW][L: %ld] --- %d lifting", mFrameIdx, filteredSafetyStatus);
  }
}
```

### 循环缓冲区

**类型**：`boost::circular_buffer<uint8_t>`

**特性**：

* 固定容量（通常5-10帧）
* FIFO（First-In-First-Out）顺序
* 自动覆盖最旧元素

**配置**：

```cpp
mCandiResultCb.set_capacity(capacity);  // 在Init()中配置
```

### 滤波算法的效果分析

**场景1：短暂遮挡（1帧误检）**

```
输入序列：[S, S, S, S, W, S, S, S, S, S]
窗口大小：5

窗口状态变化：
  [S, S, S, S, S] → SAFE (5个SAFE)
  [S, S, S, S, W] → SAFE (1个WARNING < capacity/2)
  [S, S, S, W, S] → SAFE (1个WARNING)
  [S, S, W, S, S] → SAFE (1个WARNING)
  [S, W, S, S, S] → SAFE (1个WARNING)
  [W, S, S, S, S] → SAFE (1个WARNING)
  [S, S, S, S, S] → SAFE (0个WARNING)

结果：单帧WARNING被滤除，输出始终为SAFE
```

**场景2：持续WARNING（连续3帧）**

```
输入序列：[S, S, W, W, W, W, S, S, S, S]
窗口大小：5

窗口状态变化：
  [S, S, S, S, S] → SAFE
  [S, S, S, S, W] → SAFE (1 < 5/2)
  [S, S, S, W, W] → SAFE (2 < 5/2)
  [S, S, W, W, W] → WARNING (3 > 5/2) ✅
  [S, W, W, W, W] → WARNING (4 > 5/2)
  [W, W, W, W, S] → WARNING (4 > 5/2)
  [W, W, W, S, S] → WARNING (3 > 5/2)
  [W, W, S, S, S] → SAFE (2 < 5/2)
  [W, S, S, S, S] → SAFE (1 < 5/2)
  [S, S, S, S, S] → SAFE

结果：持续WARNING被识别并输出，恢复SAFE需要2帧
```

**场景3：单次STOP（立即触发）**

```
输入序列：[S, S, S, S, T, S, S, S, S, S]
窗口大小：5

窗口状态变化：
  [S, S, S, S, S] → SAFE
  [S, S, S, S, T] → SAFE (stopSize=1, 不满足 >1)
  [S, S, S, T, S] → SAFE (stopSize=1)
  [S, S, T, S, S] → SAFE (stopSize=1)
  [S, T, S, S, S] → SAFE (stopSize=1)
  [T, S, S, S, S] → SAFE (stopSize=1)

结果：单次STOP不触发（需要至少2次）

改进建议：如果单次STOP足以构成危险，应降低阈值为 stopSize >= 1
```

**场景4：连续STOP（紧急停止）**

```
输入序列：[S, S, S, T, T, T, S, S, S, S]
窗口大小：5

窗口状态变化：
  [S, S, S, S, S] → SAFE
  [S, S, S, S, T] → SAFE (stopSize=1)
  [S, S, S, T, T] → STOP (stopSize=2 > 1) ✅
  [S, S, T, T, T] → STOP (stopSize=3 > 1)
  [S, T, T, T, S] → STOP (stopSize=3 > 1)
  [T, T, T, S, S] → STOP (stopSize=3 > 1)
  [T, T, S, S, S] → STOP (stopSize=2 > 1)
  [T, S, S, S, S] → SAFE (stopSize=1)
  [S, S, S, S, S] → SAFE

结果：2次以上连续STOP立即触发，恢复SAFE需要4帧
```

### 参数配置建议

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **窗口大小** | 5-10帧 | 越大越稳定，但响应延迟增加 |
| **STOP阈值** | stopSize > 1 | 至少2次STOP触发紧急停止 |
| **WARNING阈值** | totalSize > capacity/2 | 多数表决原则 |
| **启用滤波** | true | 建议始终启用，除非调试 |

### 响应延迟分析

**定义**：从实际碰撞发生到输出STOP指令的时间。

**计算**：

```
延迟 = (阈值 - 1) × 帧周期

示例（60Hz，stopSize > 1）：
  阈值 = 2
  帧周期 = 1/60 ≈ 16.7ms
  延迟 = (2 - 1) × 16.7ms = 16.7ms
```

**权衡**：

* **阈值越低**：响应越快，但误触发风险增加
* **阈值越高**：误触发减少，但紧急停止延迟增加

**建议**：STOP阈值应尽可能低（建议1或2），WARNING阈值可适当提高（3-5）。

### 滤波算法的技术亮点

1. **循环缓冲区**：固定内存，无动态分配
2. **多数表决**：鲁棒的统计方法
3. **快速STOP响应**：低阈值（>1）
4. **慢速SAFE恢复**：防止过早解除警告
5. **可配置阈值**：适应不同场景需求

---

## 算法集成与协同

### 算法调用顺序（processFrame中）

```
1. updateExpandSize(speed)           # 动态边界框扩展
     ↓
2. refinePosition(pos, ...)          # 多源位置融合
     ↓
3. constructSprBox(...)              # 构建吊具碰撞盒（使用扩展尺寸）
     ↓
4. collisionCheck(...)               # 碰撞检测（OBB相交测试）
     ↓
5. safetyDecision(curStatus, ...)    # 决策滤波（时间域滑动窗口）
     ↓
6. notifySafety(filteredStatus)      # 输出安全指令到PLC
```

### 算法依赖关系

```
位置融合 ────→ 相对偏移计算 ────→ 障碍物OBB更新
     │                                  │
     └───────────────────────────────────┘
                     │
                     ↓
         边界框扩展 ←──── 速度
                     │
                     ↓
              吊具碰撞盒构建
                     │
                     ↓
               碰撞检测
                     │
                     ↓
               决策滤波
                     │
                     ↓
              安全指令输出
```

---

## 参数调优指南

### 动态扩展参数

**调优目标**：在保证安全的前提下，最小化误报率。

**步骤**：

1. 确定刹车减速度（通过实际测试）
2. 调整速度阈值（匹配实际作业速度分布）
3. 调整扩展系数（平衡安全区大小）

**测试方法**：

```bash
# 记录实际刹车过程
速度: 0.8 m/s → 0 m/s
时间: 1.5s
距离: 0.6m

计算减速度:
  a = v / t = 0.8 / 1.5 = 0.53 m/s²

验证刹车距离:
  S_理论 = 0.5 * (0.8 / 0.53) * 0.8 + 0.8 + 0.2 = 1.604 m
  S_实际 = 0.6m

结论：实际刹车效果好于理论，可适当降低扩展系数
```

### 位置融合参数

**调优目标**：提高定位精度和传感器容错能力。

**步骤**：

1. 启用单个传感器，记录波动半径
2. 启用多传感器融合，对比精度提升
3. 调整异常值检测阈值（2σ → 3σ或固定阈值）

**测试方法**：

```bash
# 静止状态下记录10秒位置数据
Encoder: x=10.0±0.01, y=5.0±0.02
GNSS:    x=10.02±0.05, y=5.01±0.03
SLAM:    x=9.98±0.08, y=5.00±0.04

融合结果: x=10.00±0.03, y=5.00±0.02

精度提升: 30% (GNSS) → 70% (融合)
```

### 决策滤波参数

**调优目标**：平衡响应速度和稳定性。

**步骤**：

1. 从小窗口开始（capacity=3）
2. 逐步增大窗口，观察误报率变化
3. 调整STOP/WARNING阈值

**测试方法**：

```bash
# 记录1分钟检测数据
原始检测: 3600帧，误检率 5%（180次）
窗口=5:   误检率 2%（72次）
窗口=7:   误检率 1%（36次）
窗口=10:  误检率 0.5%（18次），但响应延迟增加

建议：窗口=7，平衡误检率和响应延迟
```

---

## 总结

LCPS的四大核心算法紧密协作，形成完整的碰撞预防闭环：

1. **动态扩展**：物理模型驱动，速度自适应
2. **位置融合**：多源传感器鲁棒定位
3. **碰撞检测**：精确几何测试，三层次分级
4. **决策滤波**：时间域滑动窗口，减少误报

这些算法共同保障了LCPS系统的**实时性、准确性和鲁棒性**，在自动化码头中发挥关键的安全防护作用。

---

**文档维护**：本文档基于代码实现分析生成，算法公式和参数与代码保持一致。代码更新时请同步更新文档。
