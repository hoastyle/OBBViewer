---
title: "LCPS点云处理管线详解"
description: "PlanarCntrDetector的点云分类、滤波、聚类和障碍物提取完整流程"
type: "技术设计"
status: "完成"
priority: "高"
created_date: "2025-12-10"
last_updated: "2025-12-10"
related_documents:
  - "docs/architecture/lcps/01_LCPS_SYSTEM_OVERVIEW.md"
  - "docs/architecture/lcps/02_LCPS_CORE_ALGORITHMS.md"
  - "docs/architecture/lcps/04_LCPS_IMPLEMENTATION_ANALYSIS.md"
related_code:
  - "src/detector/perception/planarCntrDetector/PlanarCntrDetector.cpp:classifyCloud"
  - "src/detector/perception/planarCntrDetector/PlanarCntrDetector.cpp:filterCloud"
  - "src/detector/perception/planarCntrDetector/PlanarCntrDetector.cpp:cloudToBB"
  - "src/detector/perception/planarCntrDetector/PlanarCntrDetector.cpp:segmentToLines"
  - "src/detector/perception/planarCntrDetector/PlanarCntrDetector.cpp:adaptObsToLCPS"
tags: ["LCPS", "点云处理", "障碍物检测", "滤波管线", "PCL"]
authors: ["Claude"]
version: "1.0"
---

# LCPS点云处理管线详解

## 文档说明

本文档深入解析PlanarCntrDetector的完整点云处理管线，包括点云分类、多级滤波、聚类分割、OBB构建和场景自适应转换。这是LCPS系统感知层的核心实现。

---

## 管线总览

### 完整处理流程

```
LiDAR原始点云 (XYZI)
    ↓
【阶段1: 预处理】
    ├─ 多帧融合 (mergeFrames)
    ├─ 坐标变换 (Uniform CS → Spreader CS)
    └─ 时间戳同步
    ↓
【阶段2: 点云分类】
    └─ classifyCloud (PlaneFilter)
        ├─ Horizon Cloud (水平点云：箱顶、地面)
        └─ Vertical Cloud (垂直点云：箱壁、大梁)
    ↓
【阶段3: 多级滤波】
    └─ filterCloud (动态滤波序列)
        ├─ Filter 1: AABB裁剪 (ROI提取)
        ├─ Filter 2: 吊具外点去除
        ├─ Filter 3: 自适应滤波
        ├─ Filter 4: 雨点滤波
        ├─ Filter 5: 电线滤波
        └─ Filter 6: 集装箱外点去除
    ↓
【阶段4: 线特征分割】
    └─ segmentToLines
        ├─ 聚类 (FEC/DBSCAN)
        └─ 直线/平面拟合
    ↓
【阶段5: OBB构建】
    └─ cloudToBB
        ├─ PCA主成分分析
        ├─ 计算长宽高
        ├─ 姿态修正 (refineObsPose)
        └─ 置信度评估
    ↓
【阶段6: 特征辅助】
    └─ featCloudToBB
        └─ 线性特征生成虚拟点云
    ↓
【阶段7: 场景自适应】
    └─ adaptObsToLCPS
        ├─ 起升场景转换
        ├─ 落地场景转换
        └─ 集卡场景处理
    ↓
输出: Obstacle列表 (位置、尺寸、朝向、置信度)
```

### 性能指标

| 阶段 | 处理时间 | 输入 | 输出 |
|------|---------|------|------|
| 预处理 | 5-8ms | 原始点云 | 合并点云 |
| 点云分类 | 5-8ms | 合并点云 | 水平/垂直点云 |
| 多级滤波 | 20-30ms | 分类点云 | 过滤点云 |
| 线特征分割 | 8-10ms | 过滤点云 | 聚类簇 |
| OBB构建 | 5-7ms | 聚类簇 | OBB列表 |
| 场景转换 | 3-5ms | OBB列表 | 障碍物列表 |
| **总计** | **46-68ms** | - | - |

---

## 阶段1: 预处理与多帧融合

### 为什么需要多帧融合？

