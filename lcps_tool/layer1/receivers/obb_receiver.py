"""
OBB Receiver - Receives Oriented Bounding Box data

Supports two modes:
- Normal mode: JSON format
- Compressed mode: zlib + BSON format
"""

import json
import zlib
from typing import Any, Dict, Optional

import bson
import zmq

from .base_receiver import BaseReceiver


class OBBReceiver(BaseReceiver):
    """
    OBB (Oriented Bounding Box) data receiver

    Receives OBB data from LCPS system via ZMQ PUB/SUB.
    Supports both normal (JSON) and compressed (zlib + BSON) modes.

    Data format:
    {
        "obbs": [
            {
                "type": str,           # OBB type (e.g., "car", "pedestrian")
                "position": [x, y, z], # 3D position
                "rotation": [[...], ...], # 3x3 rotation matrix or quaternion
                "size": [w, h, d],     # Width, height, depth
                "collision": bool      # Collision status
            },
            ...
        ]
    }
    """

    def __init__(self, address: str, use_compression: bool = False, queue_size: int = 10):
        """
        Initialize OBB receiver

        Args:
            address: ZMQ address (e.g., "tcp://localhost:6555")
            use_compression: Whether to use compressed mode (zlib + BSON)
            queue_size: Maximum queue size (default: 10)
        """
        super().__init__(address, "OBB", queue_size)
        self.use_compression = use_compression

    def _receive_data(self) -> Optional[Dict[str, Any]]:
        """
        Receive and parse OBB data

        Returns:
            Parsed OBB data dictionary

        Raises:
            zmq.error.Again: Timeout (no data available)
            RuntimeError: Mode mismatch or parsing error
        """
        if self.socket is None:
            raise RuntimeError("ZMQ socket not initialized")

        # Receive raw data
        message = self.socket.recv()

        # Parse based on mode
        if self.use_compression:
            return self._parse_compressed(message)
        else:
            return self._parse_normal(message)

    def _parse_normal(self, message: bytes) -> Dict[str, Any]:
        """
        Parse normal mode data (JSON)

        Supports two formats:
        1. LCPS Protocol format (with header + payload)
        2. Legacy format (direct OBB array)

        Args:
            message: Raw message bytes

        Returns:
            Parsed JSON data dictionary (with 'timestamp' and 'obbs' fields)

        Raises:
            RuntimeError: Decoding or parsing error
        """
        try:
            raw_data = json.loads(message.decode('utf-8'))
        except UnicodeDecodeError:
            raise RuntimeError(
                "Failed to decode data as UTF-8. "
                "Possible cause: Sender uses compressed mode (-m c) but receiver uses normal mode (-m n). "
                "Solution: Ensure sender and receiver use the same -m parameter."
            )
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse JSON: {e}")

        # Handle LCPS Protocol format (header + payload)
        if 'header' in raw_data and 'payload' in raw_data:
            timestamp = raw_data['header']['timestamp']
            payload = raw_data['payload']

            # Extract OBBs from payload
            if 'obbs' in payload:
                obbs = payload['obbs']
            else:
                obbs = []

            return {
                'timestamp': timestamp,
                'obbs': obbs,
                'seq_id': raw_data['header'].get('seq_id', -1),
                'source': raw_data['header'].get('source', 'unknown'),
            }

        # Handle legacy format (direct array or data field)
        # This is for backward compatibility with old sender.cpp
        if isinstance(raw_data, list):
            # Direct array format
            return {'obbs': raw_data}
        elif 'data' in raw_data:
            # Wrapped array format
            return {'obbs': raw_data['data']}
        else:
            # Unknown format
            return raw_data

    def _parse_compressed(self, message: bytes) -> Dict[str, Any]:
        """
        Parse compressed mode data (zlib + BSON)

        Args:
            message: Raw compressed message bytes

        Returns:
            Parsed data dictionary

        Raises:
            RuntimeError: Decompression or parsing error
        """
        try:
            # Decompress
            decompressed_data = zlib.decompress(message)

            # Parse BSON
            data = bson.loads(decompressed_data)
        except zlib.error as e:
            raise RuntimeError(
                f"Failed to decompress data: {e}. "
                "Possible cause: Sender uses normal mode (-m n) but receiver uses compressed mode (-m c). "
                "Solution: Ensure sender and receiver use the same -m parameter."
            )
        except bson.errors.BSONError as e:
            raise RuntimeError(f"Failed to parse BSON: {e}")

        return data

    def get_latest_obbs(self) -> Optional[list]:
        """
        Get the latest OBB list (convenience method)

        Returns:
            List of OBBs, or None if no data available
        """
        data = self.get_data(block=False)
        if data is not None and 'obbs' in data:
            return data['obbs']
        return None

    def __repr__(self) -> str:
        mode = "compressed" if self.use_compression else "normal"
        return (f"<OBBReceiver "
                f"address={self.address} "
                f"mode={mode} "
                f"running={self.receiver_thread is not None and self.receiver_thread.is_alive()}>")
