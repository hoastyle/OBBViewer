# LCPS HDF5 录制格式规范

**版本**: 1.0
**创建日期**: 2025-12-24
**父文档**: [LCPS综合设计方案](LCPS_COMPREHENSIVE_DESIGN.md)

## 1. HDF5文件结构

```
lcps_recording_YYYYMMDD_HHMMSS.h5
├── metadata/                   # 元数据组
│   ├── attrs: version, start_time, duration, site_info
│   └── lcps_config.json        # LCPS配置JSON
├── streams/                    # 数据流组
│   ├── obb/
│   │   ├── timestamps: Dataset[float64]  # 时间戳数组
│   │   ├── data: Dataset[compound]       # OBB结构化数据
│   │   └── index: Dataset[uint64]        # 索引（用于快速查询）
│   ├── pointcloud/
│   │   ├── timestamps: Dataset[float64]
│   │   ├── points: VLen Dataset[float32] # 变长点云数组
│   │   └── metadata: Dataset[compound]   # 点云元数据（count, downsample_ratio）
│   ├── status/
│   │   ├── timestamps: Dataset[float64]
│   │   └── data: Dataset[compound]       # 状态数据
│   └── images/ (可选)
│       ├── timestamps: Dataset[float64]
│       └── frames: Dataset[binary]       # JPEG压缩图像
├── events/                     # 事件索引组
│   ├── anomalies: Dataset[compound]      # 异常事件
│   ├── alerts: Dataset[compound]         # 报警事件
│   └── user_marks: Dataset[compound]     # 用户标记
└── analysis/                   # 分析结果组（可选）
    ├── statistics.json         # 统计数据
    ├── density_map: Dataset[float32]  # 点云密度热图
    └── coverage_map: Dataset[uint8]   # 覆盖范围图
```

## 2. 数据类型定义

### 2.1 OBB数据类型

```python
obb_dtype = np.dtype([
    ('id', 'S16'),            # 16字节字符串
    ('type', 'u1'),           # uint8 (0=dynamic, 1=static, 2=unknown)
    ('position', 'f4', 3),    # float32[3]
    ('rotation', 'f4', 3),    # float32[3] (euler angles)
    ('size', 'f4', 3),        # float32[3]
    ('confidence', 'f4'),     # float32
    ('track_id', 'i4'),       # int32 (-1表示未跟踪)
    ('velocity', 'f4', 3)     # float32[3] (静态障碍物为[0,0,0])
])
```

### 2.2 状态数据类型

```python
status_dtype = np.dtype([
    ('lcps_state', 'u1'),     # uint8 (枚举)
    ('protection_zone_id', 'S16'),
    ('is_triggered', 'b1'),   # bool
    ('trigger_count', 'u4'),  # uint32
    ('fps', 'f4'),
    ('pointcloud_count', 'u4'),
    ('obb_count', 'u4'),
    ('cpu_usage', 'f4'),
    ('memory_mb', 'f4')
])
```

### 2.3 异常事件类型

```python
anomaly_dtype = np.dtype([
    ('timestamp', 'f8'),      # float64
    ('type', 'S32'),          # 异常类型字符串
    ('severity', 'u1'),       # uint8 (0=low, 1=medium, 2=high, 3=critical)
    ('zone_id', 'S16'),       # 可选
    ('obb_id', 'S16'),        # 可选
    ('description', 'S256')   # 描述字符串
])
```

## 3. 压缩策略（基于ADR-002）

| 数据类型 | 压缩算法 | 压缩级别 | 压缩率 | 说明 |
|---------|---------|---------|--------|------|
| OBB数据 | zstd | 1 | ~40% | 快速压缩 |
| 点云数据 | zstd | 5 | ~74% | 高压缩率 |
| 状态数据 | gzip | 3 | ~50% | 平衡 |
| 图像数据 | JPEG | quality=85 | ~90% | 有损压缩 |

## 4. 索引策略

### 4.1 时间戳索引

```python
# 创建时间戳索引（支持快速跳转）
timestamps = np.array([...])  # 所有帧的时间戳
index_interval = 100  # 每100帧创建一个索引点

index = {
    'timestamps': timestamps[::index_interval],
    'offsets': np.arange(0, len(timestamps), index_interval)
}
```

### 4.2 事件索引

```python
# 创建事件类型索引
event_index = defaultdict(list)
for i, event in enumerate(events):
    event_index[event['type']].append(i)
```

## 5. 读写示例

### 5.1 写入示例

```python
# 创建HDF5文件
with h5py.File('recording.h5', 'w') as f:
    # 元数据
    f.attrs['version'] = '1.0'
    f.attrs['start_time'] = datetime.now().isoformat()

    # 创建OBB数据集
    obb_group = f.create_group('streams/obb')
    obb_ts = obb_group.create_dataset('timestamps',
        shape=(0,), maxshape=(None,), dtype='f8')
    obb_data = obb_group.create_dataset('data',
        shape=(0,), maxshape=(None,),
        dtype=obb_dtype, compression='zstd', compression_opts=1)

    # 写入数据
    for frame in data_stream:
        obb_ts.resize((obb_ts.shape[0] + 1,))
        obb_ts[-1] = frame.timestamp

        obb_data.resize((obb_data.shape[0] + 1,))
        obb_data[-1] = frame.to_numpy()
```

### 5.2 读取示例

```python
# 读取HDF5文件
with h5py.File('recording.h5', 'r') as f:
    # 读取元数据
    version = f.attrs['version']
    start_time = f.attrs['start_time']

    # 读取OBB数据
    obb_timestamps = f['streams/obb/timestamps'][:]
    obb_data = f['streams/obb/data'][:]

    # 按时间范围查询
    start_ts = 1703419200.0
    end_ts = 1703419800.0
    mask = (obb_timestamps >= start_ts) & (obb_timestamps <= end_ts)
    selected_data = obb_data[mask]
```

## 6. 文件大小估算

**假设**：
- 录制时长：1小时
- OBB频率：30 Hz
- 点云频率：10 Hz
- 点云数量：50,000点/帧（下采样10%）
- 状态频率：1 Hz

**估算**：
```
OBB:        30 Hz * 3600s * 52 bytes * 0.6 (压缩) = 3.3 MB
PointCloud: 10 Hz * 3600s * 50k * 12 bytes * 0.26 (压缩) = 560 MB
Status:     1 Hz * 3600s * 40 bytes * 0.5 (压缩) = 72 KB
Events:     ~100 events * 300 bytes = 30 KB

总计: ~564 MB/小时
```

符合ADR-002的 < 2GB/小时 要求 ✅

---

**版本历史**：
- v1.0 (2025-12-24): 初始版本