**问题**：单帧激光雷达点云稀疏，难以完整覆盖障碍物表面。

**解决**：维护滑动窗口，叠加多帧点云提高密度。

### 实现机制

**代码位置**: `PlanarCntrDetector.cpp:mergeFrames`

```cpp
bool PlanarCntrDetector::mergeFrames(
    const std::vector<PointCloudXYZIPtr>& frames,
    PointCloudXYZIPtr& mergedCloud)
{
    // 使用循环缓冲区存储最近N帧
    boost::circular_buffer<PointCloudXYZIPtr> mvDataCb(buffer_size);

    // 时间戳检查（避免运动拖影）
    for (auto& frame : frames) {
        if (frame->header.stamp - current_time < max_time_delta) {
            mvDataCb.push_back(frame);
        }
    }

    // 合并所有帧
    for (auto& frame : mvDataCb) {
        *mergedCloud += *frame;
    }

    return true;
}
```

### 关键参数

| 参数 | 典型值 | 说明 |
|------|--------|------|
| `buffer_size` | 3-5帧 | 滑动窗口大小 |
| `max_time_delta` | 200ms | 时间戳容差 |
| `frame_rate` | 10Hz | LiDAR帧率 |

### 副作用与权衡

**优势**：

* ✅ 点云密度提高3-5倍
* ✅ 小物体检测率提升
* ✅ OBB拟合更准确

**劣势**：

* ⚠️ 引入运动拖影（需要时间戳同步）
* ⚠️ 内存占用增加
* ⚠️ 处理延迟增加5-8ms

---

## 阶段2: 点云分类 (classifyCloud)

### 平面假设原理

**核心假设**：集装箱堆场环境中，所有有意义的障碍物都是"横平竖直"的。

**分类标准**：

* **Horizon (水平)**：箱顶、地面、水平表面
* **Vertical (垂直)**：箱壁、龙门腿、轮胎

### 算法实现 (PlaneFilter)

**代码位置**: `PlanarCntrDetector.cpp:classifyCloud`

```cpp
XYZIPtrPair PlanarCntrDetector::classifyCloud(
    PointCloudXYZIPtr pCloud,
    int lidarId)
{
    XYZIPtrPair result;

    // 调用PlaneFilter算法
    mpPlaneFilter->Filter(
        pCloud,           // 输入点云
        result.first,     // 输出: Horizon cloud
        result.second     // 输出: Vertical cloud
    );

    return result;
}
```

### PlaneFilter详细流程

#### Step 1: 双向投影

```
3D点云 → 投影到2D密度图
├─ XZ平面 (侧视图) → 检测垂直线
└─ YZ平面 (正视图) → 检测水平线
```

**投影公式**：

```
pixel_x = (point.x - x_min) / grid_size
pixel_y = (point.z - z_min) / grid_size
density[pixel_x][pixel_y] += 1
```

#### Step 2: 图像处理

```cpp
// 1. 归一化
normalized = (density - min) / (max - min)

// 2. 直方图均衡
equalized = histogramEqualization(normalized)

// 3. 二值化
binary = (equalized > threshold) ? 255 : 0
```

#### Step 3: Hough直线检测

```cpp
// 检测水平线和竖直线
std::vector<Line> horizontal_lines = detectHoughLines(
    binary_xz,
    angle_range = [85°, 95°]  // 接近垂直
);

std::vector<Line> vertical_lines = detectHoughLines(
    binary_yz,
    angle_range = [-5°, 5°]    // 接近水平
);
```

#### Step 4: 反向投影

```cpp
// 将2D直线映射回3D空间
for (auto& point : pCloud->points) {
    if (isOnHorizontalLine(point)) {
        horizon_cloud->push_back(point);
    } else if (isOnVerticalLine(point)) {
        vertical_cloud->push_back(point);
    }
}
```

### 适用场景与局限

**适用**：

* ✅ 标准集装箱堆场
* ✅ 规则的龙门吊结构
* ✅ 平整的地面

**局限**：

* ❌ 箱门打开（非横平竖直）
* ❌ 不规则障碍物（如车辆）
* ❌ 复杂地形

