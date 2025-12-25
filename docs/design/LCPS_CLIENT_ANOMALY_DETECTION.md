# LCPS 异常检测规范

**版本**: 1.0
**创建日期**: 2025-12-24
**父文档**: [LCPS综合设计方案](LCPS_COMPREHENSIVE_DESIGN.md)
**状态**: 设计完成

## 目的

定义LCPS观测工具的异常检测机制，包括漏报检测、误报检测、生命周期监控等核心功能。

---

## 1. 异常分类

### 1.1 异常类型层级

```
Anomaly (异常)
├── Safety Critical (安全关键，P0)
│   ├── MissedAlert (漏报)
│   ├── LifecycleError (生命周期错误)
│   └── DataLoss (数据丢失)
├── Functional (功能异常，P1)
│   ├── FalseAlarm (误报)
│   ├── PerformanceDegradation (性能降级)
│   └── DataQuality (数据质量)
└── Informational (信息性，P2)
    ├── ConfigurationWarning (配置警告)
    └── StatisticalAnomaly (统计异常)
```

### 1.2 严重程度分级

| 级别 | 说明 | 响应时间 | 处理方式 |
|------|------|---------|---------|
| **Critical** | 安全关键，可能导致事故 | 立即 | HUD红色高亮 + 声音警告 |
| **High** | 高风险，需要立即关注 | < 5秒 | HUD橙色高亮 + 记录 |
| **Medium** | 中等风险，需要关注 | < 30秒 | HUD黄色提示 + 记录 |
| **Low** | 低风险，仅记录 | 无要求 | 仅记录到日志 |

---

## 2. 漏报检测（MissedAlertDetector）

### 2.1 检测原理

**定义**：应该产生报警但未产生报警的情况

**核心逻辑**：
```
如果满足:
  1. 危险区域内有足够的点云 AND
  2. 点云形成了明显的障碍物 AND
  3. LCPS应该激活 AND
  4. 但未生成对应的OBB或未触发报警
则判定为: 漏报
```

### 2.2 检测算法

```python
class MissedAlertDetector(AnomalyPlugin):
    """漏报检测器"""

    def __init__(self, config: dict):
        # 加载危险区域定义
        self.danger_zones = [
            DangerZone.from_dict(z) for z in config['danger_zones']
        ]
        # 最小点云数量阈值
        self.min_points_threshold = config.get('min_points', 50)
        # OBB最小置信度
        self.min_confidence = config.get('min_confidence', 0.7)

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        """执行漏报检测"""
        anomalies = []

        # 检测1: 危险区域点云密度检测
        for zone in self.danger_zones:
            result = self._check_zone_coverage(frame, zone)
            if result:
                anomalies.append(result)

        # 检测2: LCPS状态一致性检查
        lifecycle_anomaly = self._check_lifecycle(frame)
        if lifecycle_anomaly:
            anomalies.append(lifecycle_anomaly)

        # 检测3: 障碍物生成检查
        generation_anomaly = self._check_obstacle_generation(frame)
        if generation_anomaly:
            anomalies.extend(generation_anomaly)

        return anomalies

    def _check_zone_coverage(self, frame: SyncedFrame,
                            zone: DangerZone) -> Optional[Anomaly]:
        """检查危险区域覆盖"""
        if 'pointcloud' not in frame.data:
            return None

        points = frame.data['pointcloud'].points

        # 1. 过滤出区域内的点
        points_in_zone = self._filter_points_in_zone(points, zone)

        if len(points_in_zone) < self.min_points_threshold:
            return None  # 点云不足，正常

        # 2. 检查是否生成了OBB
        obbs = frame.data.get('obb', {}).get('obbs', [])
        obbs_in_zone = [
            obb for obb in obbs
            if zone.contains_point(obb.position) and
               obb.confidence >= self.min_confidence
        ]

        if len(obbs_in_zone) == 0:
            # 有点云但无OBB，疑似漏报
            return Anomaly(
                type="missed_alert",
                severity="critical",
                timestamp=frame.timestamp,
                zone_id=zone.id,
                point_count=len(points_in_zone),
                expected_obb=True,
                actual_obb=False,
                message=f"危险区域 {zone.name} 有 {len(points_in_zone)} 个点，"
                        f"但未生成OBB"
            )

        return None

    def _check_lifecycle(self, frame: SyncedFrame) -> Optional[Anomaly]:
        """检查LCPS生命周期"""
        if 'status' not in frame.data:
            return None

        status = frame.data['status']

        # 规则1: 应该激活但未激活
        if self._should_be_active(frame) and status.lcps_state != 'active':
            return Anomaly(
                type="lifecycle_error",
                severity="critical",
                timestamp=frame.timestamp,
                expected_state="active",
                actual_state=status.lcps_state,
                message=f"LCPS应激活但当前状态为 {status.lcps_state}"
            )

        # 规则2: 不应该激活但激活了（可能误报）
        if not self._should_be_active(frame) and status.lcps_state == 'active':
            return Anomaly(
                type="lifecycle_warning",
                severity="medium",
                timestamp=frame.timestamp,
                message="LCPS在无障碍物时激活"
            )

        return None

    def _should_be_active(self, frame: SyncedFrame) -> bool:
        """判断LCPS是否应该激活"""
        # 简化逻辑：有OBB或有足够点云即应激活
        obbs = frame.data.get('obb', {}).get('obbs', [])
        if len(obbs) > 0:
            return True

        if 'pointcloud' in frame.data:
            # 检查任意危险区域是否有点云
            points = frame.data['pointcloud'].points
            for zone in self.danger_zones:
                if len(self._filter_points_in_zone(points, zone)) > self.min_points_threshold:
                    return True

        return False

    def _filter_points_in_zone(self, points: np.ndarray,
                               zone: DangerZone) -> np.ndarray:
        """过滤出区域内的点"""
        # 使用zone的边界框进行快速过滤
        mask = (
            (points[:, 0] >= zone.min_x) & (points[:, 0] <= zone.max_x) &
            (points[:, 1] >= zone.min_y) & (points[:, 1] <= zone.max_y) &
            (points[:, 2] >= zone.min_z) & (points[:, 2] <= zone.max_z)
        )
        return points[mask]
```

