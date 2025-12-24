"""
Synced Frame - Synchronized multi-source data frame

Contains synchronized data from multiple channels (OBB, PointCloud, Status)
aligned by timestamp.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class SyncedFrame:
    """
    Synchronized frame containing data from multiple channels

    All data in this frame should have timestamps within the synchronization
    window (typically ±50ms).

    Attributes:
        timestamp: Reference timestamp (in seconds, Unix time)
        frame_id: Frame sequence number
        obb_data: OBB data (from OBBReceiver)
        pointcloud_data: Point cloud data (from PointCloudReceiver)
        status_data: Status data (from StatusReceiver)
        sync_quality: Synchronization quality score (0.0-1.0)
        sync_offset_ms: Dict mapping channel names to sync offsets in ms
    """

    timestamp: float
    frame_id: int
    obb_data: Optional[Dict[str, Any]] = None
    pointcloud_data: Optional[Dict[str, Any]] = None
    status_data: Optional[Dict[str, Any]] = None
    sync_quality: float = 1.0
    sync_offset_ms: Optional[Dict[str, float]] = None

    def __post_init__(self):
        """Initialize sync_offset_ms if not provided"""
        if self.sync_offset_ms is None:
            self.sync_offset_ms = {}

    def has_obb(self) -> bool:
        """Check if frame has OBB data"""
        return self.obb_data is not None

    def has_pointcloud(self) -> bool:
        """Check if frame has point cloud data"""
        return self.pointcloud_data is not None

    def has_status(self) -> bool:
        """Check if frame has status data"""
        return self.status_data is not None

    def is_complete(self) -> bool:
        """Check if frame has data from all channels"""
        return self.has_obb() and self.has_pointcloud() and self.has_status()

    def get_obb_count(self) -> int:
        """Get number of OBBs in frame"""
        if not self.has_obb():
            return 0
        return len(self.obb_data.get('obbs', []))

    def get_pointcloud_count(self) -> int:
        """Get number of points in frame"""
        if not self.has_pointcloud():
            return 0
        points = self.pointcloud_data.get('points')
        if isinstance(points, np.ndarray):
            return len(points)
        return 0

    def get_status_state(self) -> Optional[str]:
        """Get system state from status data"""
        if not self.has_status():
            return None
        state = self.status_data.get('state')
        if state is not None and hasattr(state, 'value'):
            return state.value
        return str(state) if state is not None else None

    def get_max_sync_offset(self) -> float:
        """Get maximum synchronization offset across all channels (in ms)"""
        if not self.sync_offset_ms:
            return 0.0
        return max(abs(offset) for offset in self.sync_offset_ms.values())

    def to_dict(self) -> Dict[str, Any]:
        """Convert frame to dictionary (for JSON serialization)"""
        return {
            'timestamp': self.timestamp,
            'frame_id': self.frame_id,
            'has_obb': self.has_obb(),
            'has_pointcloud': self.has_pointcloud(),
            'has_status': self.has_status(),
            'obb_count': self.get_obb_count(),
            'pointcloud_count': self.get_pointcloud_count(),
            'status_state': self.get_status_state(),
            'sync_quality': self.sync_quality,
            'sync_offset_ms': self.sync_offset_ms,
            'max_sync_offset': self.get_max_sync_offset(),
        }

    def __repr__(self) -> str:
        channels = []
        if self.has_obb():
            channels.append(f"OBB({self.get_obb_count()})")
        if self.has_pointcloud():
            channels.append(f"PC({self.get_pointcloud_count()})")
        if self.has_status():
            channels.append(f"Status({self.get_status_state()})")

        return (f"<SyncedFrame "
                f"t={self.timestamp:.3f} "
                f"id={self.frame_id} "
                f"channels=[{', '.join(channels)}] "
                f"quality={self.sync_quality:.2f}>")
