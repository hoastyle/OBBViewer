#!/usr/bin/env python3
"""
LCPS Observation Tool - MVP Integration

Integrates Layer 1 (MultiChannelReceiver) and Layer 2 (DataSynchronizer, DataRecorder)
into a runnable MVP for real-time LCPS data observation and recording.

Usage:
    python -m lcps_tool.main --obb tcp://localhost:5555 --pc tcp://localhost:5556 --status tcp://localhost:5557 --output data/test.h5

Architecture (4-Layer):
    Layer 1: MultiChannelReceiver (OBB, PointCloud, Status channels)
    Layer 2: DataSynchronizer + DataRecorder
    Layer 3: Analysis (future - plugins)
    Layer 4: Visualization (future - OpenGL/ImGui)
"""

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .layer1.multi_channel_receiver import MultiChannelReceiver
from .layer2.data_recorder import DataRecorder
from .layer2.data_synchronizer import DataSynchronizer


class LCPSObservationTool:
    """
    LCPS Observation Tool MVP

    Integrates data acquisition, synchronization, and recording.
    """

    def __init__(self,
                 obb_address: str,
                 pc_address: str,
                 status_address: str,
                 output_path: str,
                 enable_recording: bool = True,
                 sync_window_ms: float = 50.0,
                 voxel_size: float = 0.1):
        """
        Initialize LCPS Observation Tool

        Args:
            obb_address: OBB channel ZMQ address (e.g., "tcp://localhost:5555")
            pc_address: PointCloud channel ZMQ address
            status_address: Status channel ZMQ address
            output_path: HDF5 output file path
            enable_recording: Whether to enable HDF5 recording
            sync_window_ms: Synchronization window in milliseconds
            voxel_size: Point cloud downsampling voxel size
        """
        self.enable_recording = enable_recording

        # Layer 1: Multi-channel receiver
        self.receiver = MultiChannelReceiver()
        self.receiver.add_obb_channel(obb_address, use_compression=False, queue_size=10)
        self.receiver.add_pointcloud_channel(pc_address, voxel_size=voxel_size, queue_size=10)
        self.receiver.add_status_channel(status_address, queue_size=10)

        # Layer 2: Data synchronizer
        self.synchronizer = DataSynchronizer(sync_window_ms=sync_window_ms, buffer_size=100)

        # Layer 2: Data recorder
        self.recorder: Optional[DataRecorder] = None
        if self.enable_recording:
            self.recorder = DataRecorder(
                output_path=output_path,
                compression="gzip",
                compression_level=6,
                flush_interval=100,
                async_write=True
            )

        # Runtime state
        self.running = False
        self.start_time: Optional[float] = None
        self.frame_count = 0

        # Statistics tracking
        self.stats_interval = 5.0  # Print stats every 5 seconds
        self.last_stats_time = 0.0

    def start(self) -> None:
        """Start the observation tool"""
        print("\n" + "=" * 70)
        print(" LCPS Observation Tool - MVP")
        print("=" * 70)

        # Start Layer 1 receivers
        print("\n[Layer 1] Starting data receivers...")
        started = self.receiver.start_all()
        if started == 0:
            print("❌ Failed to start receivers")
            sys.exit(1)

        # Start Layer 2 recorder
        if self.enable_recording and self.recorder:
            print("\n[Layer 2] Starting HDF5 recorder...")
            metadata = {
                'tool': 'LCPS Observation Tool',
                'version': '1.0.0-MVP',
                'channels': self.receiver.get_channel_names(),
            }
            self.recorder.start_recording(metadata)

        self.running = True
        self.start_time = time.time()
        self.last_stats_time = self.start_time

        print("\n✅ All systems started")
        print("=" * 70)
        print("\n📊 Press Ctrl+C to stop...\n")

    def stop(self) -> None:
        """Stop the observation tool"""
        if not self.running:
            return

        print("\n\n" + "=" * 70)
        print(" Shutting down...")
        print("=" * 70)

        self.running = False

        # Stop Layer 1 receivers
        print("\n[Layer 1] Stopping receivers...")
        self.receiver.stop_all()

        # Stop Layer 2 recorder
        if self.enable_recording and self.recorder:
            print("\n[Layer 2] Stopping recorder...")
            self.recorder.stop_recording(timeout=5.0)

        # Print final statistics
        self._print_final_statistics()

        print("\n✅ Shutdown complete")
        print("=" * 70 + "\n")

    def run(self) -> None:
        """Main processing loop"""
        while self.running:
            try:
                # Get data from all channels
                all_data = self.receiver.get_all_data()

                # Add data to synchronizer buffers
                for channel_name, data in all_data.items():
                    if data is not None:
                        self.synchronizer.add_data(channel_name, data)

                # Synchronize data
                synced_frame = self.synchronizer.get_latest_synced_frame()

                if synced_frame is not None:
                    self.frame_count += 1

                    # Record to HDF5
                    if self.enable_recording and self.recorder:
                        self.recorder.record_frame(synced_frame)

                    # Print periodic statistics
                    current_time = time.time()
                    if current_time - self.last_stats_time >= self.stats_interval:
                        self._print_runtime_statistics()
                        self.last_stats_time = current_time

                # Small sleep to avoid busy-waiting
                time.sleep(0.001)  # 1ms

            except KeyboardInterrupt:
                print("\n\n⚠️ Keyboard interrupt detected...")
                break
            except Exception as e:
                print(f"\n⚠️ Error in main loop: {e}")
                import traceback
                traceback.print_exc()
                break

    def _print_runtime_statistics(self) -> None:
        """Print runtime statistics"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        fps = self.frame_count / elapsed if elapsed > 0 else 0

        # Layer 1 statistics
        receiver_stats = self.receiver.get_statistics()

        # Layer 2 synchronizer statistics
        sync_stats = self.synchronizer.get_statistics()

        # Layer 2 recorder statistics
        recorder_stats = self.recorder.get_statistics() if self.recorder else {}

        print("\n" + "-" * 70)
        print(f"⏱️  Runtime: {elapsed:.1f}s | Synced Frames: {self.frame_count} | FPS: {fps:.1f}")
        print("-" * 70)

        # Print receiver stats
        print("\n📡 Receivers:")
        for channel, stats in receiver_stats.items():
            print(f"  {channel:12} | Messages: {stats['msg_count']:6} | "
                  f"Errors: {stats['error_count']:3} | "
                  f"Queue: {stats['queue_size']:3}")

        # Print synchronizer stats
        print(f"\n🔄 Synchronizer:")
        print(f"  Success Rate: {sync_stats['success_rate']:.1f}% | "
              f"Avg Offset: {sync_stats['avg_sync_offset_ms']:.2f}ms | "
              f"Buffers: {sync_stats['buffer_status']}")

        # Print recorder stats
        if recorder_stats:
            print(f"\n💾 Recorder:")
            print(f"  Frames: {recorder_stats['frame_count']} | "
                  f"FPS: {recorder_stats['fps']:.1f} | "
                  f"Size: {recorder_stats.get('file_size_mb', 0):.2f} MB")
            if 'queue_size' in recorder_stats:
                print(f"  Write Queue: {recorder_stats['queue_size']}")

        print("-" * 70)

    def _print_final_statistics(self) -> None:
        """Print final statistics"""
        elapsed = time.time() - self.start_time if self.start_time else 0

        print("\n" + "=" * 70)
        print(" Final Statistics")
        print("=" * 70)

        print(f"\n⏱️  Total Runtime: {elapsed:.2f}s")
        print(f"📊 Total Synced Frames: {self.frame_count}")
        print(f"📈 Average FPS: {self.frame_count / elapsed if elapsed > 0 else 0:.2f}")

        # Layer 1 final stats
        receiver_stats = self.receiver.get_statistics()
        print("\n📡 Receiver Summary:")
        for channel, stats in receiver_stats.items():
            print(f"  {channel:12} | Total Messages: {stats['msg_count']:6} | "
                  f"Errors: {stats['error_count']:3}")

        # Layer 2 synchronizer final stats
        sync_stats = self.synchronizer.get_statistics()
        print(f"\n🔄 Synchronizer Summary:")
        print(f"  Success: {sync_stats['sync_success_count']} | "
              f"Failed: {sync_stats['sync_fail_count']} | "
              f"Success Rate: {sync_stats['success_rate']:.1f}%")
        print(f"  Average Sync Offset: {sync_stats['avg_sync_offset_ms']:.2f}ms")

        # Layer 2 recorder final stats
        if self.recorder:
            recorder_stats = self.recorder.get_statistics()
            print(f"\n💾 Recorder Summary:")
            print(f"  Output: {recorder_stats['output_path']}")
            print(f"  Frames: {recorder_stats['frame_count']}")
            print(f"  File Size: {recorder_stats.get('file_size_mb', 0):.2f} MB")

        print("=" * 70)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='LCPS Observation Tool - MVP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage (all defaults)
  python -m lcps_tool.main

  # Custom addresses and output
  python -m lcps_tool.main \\
    --obb tcp://192.168.1.100:5555 \\
    --pc tcp://192.168.1.100:5556 \\
    --status tcp://192.168.1.100:5557 \\
    --output data/recording_$(date +%Y%m%d_%H%M%S).h5

  # Adjust sync window and voxel size
  python -m lcps_tool.main --sync-window 100 --voxel-size 0.05

  # Disable recording (observation only)
  python -m lcps_tool.main --no-record
        """
    )

    parser.add_argument(
        '--obb',
        type=str,
        default='tcp://localhost:5555',
        help='OBB channel ZMQ address (default: tcp://localhost:5555)'
    )

    parser.add_argument(
        '--pc',
        type=str,
        default='tcp://localhost:5556',
        help='PointCloud channel ZMQ address (default: tcp://localhost:5556)'
    )

    parser.add_argument(
        '--status',
        type=str,
        default='tcp://localhost:5557',
        help='Status channel ZMQ address (default: tcp://localhost:5557)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        default='data/lcps_recording.h5',
        help='HDF5 output file path (default: data/lcps_recording.h5)'
    )

    parser.add_argument(
        '--no-record',
        action='store_true',
        help='Disable HDF5 recording (observation only)'
    )

    parser.add_argument(
        '--sync-window',
        type=float,
        default=50.0,
        help='Synchronization window in milliseconds (default: 50.0)'
    )

    parser.add_argument(
        '--voxel-size',
        type=float,
        default=0.1,
        help='Point cloud downsampling voxel size in meters (default: 0.1)'
    )

    return parser.parse_args()


def main():
    """Main entry point"""
    args = parse_arguments()

    # Create output directory
    if not args.no_record:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create tool instance
    tool = LCPSObservationTool(
        obb_address=args.obb,
        pc_address=args.pc,
        status_address=args.status,
        output_path=args.output,
        enable_recording=not args.no_record,
        sync_window_ms=args.sync_window,
        voxel_size=args.voxel_size
    )

    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n⚠️ Received signal, shutting down...")
        tool.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start and run
    tool.start()
    tool.run()
    tool.stop()


if __name__ == '__main__':
    main()