### 2.3 配置示例

```yaml
# anomaly_detection_config.yaml
missed_alert:
  enabled: true
  danger_zones:
    - id: "zone_001"
      name: "前方危险区"
      type: "box"  # box, cylinder, polygon
      min_x: -2.0
      max_x: 2.0
      min_y: 0.0
      max_y: 5.0
      min_z: 0.0
      max_z: 3.0
    - id: "zone_002"
      name: "侧方危险区"
      type: "box"
      min_x: 2.0
      max_x: 5.0
      min_y: -1.0
      max_y: 1.0
      min_z: 0.0
      max_z: 3.0
  min_points: 50
  min_confidence: 0.7
```

---

## 3. 误报检测（FalseAlarmDetector）

### 3.1 检测原理

**定义**：不应该产生报警但产生了报警的情况

**核心逻辑**：
```
如果满足:
  1. 生成了OBB BUT
  2. OBB周围没有足够的点云支持 OR
  3. 点云分布不合理（过于稀疏/离散）OR
  4. 报警频率异常高
则判定为: 误报
```

### 3.2 检测算法

```python
class FalseAlarmDetector(AnomalyPlugin):
    """误报检测器"""

    def __init__(self, config: dict):
        self.min_support_points = config.get('min_support_points', 20)
        self.support_radius = config.get('support_radius', 1.0)  # 米
        self.max_alert_frequency = config.get('max_alert_freq', 10)  # Hz
        self.alert_history = deque(maxlen=100)

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        anomalies = []

        # 检测1: OBB与点云一致性检查
        consistency_anomalies = self._check_obb_pointcloud_consistency(frame)
        anomalies.extend(consistency_anomalies)

        # 检测2: 报警频率检查
        frequency_anomaly = self._check_alert_frequency(frame)
        if frequency_anomaly:
            anomalies.append(frequency_anomaly)

        # 检测3: 空间一致性检查
        spatial_anomalies = self._check_spatial_consistency(frame)
        anomalies.extend(spatial_anomalies)

        return anomalies

    def _check_obb_pointcloud_consistency(self,
                                         frame: SyncedFrame) -> List[Anomaly]:
        """检查OBB与点云的一致性"""
        if 'obb' not in frame.data or 'pointcloud' not in frame.data:
            return []

        anomalies = []
        obbs = frame.data['obb'].obbs
        points = frame.data['pointcloud'].points

        for obb in obbs:
            # 获取OBB周围的点云
            points_near_obb = self._get_points_near_obb(
                points, obb, radius=self.support_radius
            )

            if len(points_near_obb) < self.min_support_points:
                anomalies.append(Anomaly(
                    type="false_alarm",
                    severity="medium",
                    timestamp=frame.timestamp,
                    obb_id=obb.id,
                    support_points=len(points_near_obb),
                    required_points=self.min_support_points,
                    message=f"OBB {obb.id} 仅有 {len(points_near_obb)} 个支持点"
                ))

            # 进一步检查：点云分布是否合理
            if len(points_near_obb) >= self.min_support_points:
                density = self._calculate_density(points_near_obb)
                if density < 0.1:  # 密度过低
                    anomalies.append(Anomaly(
                        type="false_alarm_suspect",
                        severity="low",
                        timestamp=frame.timestamp,
                        obb_id=obb.id,
                        density=density,
                        message=f"OBB {obb.id} 周围点云密度过低 ({density:.3f})"
                    ))

        return anomalies

    def _check_alert_frequency(self, frame: SyncedFrame) -> Optional[Anomaly]:
        """检查报警频率"""
        if 'status' not in frame.data:
            return None

        status = frame.data['status']
        alerts = status.alerts

        # 记录报警历史
        for alert in alerts:
            self.alert_history.append({
                'timestamp': alert.timestamp,
                'type': alert.type
            })

        # 计算最近1秒的报警频率
        now = frame.timestamp
        recent_alerts = [
            a for a in self.alert_history
            if now - a['timestamp'] <= 1.0
        ]

        freq = len(recent_alerts)
        if freq > self.max_alert_frequency:
            return Anomaly(
                type="false_alarm_high_frequency",
                severity="medium",
                timestamp=frame.timestamp,
                alert_count=freq,
                threshold=self.max_alert_frequency,
                message=f"报警频率过高: {freq} Hz (阈值 {self.max_alert_frequency} Hz)"
            )

        return None

    def _get_points_near_obb(self, points: np.ndarray,
                            obb: OBB, radius: float) -> np.ndarray:
        """获取OBB周围的点"""
        center = np.array(obb.position)
        distances = np.linalg.norm(points - center, axis=1)
        return points[distances <= radius]

    def _calculate_density(self, points: np.ndarray) -> float:
        """计算点云密度（点/立方米）"""
        if len(points) == 0:
            return 0.0

        # 计算边界框体积
        min_coords = points.min(axis=0)
        max_coords = points.max(axis=0)
        volume = np.prod(max_coords - min_coords)

        if volume < 1e-6:  # 避免除以0
            return 0.0

        return len(points) / volume
```

