"""
PointCloud Receiver - Receives and downsamples point cloud data

Implements Voxel Grid downsampling as per ADR-003:
- Divides 3D space into voxel grid
- Keeps one representative point per voxel (centroid)
- Achieves ~85-90% point reduction
- Preserves spatial structure
"""

import json
from typing import Any, Dict, Optional, Tuple

import numpy as np
import zmq

from .base_receiver import BaseReceiver


class PointCloudReceiver(BaseReceiver):
    """
    Point Cloud data receiver with voxel grid downsampling

    Receives point cloud data from LCPS system via ZMQ PUB/SUB.
    Applies voxel grid downsampling to reduce data size.

    Data format (input):
    {
        "points": [[x1, y1, z1], [x2, y2, z2], ...],  # Nx3 array
        "timestamp": float,                            # Unix timestamp
        "frame_id": int                                # Frame ID
    }

    Data format (output, after downsampling):
    {
        "points": np.ndarray,      # Mx3 array (M << N)
        "timestamp": float,
        "frame_id": int,
        "original_count": int,     # Original point count (N)
        "downsampled_count": int,  # Downsampled point count (M)
        "reduction_rate": float    # (N - M) / N
    }
    """

    def __init__(self,
                 address: str,
                 voxel_size: float = 0.1,
                 enable_downsampling: bool = True,
                 queue_size: int = 10):
        """
        Initialize PointCloud receiver

        Args:
            address: ZMQ address (e.g., "tcp://localhost:5556")
            voxel_size: Voxel grid size in meters (default: 0.1m as per ADR-003)
            enable_downsampling: Whether to apply downsampling
            queue_size: Maximum queue size (default: 10)
        """
        super().__init__(address, "PointCloud", queue_size)
        self.voxel_size = voxel_size
        self.enable_downsampling = enable_downsampling

        # Statistics
        self.total_points_received = 0
        self.total_points_after_downsampling = 0

    def _receive_data(self) -> Optional[Dict[str, Any]]:
        """
        Receive and parse point cloud data

        Returns:
            Parsed point cloud data dictionary with downsampling applied

        Raises:
            zmq.error.Again: Timeout (no data available)
            RuntimeError: Parsing error
        """
        if self.socket is None:
            raise RuntimeError("ZMQ socket not initialized")

        # Receive raw data
        message = self.socket.recv()

        # Parse JSON
        try:
            data = json.loads(message.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to parse point cloud data: {e}")

        # Validate data format
        if 'points' not in data:
            raise RuntimeError("Invalid point cloud data: missing 'points' field")

        # Convert points to numpy array
        points = np.array(data['points'], dtype=np.float32)

        if points.ndim != 2 or points.shape[1] != 3:
            raise RuntimeError(f"Invalid point cloud shape: {points.shape}, expected (N, 3)")

        original_count = len(points)
        self.total_points_received += original_count

        # Apply downsampling if enabled
        if self.enable_downsampling and original_count > 0:
            points_downsampled = self._voxel_grid_downsample(points)
            downsampled_count = len(points_downsampled)
            self.total_points_after_downsampling += downsampled_count

            reduction_rate = (original_count - downsampled_count) / original_count
        else:
            points_downsampled = points
            downsampled_count = original_count
            reduction_rate = 0.0

        # Construct output data
        result = {
            'points': points_downsampled,
            'timestamp': data.get('timestamp', 0.0),
            'frame_id': data.get('frame_id', 0),
            'original_count': original_count,
            'downsampled_count': downsampled_count,
            'reduction_rate': reduction_rate,
        }

        return result

    def _voxel_grid_downsample(self, points: np.ndarray) -> np.ndarray:
        """
        Voxel grid downsampling (ADR-003)

        Algorithm:
        1. Divide 3D space into voxel grid (size = voxel_size)
        2. Assign each point to a voxel based on coordinates
        3. Compute centroid of points in each voxel
        4. Keep one centroid per voxel

        Args:
            points: Nx3 array of 3D points

        Returns:
            Mx3 array of downsampled points (M << N)
        """
        if len(points) == 0:
            return points

        # Compute voxel indices for each point
        voxel_indices = np.floor(points / self.voxel_size).astype(np.int32)

        # Use dictionary to group points by voxel
        voxel_map: Dict[Tuple[int, int, int], list] = {}

        for i, voxel_idx in enumerate(voxel_indices):
            voxel_key = tuple(voxel_idx)
            if voxel_key not in voxel_map:
                voxel_map[voxel_key] = []
            voxel_map[voxel_key].append(points[i])

        # Compute centroid for each voxel
        downsampled_points = []
        for voxel_points in voxel_map.values():
            centroid = np.mean(voxel_points, axis=0)
            downsampled_points.append(centroid)

        return np.array(downsampled_points, dtype=np.float32)

    def get_downsampling_statistics(self) -> Dict[str, Any]:
        """Get downsampling statistics"""
        if self.total_points_received > 0:
            avg_reduction = ((self.total_points_received - self.total_points_after_downsampling)
                            / self.total_points_received)
        else:
            avg_reduction = 0.0

        return {
            'voxel_size': self.voxel_size,
            'enabled': self.enable_downsampling,
            'total_points_received': self.total_points_received,
            'total_points_after_downsampling': self.total_points_after_downsampling,
            'avg_reduction_rate': avg_reduction,
        }

    def __repr__(self) -> str:
        ds_status = f"downsample={self.voxel_size}m" if self.enable_downsampling else "no-downsample"
        return (f"<PointCloudReceiver "
                f"address={self.address} "
                f"{ds_status} "
                f"running={self.receiver_thread is not None and self.receiver_thread.is_alive()}>")
