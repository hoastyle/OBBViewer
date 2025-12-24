# LCPS Observation Tool - Quick Start Guide

**Version**: 1.0.0-MVP
**Last Updated**: 2025-12-24

## Overview

LCPS Observation Tool is a real-time data observation and recording system for LCPS (Laser-based Collision Prevention System). It integrates Layer 1 (data acquisition) and Layer 2 (synchronization and recording) to provide a complete MVP solution.

### Features

- ✅ **Multi-channel data reception** (OBB, PointCloud, Status)
- ✅ **Timestamp-based synchronization** (±50ms window)
- ✅ **HDF5 recording** with gzip compression
- ✅ **Real-time statistics** (FPS, sync quality, buffer status)
- ✅ **Graceful shutdown** (Ctrl+C handling)

### Architecture

```
┌─────────────────────────────────────────────┐
│         LCPS Observation Tool (MVP)         │
├─────────────────────────────────────────────┤
│  Layer 1: MultiChannelReceiver              │
│    ├─ OBBReceiver     (tcp://localhost:5555)│
│    ├─ PointCloudReceiver (tcp://localhost:5556)│
│    └─ StatusReceiver  (tcp://localhost:5557)│
├─────────────────────────────────────────────┤
│  Layer 2: DataSynchronizer + DataRecorder   │
│    ├─ Sync Window: ±50ms                    │
│    └─ HDF5 Output: data/lcps_recording.h5   │
└─────────────────────────────────────────────┘
```

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 18.04+) or macOS
- **Python**: 3.8+
- **Memory**: ≥ 2GB available
- **Disk**: ≥ 10GB for recordings (1 hour ≈ 22GB)

### Dependencies

Install Python dependencies:

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

**Core dependencies**:
- `pyzmq >= 27.1.0` - ZMQ Python bindings
- `h5py >= 3.x` - HDF5 file I/O
- `numpy >= 2.4.0` - Numerical computing

---

## Installation

### Option 1: Development Setup

```bash
# Clone repository
git clone <repo-url>
cd OBBViewer

# Install dependencies
uv sync

# Verify installation
python -m lcps_tool.main --help
```

### Option 2: Standalone Executable (Future)

```bash
# Download pre-built binary
wget <release-url>/lcps_tool-linux-x64.tar.gz
tar -xzf lcps_tool-linux-x64.tar.gz
cd lcps_tool

# Run
./lcps_tool --help
```

---

## Basic Usage

### 1. Start LCPS System (Data Source)

**Note**: You need a running LCPS system that publishes data on ZMQ ports 5555-5557.

If you don't have LCPS, you can use the test sender:

```bash
# Terminal 1: Start OBB sender
./sender  # or your LCPS system
```

### 2. Start LCPS Observation Tool

```bash
# Basic usage (default settings)
python -m lcps_tool.main

# Or using uv
uv run python -m lcps_tool.main
```

**Default configuration**:
- OBB channel: `tcp://localhost:5555`
- PointCloud channel: `tcp://localhost:5556`
- Status channel: `tcp://localhost:5557`
- Output file: `data/lcps_recording.h5`
- Sync window: 50ms
- Voxel size: 0.1m

### 3. Monitor Output

You'll see real-time statistics every 5 seconds:

```
----------------------------------------------------------------------
⏱️  Runtime: 15.2s | Synced Frames: 456 | FPS: 30.0
----------------------------------------------------------------------

📡 Receivers:
  obb          | Messages:    456 | Errors:   0 | Queue:   3
  pointcloud   | Messages:    456 | Errors:   0 | Queue:   2
  status       | Messages:    456 | Errors:   0 | Queue:   1

🔄 Synchronizer:
  Success Rate: 98.5% | Avg Offset: 12.34ms | Buffers: {'obb': 10, 'pointcloud': 10, 'status': 10}

💾 Recorder:
  Frames: 449 | FPS: 29.6 | Size: 45.2 MB
  Write Queue: 5
----------------------------------------------------------------------
```

### 4. Stop Recording

Press `Ctrl+C` to gracefully stop:

```
⚠️ Keyboard interrupt detected...

======================================================================
 Shutting down...
======================================================================

[Layer 1] Stopping receivers...
✅ 3/3 channel(s) stopped

[Layer 2] Stopping recorder...
🛑 Recording stopped: data/lcps_recording.h5
   Frames: 1234, Size: 123.45 MB

======================================================================
 Final Statistics
======================================================================

⏱️  Total Runtime: 60.12s
📊 Total Synced Frames: 1234
📈 Average FPS: 20.53

...

✅ Shutdown complete
======================================================================
```

---

## Advanced Usage

### Custom Addresses

Connect to remote LCPS system:

```bash
python -m lcps_tool.main \
  --obb tcp://192.168.1.100:5555 \
  --pc tcp://192.168.1.100:5556 \
  --status tcp://192.168.1.100:5557 \
  --output data/remote_recording.h5
```

### Adjust Synchronization

Increase sync window for high-latency networks:

```bash
python -m lcps_tool.main --sync-window 100  # 100ms window
```

### Adjust Point Cloud Downsampling

Use finer voxel size for higher resolution:

```bash
python -m lcps_tool.main --voxel-size 0.05  # 5cm voxels (higher quality)
```

### Observation Only (No Recording)

Disable HDF5 recording to reduce overhead:

```bash
python -m lcps_tool.main --no-record
```

Useful for:
- Live monitoring without storage
- Testing receiver configuration
- Checking sync quality

### Auto-generated Filenames