---

## 4. 生命周期监控（LifecycleMonitor）

### 4.1 监控状态机

```
[INACTIVE] ──start──> [STARTING] ──ready──> [ACTIVE]
    ^                                            │
    │                                            │
    └──────────<───── [STOPPING] <───stop───────┘
                         │
                       error
                         │
                         v
                      [ERROR]
```

### 4.2 状态转换规则

```python
class LifecycleMonitor(AnomalyPlugin):
    """LCPS生命周期监控"""

    VALID_TRANSITIONS = {
        'inactive': ['starting'],
        'starting': ['active', 'error'],
        'active': ['stopping', 'warning', 'error'],
        'warning': ['active', 'error'],
        'stopping': ['inactive', 'error'],
        'error': ['inactive'],
        'emergency_stop': []  # 终态，需人工干预
    }

    def __init__(self):
        self.last_state = 'inactive'
        self.state_history = deque(maxlen=100)
        self.uptime_start = None

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        if 'status' not in frame.data:
            return []

        current_state = frame.data['status'].lcps_state
        anomalies = []

        # 1. 检查状态转换是否合法
        if current_state != self.last_state:
            if current_state not in self.VALID_TRANSITIONS.get(self.last_state, []):
                anomalies.append(Anomaly(
                    type="invalid_state_transition",
                    severity="high",
                    timestamp=frame.timestamp,
                    from_state=self.last_state,
                    to_state=current_state,
                    message=f"非法状态转换: {self.last_state} -> {current_state}"
                ))

            # 记录状态转换
            self.state_history.append({
                'from': self.last_state,
                'to': current_state,
                'timestamp': frame.timestamp
            })

            self.last_state = current_state

        # 2. 检查异常状态持续时间
        if current_state == 'error':
            error_duration = self._get_state_duration('error')
            if error_duration > 60:  # 错误状态持续超过60秒
                anomalies.append(Anomaly(
                    type="prolonged_error_state",
                    severity="critical",
                    timestamp=frame.timestamp,
                    duration=error_duration,
                    message=f"错误状态持续 {error_duration:.1f} 秒"
                ))

        # 3. 检查启动时间异常
        if current_state == 'starting':
            starting_duration = self._get_state_duration('starting')
            if starting_duration > 30:  # 启动超过30秒
                anomalies.append(Anomaly(
                    type="slow_startup",
                    severity="medium",
                    timestamp=frame.timestamp,
                    duration=starting_duration,
                    message=f"启动耗时过长: {starting_duration:.1f} 秒"
                ))

        # 4. 检查频繁重启
        restart_count = self._count_restarts_in_window(window=3600)  # 1小时
        if restart_count > 5:
            anomalies.append(Anomaly(
                type="frequent_restarts",
                severity="high",
                timestamp=frame.timestamp,
                restart_count=restart_count,
                message=f"最近1小时重启 {restart_count} 次"
            ))

        return anomalies

    def _get_state_duration(self, state: str) -> float:
        """获取当前状态持续时间（秒）"""
        if not self.state_history or self.last_state != state:
            return 0.0

        # 找到最近一次进入该状态的时间
        for transition in reversed(self.state_history):
            if transition['to'] == state:
                return time.time() - transition['timestamp']

        return 0.0

    def _count_restarts_in_window(self, window: float) -> int:
        """统计时间窗口内的重启次数"""
        now = time.time()
        count = 0
        for transition in self.state_history:
            if transition['to'] == 'starting' and now - transition['timestamp'] <= window:
                count += 1
        return count
```

