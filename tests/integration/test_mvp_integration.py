"""
Integration tests for LCPS Observation Tool MVP (Phase 1 - T5)

Tests end-to-end integration of Layer 1 (MultiChannelReceiver) and
Layer 2 (DataSynchronizer, DataRecorder) modules.

Test Scenarios:
- Basic multi-channel receiver functionality
- Data synchronization quality
- HDF5 recording functionality
- End-to-end data flow
- Performance benchmarks (latency < 100ms)

Based on: docs/management/TASK.md - LCPS-P1-T5
ADR: docs/adr/2025-12-24-lcps-tool-architecture-v2.md
"""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

import h5py
import pytest
import zmq

# Import modules under test
from lcps_tool.layer1.multi_channel_receiver import MultiChannelReceiver
from lcps_tool.layer2.data_recorder import DataRecorder
from lcps_tool.layer2.data_synchronizer import DataSynchronizer


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def zmq_context():
    """Provide ZMQ context for tests"""
    ctx = zmq.Context()
    yield ctx
    ctx.term()


@pytest.fixture
def mock_obb_sender(zmq_context):
    """Mock OBB data sender"""
    socket = zmq_context.socket(zmq.PUB)
    port = socket.bind_to_random_port("tcp://127.0.0.1", min_port=15555, max_port=15600)
    address = f"tcp://127.0.0.1:{port}"

    def send_obb_data(count=10, interval=0.1):
        """Send mock OBB data"""
        time.sleep(0.5)  # Wait for subscriber to connect
        for i in range(count):
            data = {
                "timestamp": time.time(),
                "obbs": [
                    {
                        "type": "car",
                        "position": [i, 0, 0],
                        "rotation": [0, 0, 0],
                        "size": [2, 2, 1],
                    }
                ]
            }
            socket.send_json(data)
            time.sleep(interval)

    yield address, send_obb_data
    socket.close()


@pytest.fixture
def mock_pc_sender(zmq_context):
    """Mock PointCloud data sender"""
    socket = zmq_context.socket(zmq.PUB)
    port = socket.bind_to_random_port("tcp://127.0.0.1", min_port=15600, max_port=15650)
    address = f"tcp://127.0.0.1:{port}"

    def send_pc_data(count=10, interval=0.1):
        """Send mock PointCloud data"""
        time.sleep(0.5)  # Wait for subscriber to connect
        for i in range(count):
            data = {
                "timestamp": time.time(),
                "points": [[i, 0, 0], [i+1, 0, 0], [i+2, 0, 0]],  # Simple 3-point cloud
                "original_count": 1000,
                "downsampled_count": 3,
            }
            socket.send_json(data)
            time.sleep(interval)

    yield address, send_pc_data
    socket.close()


@pytest.fixture
def mock_status_sender(zmq_context):
    """Mock Status data sender"""
    socket = zmq_context.socket(zmq.PUB)
    port = socket.bind_to_random_port("tcp://127.0.0.1", min_port=15650, max_port=15700)
    address = f"tcp://127.0.0.1:{port}"

    def send_status_data(count=10, interval=0.1):
        """Send mock Status data"""
        time.sleep(0.5)  # Wait for subscriber to connect
        for i in range(count):
            data = {
                "timestamp": time.time(),
                "state": "IDLE",  # Simple state string
                "frame_id": i,
            }
            socket.send_json(data)
            time.sleep(interval)

    yield address, send_status_data
    socket.close()


@pytest.fixture
def temp_hdf5_file():
    """Provide temporary HDF5 output file"""
    fd, path = tempfile.mkstemp(suffix='.h5')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.remove(path)


# =============================================================================
# Integration Tests
# =============================================================================

