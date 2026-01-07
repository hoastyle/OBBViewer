"""
Multi-Channel Receiver - Orchestrates all data receivers

Manages multiple data channels (OBB, PointCloud, Status, Image) and provides
a unified interface for data acquisition.

Architecture:
- Each channel runs in its own thread (BaseReceiver pattern)
- Non-blocking data retrieval from all channels
- Graceful startup and shutdown
- Comprehensive statistics and monitoring
"""

from typing import Any, Dict, List, Optional

from .receivers.base_receiver import BaseReceiver
from .receivers.obb_receiver import OBBReceiver
from .receivers.pointcloud_receiver import PointCloudReceiver
from .receivers.status_receiver import StatusReceiver


class MultiChannelReceiver:
    """
    Multi-channel data receiver for LCPS observation tool

    Orchestrates multiple data receivers (OBB, PointCloud, Status, etc.)
    and provides a unified interface for data acquisition.

    Usage:
        # Create receiver
        receiver = MultiChannelReceiver()

        # Configure channels
        receiver.add_obb_channel("tcp://localhost:6555", use_compression=False)
        receiver.add_pointcloud_channel("tcp://localhost:6556", voxel_size=0.1)
        receiver.add_status_channel("tcp://localhost:6557")

        # Start all channels
        receiver.start_all()

        # Get data from channels
        obb_data = receiver.get_obb_data()
        pc_data = receiver.get_pointcloud_data()
        status_data = receiver.get_status_data()

        # Stop all channels
        receiver.stop_all()
    """

    def __init__(self):
        """Initialize multi-channel receiver"""
        self.channels: Dict[str, BaseReceiver] = {}
        self._channel_configs: Dict[str, dict] = {}

    def add_obb_channel(self,
                        address: str,
                        use_compression: bool = False,
                        queue_size: int = 10) -> None:
        """
        Add OBB data channel

        Args:
            address: ZMQ address (e.g., "tcp://localhost:6555")
            use_compression: Whether to use compressed mode (zlib + BSON)
            queue_size: Maximum queue size
        """
        if 'obb' in self.channels:
            print("⚠️ OBB channel already exists, replacing...")
            self.remove_channel('obb')

        receiver = OBBReceiver(address, use_compression, queue_size)
        self.channels['obb'] = receiver
        self._channel_configs['obb'] = {
            'address': address,
            'use_compression': use_compression,
            'queue_size': queue_size,
        }
        print(f"✅ OBB channel added: {address}")

    def add_pointcloud_channel(self,
                               address: str,
                               voxel_size: float = 0.1,
                               enable_downsampling: bool = True,
                               queue_size: int = 10) -> None:
        """
        Add PointCloud data channel

        Args:
            address: ZMQ address (e.g., "tcp://localhost:5556")
            voxel_size: Voxel grid size in meters (default: 0.1m)
            enable_downsampling: Whether to apply downsampling
            queue_size: Maximum queue size
        """
        if 'pointcloud' in self.channels:
            print("⚠️ PointCloud channel already exists, replacing...")
            self.remove_channel('pointcloud')

        receiver = PointCloudReceiver(address, voxel_size, enable_downsampling, queue_size)
        self.channels['pointcloud'] = receiver
        self._channel_configs['pointcloud'] = {
            'address': address,
            'voxel_size': voxel_size,
            'enable_downsampling': enable_downsampling,
            'queue_size': queue_size,
        }
        print(f"✅ PointCloud channel added: {address}")

    def add_status_channel(self,
                          address: str,
                          queue_size: int = 10) -> None:
        """
        Add Status data channel

        Args:
            address: ZMQ address (e.g., "tcp://localhost:5557")
            queue_size: Maximum queue size
        """
        if 'status' in self.channels:
            print("⚠️ Status channel already exists, replacing...")
            self.remove_channel('status')

        receiver = StatusReceiver(address, queue_size)
        self.channels['status'] = receiver
        self._channel_configs['status'] = {
            'address': address,
            'queue_size': queue_size,
        }
        print(f"✅ Status channel added: {address}")

    def start_channel(self, channel_name: str) -> bool:
        """
        Start a specific channel

        Args:
            channel_name: Channel name ("obb", "pointcloud", "status")

        Returns:
            True if started successfully, False otherwise
        """
        if channel_name not in self.channels:
            print(f"❌ Channel '{channel_name}' not found")
            return False

        try:
            self.channels[channel_name].start()
            return True
        except Exception as e:
            print(f"❌ Failed to start channel '{channel_name}': {e}")
            return False

    def start_all(self) -> int:
        """
        Start all channels

        Returns:
            Number of channels started successfully
        """
        if not self.channels:
            print("⚠️ No channels configured")
            return 0

        print(f"\n🚀 Starting {len(self.channels)} channel(s)...")
        success_count = 0

        for channel_name in self.channels:
            if self.start_channel(channel_name):
                success_count += 1

        print(f"✅ {success_count}/{len(self.channels)} channel(s) started\n")
        return success_count

    def stop_channel(self, channel_name: str, timeout: float = 2.0) -> bool:
        """
        Stop a specific channel

        Args:
            channel_name: Channel name ("obb", "pointcloud", "status")
            timeout: Maximum wait time for thread to stop

        Returns:
            True if stopped successfully, False otherwise
        """
        if channel_name not in self.channels:
            print(f"❌ Channel '{channel_name}' not found")
            return False

        try:
            self.channels[channel_name].stop(timeout)
            return True
        except Exception as e:
            print(f"❌ Failed to stop channel '{channel_name}': {e}")
            return False

    def stop_all(self, timeout: float = 2.0) -> int:
        """
        Stop all channels

        Args:
            timeout: Maximum wait time for each thread to stop

        Returns:
            Number of channels stopped successfully
        """
        if not self.channels:
            return 0

        print(f"\n🛑 Stopping {len(self.channels)} channel(s)...")
        success_count = 0

        for channel_name in self.channels:
            if self.stop_channel(channel_name, timeout):
                success_count += 1

        print(f"✅ {success_count}/{len(self.channels)} channel(s) stopped\n")
        return success_count

    def remove_channel(self, channel_name: str) -> bool:
        """
        Remove a channel (stops it first if running)

        Args:
            channel_name: Channel name to remove

        Returns:
            True if removed successfully, False otherwise
        """
        if channel_name not in self.channels:
            return False

        # Stop channel first
        self.stop_channel(channel_name)

        # Remove from dictionaries
        del self.channels[channel_name]
        if channel_name in self._channel_configs:
            del self._channel_configs[channel_name]

        print(f"✅ Channel '{channel_name}' removed")
        return True

    def get_obb_data(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Any]:
        """Get latest OBB data"""
        if 'obb' not in self.channels:
            return None
        return self.channels['obb'].get_data(block, timeout)

    def get_pointcloud_data(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Any]:
        """Get latest PointCloud data"""
        if 'pointcloud' not in self.channels:
            return None
        return self.channels['pointcloud'].get_data(block, timeout)

    def get_status_data(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Any]:
        """Get latest Status data"""
        if 'status' not in self.channels:
            return None
        return self.channels['status'].get_data(block, timeout)

    def get_all_data(self) -> Dict[str, Any]:
        """
        Get latest data from all channels

        Returns:
            Dictionary mapping channel names to their latest data
        """
        data = {}
        for channel_name, receiver in self.channels.items():
            channel_data = receiver.get_data(block=False)
            data[channel_name] = channel_data
        return data

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics from all channels

        Returns:
            Dictionary mapping channel names to their statistics
        """
        stats = {}
        for channel_name, receiver in self.channels.items():
            stats[channel_name] = receiver.get_statistics()

            # Add channel-specific statistics
            if channel_name == 'pointcloud' and hasattr(receiver, 'get_downsampling_statistics'):
                stats[channel_name]['downsampling'] = receiver.get_downsampling_statistics()
            elif channel_name == 'status' and hasattr(receiver, 'get_state_statistics'):
                stats[channel_name]['states'] = receiver.get_state_statistics()

        return stats

    def get_channel_names(self) -> List[str]:
        """Get list of configured channel names"""
        return list(self.channels.keys())

    def is_channel_running(self, channel_name: str) -> bool:
        """Check if a channel is running"""
        if channel_name not in self.channels:
            return False
        receiver = self.channels[channel_name]
        return receiver.receiver_thread is not None and receiver.receiver_thread.is_alive()

    def get_running_channels(self) -> List[str]:
        """Get list of running channel names"""
        return [name for name in self.channels if self.is_channel_running(name)]

    def print_status(self) -> None:
        """Print status of all channels"""
        print("\n" + "=" * 60)
        print("Multi-Channel Receiver Status")
        print("=" * 60)

        if not self.channels:
            print("No channels configured")
            return

        for channel_name in self.channels:
            running = "🟢 RUNNING" if self.is_channel_running(channel_name) else "🔴 STOPPED"
            config = self._channel_configs.get(channel_name, {})
            address = config.get('address', 'N/A')
            print(f"\n{channel_name.upper():12} {running:12} {address}")

            stats = self.channels[channel_name].get_statistics()
            print(f"  Messages: {stats['msg_count']:6}  "
                  f"Errors: {stats['error_count']:6}  "
                  f"Queue: {stats['queue_size']}/{self.channels[channel_name].queue_size}")

        print("\n" + "=" * 60 + "\n")

    def __repr__(self) -> str:
        running_count = len(self.get_running_channels())
        return (f"<MultiChannelReceiver "
                f"channels={len(self.channels)} "
                f"running={running_count}>")
