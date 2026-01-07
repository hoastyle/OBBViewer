"""
Status Receiver - Receives LCPS system status data

Receives status data including:
- System state (IDLE, DETECTING, ALERTING, etc.)
- Performance metrics (FPS, latency, CPU usage, etc.)
- Collision detection results
"""

import json
from enum import Enum
from typing import Any, Dict, Optional

import zmq

from .base_receiver import BaseReceiver


class LCPSState(Enum):
    """LCPS system state enumeration"""
    IDLE = "idle"
    DETECTING = "detecting"
    ALERTING = "alerting"
    ERROR = "error"
    UNKNOWN = "unknown"


class StatusReceiver(BaseReceiver):
    """
    LCPS system status receiver

    Receives status data including system state and performance metrics.

    Data format (input):
    {
        "state": str,              # System state (see LCPSState enum)
        "timestamp": float,        # Unix timestamp
        "frame_id": int,           # Frame ID
        "metrics": {               # Performance metrics
            "fps": float,          # Frames per second
            "latency_ms": float,   # Processing latency in milliseconds
            "cpu_usage": float,    # CPU usage percentage (0-100)
            "memory_mb": float,    # Memory usage in MB
        },
        "detection": {             # Detection results
            "obb_count": int,      # Number of OBBs detected
            "collision_count": int,# Number of collisions
            "safe": bool,          # Overall safety status
        }
    }

    Data format (output, with parsed state):
    {
        "state": LCPSState,        # Parsed state enum
        "state_raw": str,          # Raw state string
        "timestamp": float,
        "frame_id": int,
        "metrics": dict,
        "detection": dict,
    }
    """

    def __init__(self, address: str, queue_size: int = 10):
        """
        Initialize Status receiver

        Args:
            address: ZMQ address (e.g., "tcp://localhost:6557")
            queue_size: Maximum queue size (default: 10)
        """
        super().__init__(address, "Status", queue_size)

        # Statistics
        self.state_counts: Dict[LCPSState, int] = {state: 0 for state in LCPSState}

    def _receive_data(self) -> Optional[Dict[str, Any]]:
        """
        Receive and parse status data

        Returns:
            Parsed status data dictionary

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
            raise RuntimeError(f"Failed to parse status data: {e}")

        # Validate data format
        if 'state' not in data:
            raise RuntimeError("Invalid status data: missing 'state' field")

        # Parse state enum
        state_raw = data['state']
        try:
            state = LCPSState(state_raw)
        except ValueError:
            state = LCPSState.UNKNOWN

        # Update state statistics
        self.state_counts[state] = self.state_counts.get(state, 0) + 1

        # Construct output data
        result = {
            'state': state,
            'state_raw': state_raw,
            'timestamp': data.get('timestamp', 0.0),
            'frame_id': data.get('frame_id', 0),
            'metrics': data.get('metrics', {}),
            'detection': data.get('detection', {}),
        }

        return result

    def get_latest_state(self) -> Optional[LCPSState]:
        """
        Get the latest system state (convenience method)

        Returns:
            Latest LCPSState, or None if no data available
        """
        data = self.get_data(block=False)
        if data is not None and 'state' in data:
            return data['state']
        return None

    def get_state_statistics(self) -> Dict[str, Any]:
        """Get state transition statistics"""
        total_states = sum(self.state_counts.values())

        state_percentages = {}
        for state, count in self.state_counts.items():
            pct = (count / total_states * 100) if total_states > 0 else 0.0
            state_percentages[state.value] = {
                'count': count,
                'percentage': pct
            }

        return {
            'total_states_received': total_states,
            'state_distribution': state_percentages,
        }

    def __repr__(self) -> str:
        return (f"<StatusReceiver "
                f"address={self.address} "
                f"running={self.receiver_thread is not None and self.receiver_thread.is_alive()}>")