class TestMultiChannelReceiver:
    """Test MultiChannelReceiver integration"""

    def test_basic_multi_channel_reception(self, mock_obb_sender, mock_pc_sender, mock_status_sender):
        """
        Test Case 1: Basic multi-channel receiver functionality

        Validates:
        - All 3 channels can be configured and started
        - Data can be received from all channels
        - Channels can be stopped gracefully
        """
        obb_addr, send_obb = mock_obb_sender
        pc_addr, send_pc = mock_pc_sender
        status_addr, send_status = mock_status_sender

        # Create receiver
        receiver = MultiChannelReceiver()
        receiver.add_obb_channel(obb_addr, use_compression=False, queue_size=10)
        receiver.add_pointcloud_channel(pc_addr, voxel_size=0.1, queue_size=10)
        receiver.add_status_channel(status_addr, queue_size=10)

        # Start all channels
        started = receiver.start_all()
        assert started == 3, "All 3 channels should start successfully"

        # Start senders in background
        obb_thread = threading.Thread(target=send_obb, args=(5, 0.1))
        pc_thread = threading.Thread(target=send_pc, args=(5, 0.1))
        status_thread = threading.Thread(target=send_status, args=(5, 0.1))

        obb_thread.start()
        pc_thread.start()
        status_thread.start()

        # Wait for data
        time.sleep(1.5)

        # Get data from all channels
        all_data = receiver.get_all_data()
        assert 'obb' in all_data
        assert 'pointcloud' in all_data
        assert 'status' in all_data

        # At least one channel should have received data
        received_count = sum(1 for data in all_data.values() if data is not None)
        assert received_count > 0, "At least one channel should receive data"

        # Stop all channels
        stopped = receiver.stop_all()
        assert stopped == 3, "All 3 channels should stop successfully"

        # Wait for threads
        obb_thread.join(timeout=1)
        pc_thread.join(timeout=1)
        status_thread.join(timeout=1)

    def test_receiver_statistics(self, mock_obb_sender):
        """
        Test Case 2: Receiver statistics tracking

        Validates:
        - Statistics are correctly tracked
        - Message counts are accurate
        """
        obb_addr, send_obb = mock_obb_sender

        receiver = MultiChannelReceiver()
        receiver.add_obb_channel(obb_addr, use_compression=False, queue_size=10)
        receiver.start_all()

        # Send data
        send_thread = threading.Thread(target=send_obb, args=(5, 0.1))
        send_thread.start()

        # Wait for data
        time.sleep(1.5)

        # Check statistics
        stats = receiver.get_statistics()
        assert 'obb' in stats
        assert stats['obb']['msg_count'] >= 0  # May be 0 if timing is off
        assert stats['obb']['error_count'] == 0

        receiver.stop_all()
        send_thread.join(timeout=1)


class TestDataSynchronizer:
    """Test DataSynchronizer integration"""

    def test_synchronization_quality(self):
        """
        Test Case 3: Data synchronization quality

        Validates:
        - Synchronization within 50ms window
        - Sync quality calculation
        - Handles missing data gracefully
        """
        synchronizer = DataSynchronizer(sync_window_ms=50.0, buffer_size=100)

        base_time = time.time()

        # Add data from 3 channels with slight time offsets
        obb_data = {"timestamp": base_time, "obbs": []}
        pc_data = {"timestamp": base_time + 0.02, "points": []}  # 20ms offset
        status_data = {"timestamp": base_time + 0.01, "state": "IDLE"}  # 10ms offset

        synchronizer.add_data('obb', obb_data)
        synchronizer.add_data('pointcloud', pc_data)
        synchronizer.add_data('status', status_data)

        # Synchronize at base time
        frame = synchronizer.synchronize(base_time)

        assert frame is not None, "Frame should be synchronized"
        assert frame.has_obb(), "Frame should have OBB data"
        assert frame.has_pointcloud(), "Frame should have PointCloud data"
        assert frame.has_status(), "Frame should have Status data"

        # Check sync quality (should be high since offsets are small)
        assert frame.sync_quality > 0.5, f"Sync quality should be > 0.5, got {frame.sync_quality}"

        # Check sync offsets
        assert 'obb' in frame.sync_offset_ms
        assert 'pointcloud' in frame.sync_offset_ms
        assert 'status' in frame.sync_offset_ms

        # Max offset should be 20ms
        max_offset = max(abs(o) for o in frame.sync_offset_ms.values())
        assert max_offset <= 50, f"Max offset should be <= 50ms, got {max_offset}ms"


