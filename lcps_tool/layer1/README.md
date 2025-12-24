# Layer 1: Data Acquisition

Multi-channel data receivers for LCPS observation and debugging tool.

## Architecture

Layer 1 implements the data acquisition layer of the 4-layer architecture (ADR-001):

```
LCPS System (ZMQ Publishers)
    :5555 OBB
    :5556 PointCloud
    :5557 Status
         │
         v
┌─────────────────────────────────────┐
│  Layer 1: Data Acquisition          │
│  - MultiChannelReceiver             │
│  - OBBReceiver                      │
│  - PointCloudReceiver (w/ downsample)
│  - StatusReceiver                   │
└─────────────────────────────────────┘
```

## Components

### BaseReceiver

Abstract base class for all data receivers.

**Features**:
- Multi-threading pattern (receiver thread + main thread)
- Thread-safe Queue buffering (maxsize=10)
- Graceful shutdown with Event signals
- Non-blocking operations
- Statistics and monitoring

**Pattern from recvOBB.py**:
```python
# Receiver thread (I/O operations)
while not stop_event.is_set():
    data = zmq_socket.recv(timeout=100ms)
    queue.put_nowait(data)  # Non-blocking

# Main thread (data consumer)
data = queue.get_nowait()  # Non-blocking
process_data(data)
```

### OBBReceiver

Receives Oriented Bounding Box data.

**Features**:
- Supports normal mode (JSON) and compressed mode (zlib + BSON)
- Compatible with existing sendOBB/recvOBB code
- Parses OBB data (type, position, rotation, size, collision)

**Usage**:
```python
from lcps_tool.layer1.receivers import OBBReceiver

# Create receiver
receiver = OBBReceiver("tcp://localhost:5555", use_compression=False)

# Start receiver thread
receiver.start()

# Get data (non-blocking)
data = receiver.get_data(block=False)
if data and 'obbs' in data:
    for obb in data['obbs']:
        print(f"OBB: {obb['type']} at {obb['position']}")

# Stop receiver
receiver.stop()
```

### PointCloudReceiver

Receives and downsamples point cloud data.

**Features**:
- Voxel Grid downsampling (ADR-003)
- Configurable voxel size (default: 0.1m)
- Achieves ~85-90% point reduction
- Preserves spatial structure

**Downsampling Algorithm**:
1. Divide 3D space into voxel grid
2. Assign each point to a voxel
3. Compute centroid of points in each voxel
4. Keep one centroid per voxel

**Usage**:
```python
from lcps_tool.layer1.receivers import PointCloudReceiver

# Create receiver with downsampling
receiver = PointCloudReceiver(
    "tcp://localhost:5556",
    voxel_size=0.1,
    enable_downsampling=True
)

# Start receiver
receiver.start()

# Get downsampled data
data = receiver.get_data(block=False)
if data:
    print(f"Original: {data['original_count']} points")
    print(f"Downsampled: {data['downsampled_count']} points")
    print(f"Reduction: {data['reduction_rate'] * 100:.1f}%")
    points = data['points']  # numpy.ndarray (N, 3)

# Get statistics
stats = receiver.get_downsampling_statistics()
print(f"Avg reduction: {stats['avg_reduction_rate'] * 100:.1f}%")

# Stop receiver
receiver.stop()
```

### StatusReceiver

Receives LCPS system status data.

**Features**:
- Status state enum (IDLE, DETECTING, ALERTING, ERROR, UNKNOWN)
- Performance metrics (FPS, latency, CPU, memory)
- Detection results (OBB count, collision count, safety status)
- State transition statistics

**Usage**:
```python
from lcps_tool.layer1.receivers import StatusReceiver, LCPSState

# Create receiver
receiver = StatusReceiver("tcp://localhost:5557")

# Start receiver
receiver.start()

# Get status data
data = receiver.get_data(block=False)
if data:
    state = data['state']  # LCPSState enum
    print(f"State: {state.value}")
    print(f"Metrics: {data['metrics']}")
    print(f"Detection: {data['detection']}")

# Get state statistics
stats = receiver.get_state_statistics()
for state_name, state_data in stats['state_distribution'].items():
    print(f"{state_name}: {state_data['count']} ({state_data['percentage']:.1f}%)")

# Stop receiver
receiver.stop()
```

### MultiChannelReceiver

Orchestrates multiple data receivers.

**Features**:
- Unified interface for all channels
- Graceful startup and shutdown
- Comprehensive statistics
- Status monitoring

**Usage**:
```python
from lcps_tool.layer1 import MultiChannelReceiver

# Create receiver
receiver = MultiChannelReceiver()

# Configure channels
receiver.add_obb_channel("tcp://localhost:5555", use_compression=False)
receiver.add_pointcloud_channel("tcp://localhost:5556", voxel_size=0.1)
receiver.add_status_channel("tcp://localhost:5557")

# Start all channels
receiver.start_all()

# Get data from all channels
all_data = receiver.get_all_data()
obb_data = all_data.get('obb')
pc_data = all_data.get('pointcloud')
status_data = all_data.get('status')

# Or get data from specific channel
obb_data = receiver.get_obb_data()
pc_data = receiver.get_pointcloud_data()
status_data = receiver.get_status_data()

# Print status
receiver.print_status()

# Get statistics
stats = receiver.get_statistics()
print(stats)

# Stop all channels
receiver.stop_all()
```

## Example

See `examples/layer1_receiver_example.py` for a complete example.

```bash
python examples/layer1_receiver_example.py
```

## Technical Decisions

- **ADR-001**: 4-layer architecture design (Layer 1: Data Acquisition)
- **ADR-003**: Voxel Grid downsampling strategy (voxel size 0.1m)

See [LCPS Tool Architecture v2.0](../../docs/adr/2025-12-24-lcps-tool-architecture-v2.md) for details.

## Next Steps

- **Layer 2**: Data synchronization and HDF5 recording (LCPS-P1-T3, LCPS-P1-T4)
- **Layer 3**: Anomaly detection and analysis (Phase 2)
- **Layer 4**: 3D visualization and HUD (Phase 1, Phase 3)

## Dependencies

- Python 3.8+
- pyzmq
- numpy
- bson (for compressed mode)

```bash
pip install pyzmq numpy pymongo
# or
uv add pyzmq numpy pymongo
```