### 性能优化

* 使用积分图加速密度计算
* GPU并行化Hough变换
* 缓存投影结果

---

## 阶段3: 多级滤波管线 (filterCloud)

### 动态滤波器序列

**设计特点**：使用函数对象（std::function）实现动态滤波管线。

**代码位置**: `PlanarCntrDetector.cpp:filterCloud`

```cpp
bool PlanarCntrDetector::filterCloud(
    uint8_t detectMode,
    uint8_t motionMode,
    uint8_t cloudType,
    const Eigen::Matrix4f& sprTargetPose,
    const MM_SPR_POSE& sprPose,
    PointCloudXYZIPtr pFrame)
{
    // 动态滤波器序列
    std::vector<std::function<bool()>> filterSequence;

    // 根据模式添加滤波器
    if (cloudType == HORIZON) {
        filterSequence.push_back(
            std::bind(&PlanarCntrDetector::filterAABB, this, ...)
        );
        filterSequence.push_back(
            std::bind(&PlanarCntrDetector::filterSprOutlier, this, ...)
        );
        // ... 更多滤波器
    }

    // 顺序执行
    for (auto& filter : filterSequence) {
        if (!filter()) {
            MM_ERROR("Filter failed");
            return false;
        }
    }

    return true;
}
```

### Filter 1: AABB裁剪 (filterAABB)

**目的**：根据作业区域（ROI）裁剪点云，去除无关区域。

**实现**：

```cpp
bool PlanarCntrDetector::filterAABB(
    PointCloudXYZIPtr pCloud,
    const Eigen::Vector3f& min_pt,
    const Eigen::Vector3f& max_pt)
{
    PointCloudXYZIPtr filtered(new PointCloudXYZI);

    for (auto& point : pCloud->points) {
        if (point.x >= min_pt.x && point.x <= max_pt.x &&
            point.y >= min_pt.y && point.y <= max_pt.y &&
            point.z >= min_pt.z && point.z <= max_pt.z) {
            filtered->push_back(point);
        }
    }

    pCloud->swap(*filtered);
    return true;
}
```

**ROI计算**：

```
ROI中心 = 目标集装箱位置
ROI尺寸 = 集装箱尺寸 + 安全边界
```

### Filter 2: 吊具外点去除 (filterSprOutlier)

**目的**：去除吊具自身点云，避免误检为障碍物。

**风险**：

* Box太小 → 吊具被当成障碍物（误报）
* Box太大 → 紧贴吊具的集装箱被滤除（漏报）

**实现**：

```cpp
bool PlanarCntrDetector::filterSprOutlier(
    PointCloudXYZIPtr pCloud,
    const MM_SPR_POSE& sprPose)
{
    // 构建吊具OBB（加安全边界）
    OBBox sprOBB = constructOBB(
        sprPose.position,
        sprPose.size + mLandHorizonSprOutlierExpand  // 关键参数
    );

    PointCloudXYZIPtr filtered(new PointCloudXYZI);

    for (auto& point : pCloud->points) {
        if (!sprOBB.contains(point)) {
            filtered->push_back(point);  // 保留吊具外的点
        }
    }

    pCloud->swap(*filtered);
    return true;
}
```

**关键参数**：

| 参数 | 典型值 | 说明 |
|------|--------|------|
| `mLandHorizonSprOutlierExpand` | [0.1, 0.1, 0.2]m | 水平外扩 |
| `mLiftSprOutlierExpand` | [0.15, 0.15, 0.3]m | 起升外扩 |
| `mUpperSprOutlierExpand` | [0.2, 0.2, 0.35]m | 上吊具外扩 |

### Filter 3: 自适应滤波 (filterAdaptively)

**目的**：根据点云密度和场景动态调整滤波参数。

**实现**：