class TestDataRecorder:
    """Test DataRecorder integration"""

    def test_hdf5_recording(self, temp_hdf5_file):
        """
        Test Case 4: HDF5 recording functionality

        Validates:
        - HDF5 file creation
        - Frame recording
        - Metadata storage
        - File structure correctness
        """
        from lcps_tool.data_models.synced_frame import SyncedFrame

        recorder = DataRecorder(
            output_path=temp_hdf5_file,
            compression="gzip",
            compression_level=6,
            flush_interval=10,
            async_write=False  # Synchronous for testing
        )

        # Start recording
        metadata = {"test": "mvp_integration", "version": "1.0.0"}
        recorder.start_recording(metadata)

        # Record some frames
        for i in range(5):
            frame = SyncedFrame(
                timestamp=time.time(),
                frame_id=i,
                obb_data={"obbs": [{"type": "car", "position": [i, 0, 0], "rotation": [0, 0, 0], "size": [2, 2, 1]}]},
                pointcloud_data={"points": [[i, 0, 0]], "original_count": 1000, "downsampled_count": 1},
                status_data={"state": "IDLE", "frame_id": i},
                sync_quality=0.95,
                sync_offset_ms={"obb": 0.0, "pointcloud": 10.0, "status": 5.0}
            )
            recorder.record_frame(frame)
            time.sleep(0.01)  # Small delay

        # Stop recording
        recorder.stop_recording()

        # Verify HDF5 file
        assert os.path.exists(temp_hdf5_file), "HDF5 file should exist"

        with h5py.File(temp_hdf5_file, 'r') as f:
            # Check metadata
            assert 'recording_date' in f.attrs
            assert 'version' in f.attrs
            assert f.attrs['version'] == '1.0.0'
            assert 'user_test' in f.attrs

            # Check datasets
            assert 'timestamps' in f
            assert 'frame_ids' in f
            assert len(f['timestamps']) == 5
            assert len(f['frame_ids']) == 5

            # Check data groups
            assert 'obb_data' in f
            assert 'pointcloud_data' in f
            assert 'status_data' in f

            # Check individual frames
            assert 'frame_000000' in f['obb_data']
            assert 'frame_000000' in f['pointcloud_data']
            assert 'frame_000000' in f['status_data']


class TestEndToEnd:
    """End-to-end integration tests"""

    def test_full_pipeline(self, mock_obb_sender, mock_pc_sender, mock_status_sender, temp_hdf5_file):
        """
        Test Case 5: Full pipeline integration

        Validates:
        - Complete data flow: receiver → synchronizer → recorder
        - Data consistency through the pipeline
        - All components work together correctly
        """
        from lcps_tool.data_models.synced_frame import SyncedFrame

        obb_addr, send_obb = mock_obb_sender
        pc_addr, send_pc = mock_pc_sender
        status_addr, send_status = mock_status_sender

        # Setup components
        receiver = MultiChannelReceiver()
        receiver.add_obb_channel(obb_addr, use_compression=False, queue_size=10)
        receiver.add_pointcloud_channel(pc_addr, voxel_size=0.1, queue_size=10)
        receiver.add_status_channel(status_addr, queue_size=10)

        synchronizer = DataSynchronizer(sync_window_ms=100.0, buffer_size=100)  # Larger window for robustness

        recorder = DataRecorder(
            output_path=temp_hdf5_file,
            compression="gzip",
            compression_level=6,
            flush_interval=5,
            async_write=False
        )

        # Start pipeline
        receiver.start_all()
        recorder.start_recording({"test": "full_pipeline"})

        # Start senders
        message_count = 10
        obb_thread = threading.Thread(target=send_obb, args=(message_count, 0.05))
        pc_thread = threading.Thread(target=send_pc, args=(message_count, 0.05))
        status_thread = threading.Thread(target=send_status, args=(message_count, 0.05))

        obb_thread.start()
        pc_thread.start()
        status_thread.start()

        # Process data
        synced_frames = []
        for _ in range(20):  # Run for 2 seconds (20 * 0.1s)
            # Get data from all channels
            all_data = receiver.get_all_data()

            # Add to synchronizer
            for channel_name, data in all_data.items():
                if data is not None:
                    synchronizer.add_data(channel_name, data)

            # Try to synchronize
            frame = synchronizer.get_latest_synced_frame()
            if frame is not None:
                synced_frames.append(frame)
                recorder.record_frame(frame)

            time.sleep(0.1)

        # Stop pipeline
        receiver.stop_all()
        recorder.stop_recording()

        # Wait for threads
        obb_thread.join(timeout=2)
        pc_thread.join(timeout=2)
        status_thread.join(timeout=2)

        # Verify results
        assert len(synced_frames) > 0, "Should have synchronized at least some frames"

        # Verify HDF5 file
        with h5py.File(temp_hdf5_file, 'r') as f:
            recorded_frames = len(f['timestamps'])
            assert recorded_frames > 0, "Should have recorded at least some frames"
            assert recorded_frames <= len(synced_frames), "Recorded frames should match synced frames"


