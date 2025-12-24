"""
Data Recorder - Records synchronized data to HDF5 format

Implements HDF5 recording with:
- Asynchronous writing (queue-based)
- Stream compression (gzip/zstd)
- Periodic flush (every 100 frames)
- Metadata recording
"""

import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import h5py
import numpy as np

from ..data_models.synced_frame import SyncedFrame


class DataRecorder:
    """
    HDF5 data recorder with async writing

    File structure (ADR-002):
    /
    ├── metadata (attrs)
    │   ├── recording_date
    │   ├── version
    │   ├── config
    │   └── ...
    ├── timestamps (dataset)
    ├── frame_ids (dataset)
    ├── obb_data/
    │   ├── frame_0000 (group)
    │   ├── frame_0001 (group)
    │   └── ...
    ├── pointcloud_data/
    │   ├── frame_0000 (dataset)
    │   ├── frame_0001 (dataset)
    │   └── ...
    └── status_data/
        ├── frame_0000 (group)
        ├── frame_0001 (group)
        └── ...

    Parameters:
        output_path: Output HDF5 file path
        compression: Compression algorithm ("gzip" or "zstd")
        compression_level: Compression level (1-9 for gzip)
        flush_interval: Flush every N frames (default: 100)
        async_write: Enable asynchronous writing (default: True)
    """

    def __init__(self,
                 output_path: str,
                 compression: str = "gzip",
                 compression_level: int = 6,
                 flush_interval: int = 100,
                 async_write: bool = True):
        """
        Initialize data recorder

        Args:
            output_path: Output HDF5 file path
            compression: Compression algorithm ("gzip")
            compression_level: Compression level (1-9)
            flush_interval: Flush every N frames
            async_write: Enable asynchronous writing
        """
        self.output_path = Path(output_path)
        self.compression = compression
        self.compression_level = compression_level
        self.flush_interval = flush_interval
        self.async_write = async_write

        # HDF5 file and datasets
        self.h5file: Optional[h5py.File] = None
        self.timestamps_ds: Optional[h5py.Dataset] = None
        self.frame_ids_ds: Optional[h5py.Dataset] = None

        # Frame counter
        self.frame_count = 0
        self.bytes_written = 0

        # Async writing
        if self.async_write:
            self.write_queue: queue.Queue = queue.Queue(maxsize=200)
            self.stop_event = threading.Event()
            self.writer_thread: Optional[threading.Thread] = None

        # Recording state
        self.is_recording = False
        self.start_time: Optional[float] = None

    def start_recording(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Start recording

        Args:
            metadata: Optional metadata to store in file

        Raises:
            RuntimeError: If already recording
        """
        if self.is_recording:
            raise RuntimeError("Already recording")

        # Create output directory if needed
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # Open HDF5 file
        self.h5file = h5py.File(self.output_path, 'w')

        # Initialize metadata
        self._init_metadata(metadata)

        # Create datasets
        self._init_datasets()

        # Start async writer thread
        if self.async_write:
            self.stop_event.clear()
            self.writer_thread = threading.Thread(
                target=self._writer_thread_func,
                daemon=True,
                name="HDF5-Writer"
            )
            self.writer_thread.start()
            print(f"✅ Async writer thread started")

        self.is_recording = True
        self.start_time = time.time()
        print(f"🎬 Recording started: {self.output_path}")

    def stop_recording(self, timeout: float = 5.0) -> None:
        """
        Stop recording and close file

        Args:
            timeout: Maximum wait time for async writer to finish
        """
        if not self.is_recording:
            return

        # Stop async writer
        if self.async_write and self.writer_thread is not None:
            self.stop_event.set()
            self.writer_thread.join(timeout=timeout)
            print("✅ Async writer thread stopped")

        # Final flush
        if self.h5file is not None:
            self.h5file.flush()

            # Update final metadata
            duration = time.time() - self.start_time if self.start_time else 0
            self.h5file.attrs['frame_count'] = self.frame_count
            self.h5file.attrs['duration_seconds'] = duration
            self.h5file.attrs['bytes_written'] = self.bytes_written

            # Close file
            self.h5file.close()
            self.h5file = None

        self.is_recording = False
        file_size_mb = self.output_path.stat().st_size / (1024 * 1024)
        print(f"🛑 Recording stopped: {self.output_path}")
        print(f"   Frames: {self.frame_count}, Size: {file_size_mb:.2f} MB")

    def record_frame(self, frame: SyncedFrame) -> None:
        """
        Record a synced frame

        Args:
            frame: Synced frame to record

        Raises:
            RuntimeError: If not recording
        """
        if not self.is_recording:
            raise RuntimeError("Not recording")

        if self.async_write:
            # Add to queue for async writing
            try:
                self.write_queue.put_nowait(frame)
            except queue.Full:
                print("⚠️ Write queue full, dropping frame")
        else:
            # Write synchronously
            self._write_frame(frame)

    def _writer_thread_func(self) -> None:
        """Async writer thread main function"""
        while not self.stop_event.is_set():
            try:
                # Get frame from queue with timeout
                frame = self.write_queue.get(timeout=0.1)
                self._write_frame(frame)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Writer thread error: {e}")

        # Drain remaining frames
        while not self.write_queue.empty():
            try:
                frame = self.write_queue.get_nowait()
                self._write_frame(frame)
            except queue.Empty:
                break

    def _write_frame(self, frame: SyncedFrame) -> None:
        """
        Write frame to HDF5 file

        Args:
            frame: Frame to write
        """
        if self.h5file is None:
            return

        # Resize timestamp and frame_id datasets
        new_size = self.frame_count + 1
        self.timestamps_ds.resize((new_size,))
        self.frame_ids_ds.resize((new_size,))

        # Write timestamp and frame_id
        self.timestamps_ds[self.frame_count] = frame.timestamp
        self.frame_ids_ds[self.frame_count] = frame.frame_id

        # Write OBB data
        if frame.has_obb():
            self._write_obb_data(frame.obb_data, self.frame_count)

        # Write point cloud data
        if frame.has_pointcloud():
            self._write_pointcloud_data(frame.pointcloud_data, self.frame_count)

        # Write status data
        if frame.has_status():
            self._write_status_data(frame.status_data, self.frame_count)

        self.frame_count += 1

        # Periodic flush
        if self.frame_count % self.flush_interval == 0:
            self.h5file.flush()

    def _init_metadata(self, metadata: Optional[Dict[str, Any]]) -> None:
        """Initialize HDF5 file metadata"""
        if self.h5file is None:
            return

        # Standard metadata
        self.h5file.attrs['recording_date'] = datetime.now().isoformat()
        self.h5file.attrs['version'] = '1.0.0'
        self.h5file.attrs['compression'] = self.compression
        self.h5file.attrs['compression_level'] = self.compression_level

        # User metadata
        if metadata:
            for key, value in metadata.items():
                # Convert to JSON for complex types
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)
                self.h5file.attrs[f'user_{key}'] = value

    def _init_datasets(self) -> None:
        """Initialize HDF5 datasets"""
        if self.h5file is None:
            return

        # Create resizable datasets for timestamps and frame_ids
        self.timestamps_ds = self.h5file.create_dataset(
            'timestamps',
            shape=(0,),
            maxshape=(None,),
            dtype='f8',
            compression=self.compression,
            compression_opts=self.compression_level
        )

        self.frame_ids_ds = self.h5file.create_dataset(
            'frame_ids',
            shape=(0,),
            maxshape=(None,),
            dtype='i4',
            compression=self.compression,
            compression_opts=self.compression_level
        )

        # Create groups for data channels
        self.h5file.create_group('obb_data')
        self.h5file.create_group('pointcloud_data')
        self.h5file.create_group('status_data')

    def _write_obb_data(self, obb_data: Dict[str, Any], frame_idx: int) -> None:
        """Write OBB data to HDF5"""
        if self.h5file is None:
            return

        group = self.h5file['obb_data'].create_group(f'frame_{frame_idx:06d}')

        # Store OBBs as JSON (simple approach)
        obbs_json = json.dumps(obb_data.get('obbs', []))
        group.attrs['obbs'] = obbs_json

    def _write_pointcloud_data(self, pc_data: Dict[str, Any], frame_idx: int) -> None:
        """Write point cloud data to HDF5"""
        if self.h5file is None:
            return

        points = pc_data.get('points')
        if isinstance(points, np.ndarray):
            # Store points as dataset
            ds = self.h5file['pointcloud_data'].create_dataset(
                f'frame_{frame_idx:06d}',
                data=points,
                compression=self.compression,
                compression_opts=self.compression_level
            )

            # Store metadata
            ds.attrs['original_count'] = pc_data.get('original_count', 0)
            ds.attrs['downsampled_count'] = pc_data.get('downsampled_count', 0)
            ds.attrs['reduction_rate'] = pc_data.get('reduction_rate', 0.0)

    def _write_status_data(self, status_data: Dict[str, Any], frame_idx: int) -> None:
        """Write status data to HDF5"""
        if self.h5file is None:
            return

        group = self.h5file['status_data'].create_group(f'frame_{frame_idx:06d}')

        # Store status as JSON
        # Convert LCPSState enum to string
        status_copy = status_data.copy()
        if 'state' in status_copy and hasattr(status_copy['state'], 'value'):
            status_copy['state'] = status_copy['state'].value

        status_json = json.dumps(status_copy)
        group.attrs['status'] = status_json

    def get_statistics(self) -> Dict[str, Any]:
        """Get recording statistics"""
        duration = time.time() - self.start_time if self.start_time and self.is_recording else 0

        stats = {
            'is_recording': self.is_recording,
            'frame_count': self.frame_count,
            'duration_seconds': duration,
            'fps': self.frame_count / duration if duration > 0 else 0,
            'output_path': str(self.output_path),
        }

        if self.async_write and self.is_recording:
            stats['queue_size'] = self.write_queue.qsize()

        if self.output_path.exists():
            stats['file_size_mb'] = self.output_path.stat().st_size / (1024 * 1024)

        return stats

    def __repr__(self) -> str:
        status = "RECORDING" if self.is_recording else "STOPPED"
        return (f"<DataRecorder "
                f"path={self.output_path.name} "
                f"status={status} "
                f"frames={self.frame_count}>")