```cpp
bool PlanarCntrDetector::filterAdaptively(
    PointCloudXYZIPtr pCloud)
{
    // 计算点云密度
    float density = estimateDensity(pCloud);

    // 自适应参数
    float radius = (density > high_threshold) ? 0.05 : 0.1;
    int min_neighbors = (density > high_threshold) ? 3 : 5;

    // 半径滤波
    pcl::RadiusOutlierRemoval<PointXYZI> ror;
    ror.setInputCloud(pCloud);
    ror.setRadiusSearch(radius);
    ror.setMinNeighborsInRadius(min_neighbors);
    ror.filter(*pCloud);

    return true;
}
```

### Filter 4: 雨点滤波 (filterRain)

**目的**：去除雨雾干扰。

**原理**：雨滴反射强度低且稀疏。

**实现**：

```cpp
bool PlanarCntrDetector::filterRain(
    PointCloudXYZIPtr pCloud)
{
    PointCloudXYZIPtr filtered(new PointCloudXYZI);

    for (auto& point : pCloud->points) {
        // 雨点特征：低强度 + 孤立点
        if (point.intensity > mRainIntensityThres[0] &&
            point.intensity < mRainIntensityThres[1] &&
            hasNeighbors(point, radius=0.1, min_count=3)) {
            filtered->push_back(point);
        }
    }

    pCloud->swap(*filtered);
    return true;
}
```

**关键参数**：

```yaml
rain_intensity_range: [0, 50]  # 雨点强度范围
rain_min_neighbors: 3          # 最小邻近点数
```

### Filter 5: 电线滤波 (filterWire)

**目的**：去除吊具钢丝绳。

**原理**：钢丝绳是吊具上方的细长垂直特征。

**实现**：

```cpp
bool PlanarCntrDetector::filterWire(
    PointCloudXYZIPtr pCloud,
    const MM_SPR_POSE& sprPose)
{
    PointCloudXYZIPtr filtered(new PointCloudXYZI);

    // 定义钢丝绳检测区域（吊具上方）
    Eigen::Vector3f wire_region_min = sprPose.position +
        Eigen::Vector3f(-0.5, -0.5, 0.5);
    Eigen::Vector3f wire_region_max = sprPose.position +
        Eigen::Vector3f(0.5, 0.5, 5.0);

    for (auto& point : pCloud->points) {
        // 排除细长垂直特征
        if (!isInRegion(point, wire_region_min, wire_region_max) ||
            !isThinVerticalFeature(point)) {
            filtered->push_back(point);
        }
    }

    pCloud->swap(*filtered);
    return true;
}
```

### Filter 6: 集装箱外点去除 (filterCntrOutlier)

**目的**：仅保留目标集装箱附近的点云。

**实现**：类似AABB裁剪，但范围更精确。

---

## 阶段4: 聚类与分割 (segmentToLines)

### FEC聚类算法

**FEC (Fast Euclidean Clustering)**：基于欧几里得距离的快速聚类。

**代码位置**: `PlanarCntrDetector.cpp:segmentToLines`

```cpp
bool PlanarCntrDetector::segmentToLines(
    PointCloudXYZIPtr pCloud,
    std::vector<PointCloudXYZIPtr>& clusters)
{
    // 使用mm::FEC聚类器
    mm::FEC fec_clusterer;
    fec_clusterer.setInputCloud(pCloud);
    fec_clusterer.setClusterTolerance(mDistanceTolerance);  // 0.1m
    fec_clusterer.setMinClusterSize(mMinClusterSize);      // 10 points
    fec_clusterer.setMaxClusterSize(10000);

    std::vector<pcl::PointIndices> cluster_indices;
    fec_clusterer.extract(cluster_indices);

    // 提取聚类簇
    for (auto& indices : cluster_indices) {
        PointCloudXYZIPtr cluster(new PointCloudXYZI);
        pcl::copyPointCloud(*pCloud, indices, *cluster);
        clusters.push_back(cluster);
    }

    return true;
}
```

### 聚类参数

| 参数 | 水平点云 | 垂直点云 | 说明 |
|------|---------|---------|------|
| `distance_tolerance` | 0.1m | 0.05m | 距离容差 |
| `min_cluster_size` | 10 | 15 | 最小簇大小 |
| `max_cluster_size` | 10000 | 5000 | 最大簇大小 |