---

## 5. 异常聚合和报告

### 5.1 异常聚合

```python
class AnomalyAggregator:
    """异常聚合器（避免重复报警）"""

    def __init__(self, dedupe_window=5.0):
        self.dedupe_window = dedupe_window  # 去重时间窗口（秒）
        self.recent_anomalies = deque(maxlen=1000)

    def aggregate(self, anomalies: List[Anomaly]) -> List[Anomaly]:
        """聚合异常，去除重复"""
        unique_anomalies = []
        now = time.time()

        for anomaly in anomalies:
            if not self._is_duplicate(anomaly, now):
                unique_anomalies.append(anomaly)
                self.recent_anomalies.append({
                    'anomaly': anomaly,
                    'timestamp': now
                })

        return unique_anomalies

    def _is_duplicate(self, anomaly: Anomaly, now: float) -> bool:
        """检查是否为重复异常"""
        for recent in self.recent_anomalies:
            if now - recent['timestamp'] > self.dedupe_window:
                continue

            # 相同类型、相同区域/对象、时间接近 → 重复
            r_anomaly = recent['anomaly']
            if (anomaly.type == r_anomaly.type and
                getattr(anomaly, 'zone_id', None) == getattr(r_anomaly, 'zone_id', None) and
                getattr(anomaly, 'obb_id', None) == getattr(r_anomaly, 'obb_id', None)):
                return True

        return False
```

### 5.2 异常报告生成

```python
class AnomalyReporter:
    """异常报告生成器"""

    def generate_report(self, anomalies: List[Anomaly],
                       start_time: float, end_time: float) -> dict:
        """生成异常分析报告"""
        report = {
            'summary': {
                'total_anomalies': len(anomalies),
                'time_range': {
                    'start': start_time,
                    'end': end_time,
                    'duration': end_time - start_time
                },
                'by_type': self._group_by_type(anomalies),
                'by_severity': self._group_by_severity(anomalies)
            },
            'details': {
                'missed_alerts': self._analyze_missed_alerts(anomalies),
                'false_alarms': self._analyze_false_alarms(anomalies),
                'lifecycle_issues': self._analyze_lifecycle(anomalies)
            },
            'recommendations': self._generate_recommendations(anomalies)
        }

        return report

    def _group_by_type(self, anomalies: List[Anomaly]) -> dict:
        """按类型统计"""
        type_counts = {}
        for anomaly in anomalies:
            type_counts[anomaly.type] = type_counts.get(anomaly.type, 0) + 1
        return type_counts

    def _generate_recommendations(self, anomalies: List[Anomaly]) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 检查漏报
        missed_count = sum(1 for a in anomalies if a.type == 'missed_alert')
        if missed_count > 10:
            recommendations.append(
                f"检测到 {missed_count} 次漏报，建议检查LCPS障碍物生成逻辑"
            )

        # 检查误报
        false_count = sum(1 for a in anomalies if 'false_alarm' in a.type)
        if false_count > 20:
            recommendations.append(
                f"检测到 {false_count} 次误报，建议调整OBB置信度阈值或过滤参数"
            )

        # 检查生命周期
        lifecycle_count = sum(1 for a in anomalies if 'lifecycle' in a.type)
        if lifecycle_count > 5:
            recommendations.append(
                "生命周期异常频繁，建议检查LCPS启动/停止逻辑"
            )

        return recommendations
```

---

## 6. 配置示例（完整）