Use date/time in output filename:

```bash
# Linux/macOS
python -m lcps_tool.main --output "data/recording_$(date +%Y%m%d_%H%M%S).h5"

# Result: data/recording_20251224_153045.h5
```

---

## Output Files

### HDF5 File Structure

The output HDF5 file follows the structure defined in [ADR-002](../adr/2025-12-24-lcps-tool-architecture-v2.md#决策-2-hdf5-数据格式):

```
lcps_recording.h5
├── metadata (attrs)
│   ├── recording_date: "2025-12-24T15:30:45"
│   ├── version: "1.0.0"
│   ├── compression: "gzip"
│   └── user_tool: "LCPS Observation Tool"
├── timestamps (dataset, Nx1 float64)
├── frame_ids (dataset, Nx1 int32)
├── obb_data/
│   ├── frame_000000 (group, attrs: obbs JSON)
│   ├── frame_000001
│   └── ...
├── pointcloud_data/
│   ├── frame_000000 (dataset, Kx3 float32, compressed)
│   ├── frame_000001
│   └── ...
└── status_data/
    ├── frame_000000 (group, attrs: status JSON)
    ├── frame_000001
    └── ...
```

### Inspecting HDF5 Files

Use `h5dump` or Python:

```bash
# View file structure
h5dump -H data/lcps_recording.h5

# View metadata
h5dump -A data/lcps_recording.h5
```

```python
# Python inspection
import h5py

with h5py.File('data/lcps_recording.h5', 'r') as f:
    print(f"Frames: {len(f['timestamps'])}")
    print(f"Recording date: {f.attrs['recording_date']}")
    print(f"Channels: {list(f.keys())}")
```

---

## Verification and Testing

### Performance Benchmarks

Expected performance (based on ADR v2.0 validation):

| Metric | Target | Typical |
|--------|--------|---------|
| **Layer 1 Latency** | < 100ms | 30-50ms |
| **Sync Success Rate** | ≥ 95% | 98-99% |
| **Average Sync Offset** | < 25ms | 10-20ms |
| **Recording FPS** | ≥ 20 | 25-30 |
| **CPU Usage** | < 50% (single core) | 30-40% |
| **Memory Usage** | < 2GB | 500MB-1GB |

### Test Scenarios

Run the following tests to validate MVP:

#### Test 1: Local Test (Default)

```bash
# Terminal 1: Start sender
./sender

# Terminal 2: Start tool
python -m lcps_tool.main

# Expected: FPS ≥ 20, sync rate ≥ 95%
```

#### Test 2: Different Frame Rates

```bash
# Test at 10Hz
python -m lcps_tool.main --sync-window 100

# Test at 30Hz (default)
python -m lcps_tool.main

# Test at 60Hz
python -m lcps_tool.main --sync-window 30
```

#### Test 3: Long-duration Test (≥ 1 hour)

```bash
# Run for 1 hour
timeout 3600 python -m lcps_tool.main --output data/long_test.h5

# Verify file size and integrity
ls -lh data/long_test.h5
h5dump -H data/long_test.h5
```

---

## Troubleshooting

### Issue 1: "Failed to start receivers"

**Cause**: ZMQ connection failed (sender not running or wrong address)

**Solution**:
1. Verify sender is running: `netstat -an | grep 5555`
2. Check firewall settings
3. Try localhost explicitly: `--obb tcp://127.0.0.1:5555`

### Issue 2: Low sync success rate (< 90%)

**Cause**: Data sources have inconsistent timing or high latency

**Solution**:
1. Increase sync window: `--sync-window 100`
2. Check sender frame rate consistency
3. Verify network latency (if remote)

### Issue 3: High CPU usage (> 80%)

**Cause**: Too many messages or inefficient processing

**Solution**:
1. Increase voxel size (less points): `--voxel-size 0.2`
2. Disable recording temporarily: `--no-record`
3. Check sender message rate

### Issue 4: HDF5 file corruption

**Cause**: Interrupted shutdown (kill -9 or power loss)

**Solution**:
1. Always use `Ctrl+C` for graceful shutdown
2. Check file integrity: `h5dump -H <file>`
3. If corrupted, restore from backup or re-record

---

## Next Steps

### Phase 2: Plugin System

After MVP validation, implement:
- Dynamic plugin loading (`PluginManager`)
- Anomaly detection plugins (`MissedAlertDetector`, `FalseAlarmDetector`)
- Data replay functionality (`DataReplayer`)

See: [TASK.md - Phase 2](../management/TASK.md#lcps-观测工具---phase-2-完整功能-优先级-🟠-中3-周)

### Phase 3: Visualization

Add Layer 4 visualization:
- OpenGL 3D rendering (OBB + PointCloud)
- ImGui HUD (statistics, controls)
- Multi-view layout

See: [TASK.md - Phase 3](../management/TASK.md#lcps-观测工具---phase-3-高级功能-优先级-🟡-低3-周)

---

## Additional Resources

- **Architecture**: [ADR v2.0 - LCPS Tool Architecture](../adr/2025-12-24-lcps-tool-architecture-v2.md)
- **HDF5 Format**: [LCPS HDF5 Format Specification](../design/LCPS_HDF5_FORMAT.md)
- **Task Tracking**: [TASK.md](../management/TASK.md)
- **Project Planning**: [PLANNING.md](../management/PLANNING.md)

---

## Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review [TASK.md](../management/TASK.md) for known issues
3. Create issue in project tracker

**Version**: 1.0.0-MVP
**Date**: 2025-12-24