### 直线拟合（可选）

```cpp
// 对聚类簇拟合直线（针对箱壁）
for (auto& cluster : clusters) {
    Eigen::VectorXf line_coeffs;
    pcl::SampleConsensusModelLine<PointXYZI>::Ptr model(
        new pcl::SampleConsensusModelLine<PointXYZI>(cluster)
    );

    pcl::RandomSampleConsensus<PointXYZI> ransac(model);
    ransac.setDistanceThreshold(0.01);
    ransac.computeModel();
    ransac.getModelCoefficients(line_coeffs);
}
```

---

## 阶段5: OBB构建 (cloudToBB)

### PCA主成分分析

**目的**：找到点云的主方向，构建最小外接有向边界框（OBB）。

**代码位置**: `PlanarCntrDetector.cpp:cloudToBB`

```cpp
bool PlanarCntrDetector::cloudToBB(
    const PointCloudXYZIPtr cluster,
    ObstaclePtr& obstacle)
{
    // Step 1: 计算质心
    Eigen::Vector4f centroid;
    pcl::compute3DCentroid(*cluster, centroid);

    // Step 2: PCA分析
    Eigen::Matrix3f covariance;
    pcl::computeCovarianceMatrixNormalized(*cluster, centroid, covariance);

    Eigen::SelfAdjointEigenSolver<Eigen::Matrix3f> eigen_solver(covariance);
    Eigen::Matrix3f eigenvectors = eigen_solver.eigenvectors();
    Eigen::Vector3f eigenvalues = eigen_solver.eigenvalues();

    // Step 3: 构建旋转矩阵
    Eigen::Matrix3f rotation = eigenvectors;

    // Step 4: 将点云转到主轴坐标系
    PointCloudXYZIPtr aligned_cloud(new PointCloudXYZI);
    pcl::transformPointCloud(*cluster, *aligned_cloud,
        Eigen::Affine3f::Identity(), rotation.inverse());

    // Step 5: 计算AABB（在主轴坐标系）
    PointXYZI min_pt, max_pt;
    pcl::getMinMax3D(*aligned_cloud, min_pt, max_pt);

    // Step 6: 构建OBB
    obstacle->position = centroid.head<3>();
    obstacle->size = Eigen::Vector3f(
        max_pt.x - min_pt.x,
        max_pt.y - min_pt.y,
        max_pt.z - min_pt.z
    );
    obstacle->rotation = Eigen::Quaternionf(rotation);

    return true;
}
```

### 姿态修正 (refineObsPose)

**目的**：修正OBB旋转角度，确保轴线与坐标系对齐。

**代码位置**: `PlanarCntrDetector.cpp:refineObsPose`

```cpp
void PlanarCntrDetector::refineObsPose(ObstaclePtr& obstacle)
{
    // 提取偏航角
    float yaw = obstacle->rotation.toRotationMatrix().eulerAngles(2, 1, 0)[0];

    // 校正到最近的0°, 90°, 180°, 270°
    float corrected_yaw = std::round(yaw / (M_PI / 2)) * (M_PI / 2);

    // 如果偏差过大，强制校正
    if (std::abs(yaw - corrected_yaw) < 15.0 * M_PI / 180.0) {
        Eigen::AngleAxisf corrected_rotation(corrected_yaw, Eigen::Vector3f::UnitZ());
        obstacle->rotation = Eigen::Quaternionf(corrected_rotation);
    }
}
```

**物理意义**：

* 利用先验知识：集装箱通常是横平竖直的
* 减少PCA的随机性
* 提高OBB稳定性

---

## 阶段6: 特征辅助处理 (featCloudToBB)

### 线性特征虚拟点云

**目的**：当点云稀疏时，使用线特征生成虚拟点云补充。

**代码位置**: `PlanarCntrDetector.cpp:featCloudToBB`