```yaml
# lcps_anomaly_config.yaml
anomaly_detection:
  # 全局设置
  enabled: true
  log_level: "INFO"
  output_path: "/var/log/lcps/anomalies.log"

  # 漏报检测
  missed_alert:
    enabled: true
    danger_zones:
      - id: "zone_front"
        name: "前方危险区"
        type: "box"
        min_x: -2.0
        max_x: 2.0
        min_y: 0.0
        max_y: 5.0
        min_z: 0.0
        max_z: 3.0
      - id: "zone_side"
        name: "侧方危险区"
        type: "box"
        min_x: 2.0
        max_x: 5.0
        min_y: -1.0
        max_y: 1.0
        min_z: 0.0
        max_z: 3.0
    min_points: 50
    min_confidence: 0.7

  # 误报检测
  false_alarm:
    enabled: true
    min_support_points: 20
    support_radius: 1.0
    max_alert_frequency: 10
    min_density: 0.1

  # 生命周期监控
  lifecycle:
    enabled: true
    max_startup_time: 30
    max_error_duration: 60
    max_restarts_per_hour: 5

  # 异常聚合
  aggregation:
    dedupe_window: 5.0
    max_recent_anomalies: 1000

  # 报告生成
  reporting:
    auto_generate: true
    report_interval: 3600  # 每小时生成一次报告
    output_format: "html"  # html, json, pdf
```

---

## 7. 性能要求

| 指标 | 要求 | 说明 |
|------|------|------|
| 检测延迟 | < 50ms | 从接收数据到检测完成 |
| CPU占用 | < 5% | 单核CPU占用 |
| 内存占用 | < 100MB | 历史数据缓存 |
| 漏报检测率 | ≥ 95% | 真实漏报的检出率 |
| 误报率 | < 5% | 误判为漏报/误报的比例 |

---

## 8. 测试用例

### 8.1 漏报检测测试

```python
def test_missed_alert_detection():
    """测试漏报检测"""
    detector = MissedAlertDetector(config)

    # 场景1：危险区域有点云但无OBB
    frame = SyncedFrame(
        timestamp=time.time(),
        data={
            'pointcloud': generate_pointcloud_in_zone(zone_id='zone_front', count=100),
            'obb': {'obbs': []},  # 无OBB
            'status': {'lcps_state': 'active'}
        }
    )

    anomalies = detector.detect(frame)
    assert len(anomalies) > 0
    assert anomalies[0].type == 'missed_alert'
    assert anomalies[0].severity == 'critical'

def test_false_alarm_detection():
    """测试误报检测"""
    detector = FalseAlarmDetector(config)

    # 场景2：有OBB但周围无点云
    frame = SyncedFrame(
        timestamp=time.time(),
        data={
            'pointcloud': generate_empty_pointcloud(),
            'obb': {'obbs': [create_obb(id='obb_001', pos=[1, 2, 0])]},
            'status': {'lcps_state': 'active'}
        }
    )

    anomalies = detector.detect(frame)
    assert len(anomalies) > 0
    assert anomalies[0].type == 'false_alarm'
```

---

## 9. 未来扩展

### 9.1 机器学习增强

```python
class MLAnomalyDetector(AnomalyPlugin):
    """基于机器学习的异常检测（Phase 3）"""

    def __init__(self, model_path: str):
        self.model = load_model(model_path)  # 加载预训练模型

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        # 1. 提取特征
        features = self._extract_features(frame)

        # 2. 模型预测
        prediction = self.model.predict(features)

        # 3. 根据预测结果生成异常
        if prediction['anomaly_score'] > 0.8:
            return [Anomaly(
                type="ml_detected_anomaly",
                severity="medium",
                confidence=prediction['anomaly_score'],
                message="机器学习模型检测到异常模式"
            )]

        return []
```

### 9.2 历史数据对比

```python
class HistoricalComparison(AnomalyPlugin):
    """基于历史数据的异常检测（Phase 3）"""

    def __init__(self, history_db: str):
        self.db = HistoryDatabase(history_db)

    def detect(self, frame: SyncedFrame) -> List[Anomaly]:
        # 查找相似场景的历史数据
        similar_frames = self.db.find_similar(frame, top_k=10)

        # 对比当前frame与历史frame的差异
        diff = self._compare_with_history(frame, similar_frames)

        if diff['anomaly_score'] > threshold:
            return [Anomaly(...)]

        return []
```

---

**版本历史**：
- v1.0 (2025-12-24): 初始版本（规则基检测）
- v2.0 (规划中): 机器学习增强