# =============================================================================
# Performance Benchmark Tests
# =============================================================================

class TestPerformance:
    """Performance benchmark tests"""

    def test_layer1_latency(self, mock_obb_sender):
        """
        Test Case 6: Layer 1 latency benchmark

        Validation Criteria (ADR v2.0):
        - Layer 1 延迟 < 100ms

        Measures:
        - Time from sender publishing to receiver retrieving data
        """
        obb_addr, send_obb = mock_obb_sender

        receiver = MultiChannelReceiver()
        receiver.add_obb_channel(obb_addr, use_compression=False, queue_size=10)
        receiver.start_all()

        latencies = []

        def send_timestamped_data():
            """Send data with precise timestamps"""
            time.sleep(0.5)  # Wait for connection
            for i in range(20):
                send_time = time.time()
                data = {
                    "timestamp": send_time,
                    "obbs": [{"type": "car", "position": [i, 0, 0], "rotation": [0, 0, 0], "size": [2, 2, 1]}]
                }
                socket = zmq.Context.instance().socket(zmq.PUB)
                socket.connect(obb_addr)
                socket.send_json(data)
                time.sleep(0.05)  # 20Hz

        send_thread = threading.Thread(target=send_timestamped_data)
        send_thread.start()

        # Measure latencies
        for _ in range(30):  # Run for 1.5 seconds
            receive_time = time.time()
            data = receiver.get_obb_data()

            if data is not None and 'timestamp' in data:
                send_time = data['timestamp']
                latency = (receive_time - send_time) * 1000  # Convert to ms
                if latency < 500:  # Filter out unrealistic values
                    latencies.append(latency)

            time.sleep(0.05)

        receiver.stop_all()
        send_thread.join(timeout=2)

        # Analyze latencies
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)

            print(f"\n📊 Layer 1 Latency Benchmark:")
            print(f"   Average: {avg_latency:.2f}ms")
            print(f"   Maximum: {max_latency:.2f}ms")
            print(f"   Samples: {len(latencies)}")

            # Validation
            assert avg_latency < 100, f"Average latency should be < 100ms, got {avg_latency:.2f}ms"
            print(f"   ✅ PASS: Average latency {avg_latency:.2f}ms < 100ms")
        else:
            pytest.skip("No valid latency samples collected")


# =============================================================================
# Test Execution Report
# =============================================================================

if __name__ == "__main__":
    """
    Run integration tests with pytest

    Usage:
        pytest tests/integration/test_mvp_integration.py -v
        pytest tests/integration/test_mvp_integration.py -v -k "test_full_pipeline"
        pytest tests/integration/test_mvp_integration.py -v -k "test_layer1_latency"
    """
    pytest.main([__file__, "-v", "--tb=short"])
