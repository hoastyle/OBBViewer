#!/usr/bin/env python3
"""
Layer 2 Data Synchronization and Recording Example

Demonstrates how to use DataSynchronizer and DataRecorder with MultiChannelReceiver.

Usage:
    python examples/layer2_sync_record_example.py

Prerequisites:
    - LCPS system (or sender) must be running on:
      * tcp://localhost:5555 (OBB data)
      * tcp://localhost:5556 (PointCloud data)
      * tcp://localhost:5557 (Status data)
"""

import time
import signal
import sys
from pathlib import Path

from lcps_tool.layer1 import MultiChannelReceiver
from lcps_tool.layer2 import DataSynchronizer, DataRecorder


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n🛑 Received interrupt signal, shutting down...")
    sys.exit(0)


def main():
    """Main function"""
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 70)
    print("LCPS Layer 2: Data Synchronization and Recording Example")
    print("=" * 70)
    print()

    # Step 1: Create multi-channel receiver (Layer 1)
    print("📡 Step 1: Setting up data receivers...")
    receiver = MultiChannelReceiver()
    receiver.add_obb_channel("tcp://localhost:5555", use_compression=False)
    receiver.add_pointcloud_channel("tcp://localhost:5556", voxel_size=0.1, enable_downsampling=True)
    receiver.add_status_channel("tcp://localhost:5557")
    receiver.start_all()
    print()

    # Step 2: Create data synchronizer (Layer 2)
    print("🔄 Step 2: Setting up data synchronizer...")
    synchronizer = DataSynchronizer(
        sync_window_ms=50.0,  # ±50ms window
        min_quality=0.5  # Minimum sync quality
    )
    print(f"   Sync window: ±{synchronizer.sync_window_ms}ms")
    print(f"   Min quality: {synchronizer.min_quality}")
    print()

    # Step 3: Create data recorder (Layer 2)
    print("💾 Step 3: Setting up HDF5 recorder...")
    output_path = Path("output") / f"lcps_recording_{int(time.time())}.h5"
    recorder = DataRecorder(
        output_path=str(output_path),
        compression="gzip",
        compression_level=6,
        flush_interval=100,
        async_write=True
    )

    metadata = {
        'description': 'LCPS Layer 2 example recording',
        'sync_window_ms': synchronizer.sync_window_ms,
    }
    recorder.start_recording(metadata)
    print()

    # Step 4: Main loop - receive, synchronize, record
    print("🎬 Starting main loop...")
    print("   Layer 1: Receiving data from multiple channels")
    print("   Layer 2: Synchronizing and recording to HDF5")
    print("   Press Ctrl+C to stop")
    print()

    try:
        frame_count = 0
        last_print_time = time.time()

        while True:
            # Get data from all channels (Layer 1)
            obb_data = receiver.get_obb_data()
            pc_data = receiver.get_pointcloud_data()
            status_data = receiver.get_status_data()

            # Add data to synchronizer buffers
            if obb_data:
                synchronizer.add_data('obb', obb_data)
            if pc_data:
                synchronizer.add_data('pointcloud', pc_data)
            if status_data:
                synchronizer.add_data('status', status_data)

            # Try to synchronize
            synced_frame = synchronizer.get_latest_synced_frame()

            if synced_frame:
                # Record synced frame
                recorder.record_frame(synced_frame)
                frame_count += 1

                # Print progress every second
                now = time.time()
                if now - last_print_time >= 1.0:
                    print(f"\r[Frame {frame_count:6}] {synced_frame}", end='', flush=True)
                    last_print_time = now

            # Sleep briefly
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")

    finally:
        # Stop recording
        print("\n")
        print("=" * 70)
        print("Shutting down...")
        print("=" * 70)

        recorder.stop_recording()
        receiver.stop_all()

        # Print final statistics
        print("\n📊 Final Statistics")
        print("─" * 70)

        # Synchronizer stats
        sync_stats = synchronizer.get_statistics()
        print(f"\n🔄 Synchronizer:")
        print(f"   Frames generated: {sync_stats['frame_count']}")
        print(f"   Success rate: {sync_stats['success_rate']:.1f}%")
        print(f"   Avg sync offset: {sync_stats['avg_sync_offset_ms']:.2f} ms")
        print(f"   Buffer status: {sync_stats['buffer_status']}")

        # Recorder stats
        rec_stats = recorder.get_statistics()
        print(f"\n💾 Recorder:")
        print(f"   Frames recorded: {rec_stats['frame_count']}")
        print(f"   Duration: {rec_stats['duration_seconds']:.1f} s")
        print(f"   Average FPS: {rec_stats['fps']:.1f}")
        print(f"   File size: {rec_stats.get('file_size_mb', 0):.2f} MB")
        print(f"   Output: {rec_stats['output_path']}")

        # Layer 1 stats
        print(f"\n📡 Receivers:")
        receiver.print_status()

        print("\n✅ Shutdown complete")


if __name__ == "__main__":
    main()
