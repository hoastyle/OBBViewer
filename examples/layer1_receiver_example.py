#!/usr/bin/env python3
"""
Layer 1 MultiChannelReceiver Example

Demonstrates how to use the MultiChannelReceiver to receive data from
OBB, PointCloud, and Status channels.

Usage:
    python examples/layer1_receiver_example.py

Prerequisites:
    - LCPS system (or sender) must be running on:
      * tcp://localhost:5555 (OBB data)
      * tcp://localhost:5556 (PointCloud data)
      * tcp://localhost:5557 (Status data)
"""

import time
import signal
import sys

from lcps_tool.layer1 import MultiChannelReceiver


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n🛑 Received interrupt signal, shutting down...")
    sys.exit(0)


def main():
    """Main function"""
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 70)
    print("LCPS Layer 1: Multi-Channel Receiver Example")
    print("=" * 70)
    print()

    # Create receiver
    receiver = MultiChannelReceiver()

    # Configure channels
    print("📡 Configuring channels...")
    receiver.add_obb_channel("tcp://localhost:5555", use_compression=False)
    receiver.add_pointcloud_channel("tcp://localhost:5556", voxel_size=0.1, enable_downsampling=True)
    receiver.add_status_channel("tcp://localhost:5557")
    print()

    # Start all channels
    receiver.start_all()

    # Print initial status
    receiver.print_status()

    print("📊 Receiving data... (Press Ctrl+C to stop)")
    print()

    try:
        msg_count = 0
        while True:
            # Get data from all channels
            all_data = receiver.get_all_data()

            # Process OBB data
            if all_data.get('obb') is not None:
                obb_data = all_data['obb']
                obb_count = len(obb_data.get('obbs', []))
                print(f"[OBB] Received {obb_count} OBBs")

            # Process PointCloud data
            if all_data.get('pointcloud') is not None:
                pc_data = all_data['pointcloud']
                original = pc_data.get('original_count', 0)
                downsampled = pc_data.get('downsampled_count', 0)
                reduction = pc_data.get('reduction_rate', 0.0) * 100
                print(f"[PointCloud] {original} → {downsampled} points ({reduction:.1f}% reduction)")

            # Process Status data
            if all_data.get('status') is not None:
                status_data = all_data['status']
                state = status_data.get('state')
                print(f"[Status] State: {state.value if state else 'N/A'}")

            msg_count += 1

            # Print statistics every 10 messages
            if msg_count % 10 == 0:
                print()
                print("─" * 70)
                stats = receiver.get_statistics()
                for channel_name, channel_stats in stats.items():
                    msg_count_ch = channel_stats.get('msg_count', 0)
                    error_count = channel_stats.get('error_count', 0)
                    queue_size = channel_stats.get('queue_size', 0)
                    print(f"{channel_name.upper():12} | "
                          f"Messages: {msg_count_ch:6} | "
                          f"Errors: {error_count:6} | "
                          f"Queue: {queue_size:2}")
                print("─" * 70)
                print()

            # Sleep briefly to avoid busy-waiting
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n\n🛑 Interrupted by user")

    finally:
        # Stop all channels
        receiver.stop_all()

        # Print final statistics
        print()
        print("=" * 70)
        print("Final Statistics")
        print("=" * 70)
        receiver.print_status()

        # Print channel-specific statistics
        stats = receiver.get_statistics()

        if 'pointcloud' in stats and 'downsampling' in stats['pointcloud']:
            ds_stats = stats['pointcloud']['downsampling']
            print("\n📊 PointCloud Downsampling Statistics:")
            print(f"  Voxel Size: {ds_stats['voxel_size']:.2f} m")
            print(f"  Total Points Received: {ds_stats['total_points_received']}")
            print(f"  Total Points After Downsampling: {ds_stats['total_points_after_downsampling']}")
            print(f"  Average Reduction Rate: {ds_stats['avg_reduction_rate'] * 100:.1f}%")

        if 'status' in stats and 'states' in stats['status']:
            state_stats = stats['status']['states']
            print("\n📊 Status State Distribution:")
            for state_name, state_data in state_stats['state_distribution'].items():
                count = state_data['count']
                pct = state_data['percentage']
                print(f"  {state_name:12} {count:6} ({pct:.1f}%)")

        print("\n✅ Shutdown complete")


if __name__ == "__main__":
    main()
