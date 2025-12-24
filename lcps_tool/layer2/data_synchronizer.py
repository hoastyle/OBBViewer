"""
Data Synchronizer - Synchronizes multi-source data by timestamp

Implements timestamp-based synchronization algorithm:
- Threshold matching (±50ms window)
- Generates SyncedFrame with aligned data
- Handles missing data gracefully
"""

import time
from collections import deque
from typing import Any, Dict, List, Optional

from ..data_models.synced_frame import SyncedFrame


class DataSynchronizer:
    """
    Synchronizes data from multiple channels by timestamp

    Algorithm:
    1. Buffer incoming data from each channel (with timestamps)
    2. For each target timestamp, find closest data within sync window
    3. Generate SyncedFrame with synchronized data
    4. Calculate sync quality based on time offsets

    Parameters:
        sync_window_ms: Synchronization window in milliseconds (default: 50ms)
        buffer_size: Maximum buffer size per channel (default: 100)
        min_quality: Minimum sync quality to accept frame (default: 0.5)
    """

    def __init__(self,
                 sync_window_ms: float = 50.0,
                 buffer_size: int = 100,
                 min_quality: float = 0.5):
        """
        Initialize data synchronizer

        Args:
            sync_window_ms: Synchronization window in milliseconds (±50ms)
            buffer_size: Maximum buffer size per channel
            min_quality: Minimum sync quality (0.0-1.0)
        """
        self.sync_window_ms = sync_window_ms
        self.sync_window_s = sync_window_ms / 1000.0  # Convert to seconds
        self.buffer_size = buffer_size
        self.min_quality = min_quality

        # Data buffers for each channel
        self.buffers: Dict[str, deque] = {
            'obb': deque(maxlen=buffer_size),
            'pointcloud': deque(maxlen=buffer_size),
            'status': deque(maxlen=buffer_size),
        }

        # Statistics
        self.frame_count = 0
        self.sync_success_count = 0
        self.sync_fail_count = 0
        self.total_sync_offset = 0.0

    def add_data(self, channel: str, data: Dict[str, Any]) -> None:
        """
        Add data to channel buffer

        Args:
            channel: Channel name ("obb", "pointcloud", "status")
            data: Data dictionary with 'timestamp' field

        Raises:
            ValueError: If channel is invalid or data missing timestamp
        """
        if channel not in self.buffers:
            raise ValueError(f"Invalid channel: {channel}. Must be one of {list(self.buffers.keys())}")

        if 'timestamp' not in data:
            raise ValueError(f"Data missing 'timestamp' field for channel {channel}")

        self.buffers[channel].append(data)

    def synchronize(self, target_timestamp: Optional[float] = None) -> Optional[SyncedFrame]:
        """
        Synchronize data at target timestamp

        Args:
            target_timestamp: Target timestamp (if None, use latest data)

        Returns:
            SyncedFrame if synchronization successful, None otherwise
        """
        # Use latest timestamp if not specified
        if target_timestamp is None:
            target_timestamp = self._get_latest_timestamp()
            if target_timestamp is None:
                return None

        # Find matching data for each channel
        obb_data, obb_offset = self._find_closest_data('obb', target_timestamp)
        pc_data, pc_offset = self._find_closest_data('pointcloud', target_timestamp)
        status_data, status_offset = self._find_closest_data('status', target_timestamp)

        # Calculate sync quality
        offsets = {}
        if obb_offset is not None:
            offsets['obb'] = obb_offset * 1000  # Convert to ms
        if pc_offset is not None:
            offsets['pointcloud'] = pc_offset * 1000
        if status_offset is not None:
            offsets['status'] = status_offset * 1000

        # Calculate quality score (1.0 - normalized max offset)
        if offsets:
            max_offset = max(abs(o) for o in offsets.values())
            sync_quality = 1.0 - (max_offset / self.sync_window_ms)
            sync_quality = max(0.0, min(1.0, sync_quality))  # Clamp to [0, 1]
        else:
            sync_quality = 0.0

        # Check if quality meets minimum threshold
        if sync_quality < self.min_quality:
            self.sync_fail_count += 1
            return None

        # Create synced frame
        self.frame_count += 1
        self.sync_success_count += 1
        if offsets:
            self.total_sync_offset += max(abs(o) for o in offsets.values())

        frame = SyncedFrame(
            timestamp=target_timestamp,
            frame_id=self.frame_count,
            obb_data=obb_data,
            pointcloud_data=pc_data,
            status_data=status_data,
            sync_quality=sync_quality,
            sync_offset_ms=offsets
        )

        return frame

    def synchronize_batch(self, timestamps: List[float]) -> List[SyncedFrame]:
        """
        Synchronize multiple timestamps

        Args:
            timestamps: List of target timestamps

        Returns:
            List of successfully synchronized frames
        """
        frames = []
        for ts in timestamps:
            frame = self.synchronize(ts)
            if frame is not None:
                frames.append(frame)
        return frames

    def get_latest_synced_frame(self) -> Optional[SyncedFrame]:
        """
        Get the latest synchronized frame (convenience method)

        Returns:
            Latest SyncedFrame or None
        """
        return self.synchronize()

    def clear_buffers(self) -> None:
        """Clear all data buffers"""
        for buffer in self.buffers.values():
            buffer.clear()

    def get_buffer_status(self) -> Dict[str, int]:
        """Get current buffer sizes"""
        return {
            channel: len(buffer)
            for channel, buffer in self.buffers.items()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get synchronization statistics"""
        total_frames = self.sync_success_count + self.sync_fail_count
        success_rate = (self.sync_success_count / total_frames * 100) if total_frames > 0 else 0.0
        avg_offset = (self.total_sync_offset / self.sync_success_count) if self.sync_success_count > 0 else 0.0

        return {
            'frame_count': self.frame_count,
            'sync_success_count': self.sync_success_count,
            'sync_fail_count': self.sync_fail_count,
            'success_rate': success_rate,
            'avg_sync_offset_ms': avg_offset,
            'buffer_status': self.get_buffer_status(),
        }

    def _get_latest_timestamp(self) -> Optional[float]:
        """Get the latest timestamp from all buffers"""
        timestamps = []
        for buffer in self.buffers.values():
            if buffer:
                timestamps.append(buffer[-1]['timestamp'])

        return max(timestamps) if timestamps else None

    def _find_closest_data(self,
                          channel: str,
                          target_timestamp: float) -> tuple[Optional[Dict[str, Any]], Optional[float]]:
        """
        Find closest data within sync window

        Args:
            channel: Channel name
            target_timestamp: Target timestamp

        Returns:
            Tuple of (data, time_offset) or (None, None) if no match
        """
        buffer = self.buffers[channel]
        if not buffer:
            return None, None

        # Find closest timestamp within window
        closest_data = None
        closest_offset = None

        for data in buffer:
            offset = data['timestamp'] - target_timestamp
            abs_offset = abs(offset)

            # Check if within window
            if abs_offset <= self.sync_window_s:
                # Update if closer than previous best
                if closest_offset is None or abs_offset < abs(closest_offset):
                    closest_data = data
                    closest_offset = offset

        return closest_data, closest_offset

    def __repr__(self) -> str:
        return (f"<DataSynchronizer "
                f"window={self.sync_window_ms}ms "
                f"buffers={self.get_buffer_status()} "
                f"frames={self.frame_count}>")