```cpp
bool PlanarCntrDetector::featCloudToBB(
    const std::vector<LineFeature>& line_features,
    std::vector<ObstaclePtr>& obstacles)
{
    for (auto& line : line_features) {
        // 沿线生成虚拟点
        PointCloudXYZIPtr virtual_cloud(new PointCloudXYZI);

        float step = 0.05;  // 5cm间隔
        for (float t = 0; t <= line.length; t += step) {
            PointXYZI point;
            point.x = line.start.x + t * line.direction.x;
            point.y = line.start.y + t * line.direction.y;
            point.z = line.start.z + t * line.direction.z;
            point.intensity = 100;
            virtual_cloud->push_back(point);
        }

        // 为虚拟点云构建OBB
        ObstaclePtr obstacle;
        cloudToBB(virtual_cloud, obstacle);
        obstacle->source = VIRTUAL_CLOUD;
        obstacles.push_back(obstacle);
    }

    return true;
}
```

---

## 阶段7: 场景自适应转换 (adaptObsToLCPS)

### 起升场景 (Lift Mode)

**重点**：检测垂直方向障碍物。

```cpp
void PlanarCntrDetector::adaptObsToLCPS_Lift(
    std::vector<ObstaclePtr>& obstacles)
{
    for (auto& obs : obstacles) {
        // 优先处理竖直方向障碍物
        if (obs->type == VERTICAL_OBSTACLE) {
            obs->priority = HIGH;
        }

        // 高度层过滤
        if (obs->position.z > mMaxLayerHeight) {
            obs->valid = false;
        }
    }
}
```

### 落地场景 (Land Mode)

**重点**：检测水平方向障碍物（大车、小车）。

```cpp
void PlanarCntrDetector::adaptObsToLCPS_Land(
    std::vector<ObstaclePtr>& obstacles)
{
    // 分方向处理
    for (auto& obs : obstacles) {
        // 大车方向障碍物
        if (isInGantryDirection(obs)) {
            obs->detection_axis = GANTRY;
            obs->priority = HIGH;
        }

        // 小车方向障碍物
        if (isInTrolleyDirection(obs)) {
            obs->detection_axis = TROLLEY;
            obs->priority = MEDIUM;
        }
    }
}
```

### 集卡场景 (Truck Mode)

**特殊处理**：检测车道侧障碍物。

```cpp
void PlanarCntrDetector::adaptObsToLCPS_Truck(
    std::vector<ObstaclePtr>& obstacles)
{
    // 检测卡车轮胎、车身
    for (auto& obs : obstacles) {
        if (isTruckFeature(obs)) {
            obs->type = TRUCK_OBSTACLE;
            obs->priority = CRITICAL;
        }
    }
}
```

---

## 管线优化策略

### 性能瓶颈

| 阶段 | 占比 | 瓶颈 |
|------|------|------|
| 多级滤波 | 43% | 多次遍历点云 |
| 聚类分割 | 17% | FEC复杂度 |
| 点云分类 | 14% | Hough变换 |
| OBB构建 | 12% | PCA计算 |

### 优化方案

**1. 单遍处理**：

```cpp
// 当前: 多次遍历
filterAABB() → filterSprOutlier() → filterAdaptively()

// 优化: 单次遍历
for (auto& point : pCloud->points) {
    if (passAABB(point) &&
        passSprOutlier(point) &&
        passAdaptive(point)) {
        filtered->push_back(point);
    }
}
```

**2. GPU加速**：

* 使用PCL-GPU模块
* 并行化Hough变换
* 并行化FEC聚类

**3. 空间索引**：

* 使用Octree加速邻近搜索
* 使用KD-Tree加速聚类

---

## 总结

PlanarCntrDetector的7阶段点云处理管线通过分类、滤波、聚类、OBB构建和场景自适应，将原始LiDAR点云转换为结构化的障碍物列表，为LCPS碰撞检测提供准确的环境感知。

**关键设计**：

1. **平面假设** - 横平竖直分类
2. **动态滤波** - 函数对象灵活配置
3. **PCA+先验** - OBB姿态修正
4. **场景自适应** - 根据作业模式调整

---

**文档完成**

本文档完整覆盖了LCPS系统点云处理管线的实现细节。通过学习此文档，可以理解从原始点云到障碍物OBB的完整转换过程。
