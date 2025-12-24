"""
Base Receiver - Abstract base class for all data receivers

Architecture based on recvOBB.py multi-threading pattern:
- Threading + Queue architecture
- Non-blocking operations
- Graceful shutdown with Event signals
"""

import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import zmq


class BaseReceiver(ABC):
    """
    Abstract base class for data receivers

    Implements the common multi-threading pattern:
    - Main thread: Data consumer (visualization, processing)
    - Receiver thread: ZMQ I/O operations (non-blocking)
    - Queue: Thread-safe data buffer (maxsize=10)
    - Event: Graceful shutdown signal
    """

    def __init__(self, address: str, channel_name: str, queue_size: int = 10):
        """
        Initialize receiver

        Args:
            address: ZMQ address (e.g., "tcp://localhost:5555")
            channel_name: Channel name for logging (e.g., "OBB", "PointCloud")
            queue_size: Maximum queue size (default: 10)
        """
        self.address = address
        self.channel_name = channel_name
        self.queue_size = queue_size

        # ZMQ context and socket (initialized in receiver thread)
        self.context: Optional[zmq.Context] = None
        self.socket: Optional[zmq.Socket] = None

        # Thread-safe data queue
        self.data_queue: queue.Queue = queue.Queue(maxsize=queue_size)

        # Threading control
        self.stop_event = threading.Event()
        self.receiver_thread: Optional[threading.Thread] = None

        # Statistics
        self.msg_count = 0
        self.error_count = 0
        self.last_receive_time: Optional[float] = None

    def start(self) -> None:
        """Start the receiver thread"""
        if self.receiver_thread is not None and self.receiver_thread.is_alive():
            print(f"⚠️ [{self.channel_name}] Receiver already running")
            return

        # Reset stop event
        self.stop_event.clear()

        # Start receiver thread
        self.receiver_thread = threading.Thread(
            target=self._receiver_thread_func,
            daemon=True,
            name=f"{self.channel_name}-Receiver"
        )
        self.receiver_thread.start()
        print(f"✅ [{self.channel_name}] Receiver thread started on {self.address}")

    def stop(self, timeout: float = 2.0) -> None:
        """
        Stop the receiver thread gracefully

        Args:
            timeout: Maximum wait time for thread to stop (seconds)
        """
        if self.receiver_thread is None or not self.receiver_thread.is_alive():
            return

        # Signal thread to stop
        self.stop_event.set()

        # Wait for thread to finish
        self.receiver_thread.join(timeout=timeout)

        if self.receiver_thread.is_alive():
            print(f"⚠️ [{self.channel_name}] Receiver thread did not stop gracefully")
        else:
            print(f"✅ [{self.channel_name}] Receiver thread stopped")

        # Cleanup ZMQ resources
        self._cleanup_zmq()

    def get_data(self, block: bool = False, timeout: Optional[float] = None) -> Optional[Any]:
        """
        Get data from queue

        Args:
            block: Whether to block if queue is empty
            timeout: Maximum wait time (only used if block=True)

        Returns:
            Data from queue, or None if queue is empty
        """
        try:
            if block:
                return self.data_queue.get(timeout=timeout)
            else:
                return self.data_queue.get_nowait()
        except queue.Empty:
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get receiver statistics"""
        return {
            'channel': self.channel_name,
            'address': self.address,
            'msg_count': self.msg_count,
            'error_count': self.error_count,
            'queue_size': self.data_queue.qsize(),
            'is_running': self.receiver_thread is not None and self.receiver_thread.is_alive(),
            'last_receive_time': self.last_receive_time,
        }

    def _receiver_thread_func(self) -> None:
        """
        Receiver thread main function (I/O operations, non-blocking)

        Pattern from recvOBB.py:
        1. Initialize ZMQ socket
        2. Loop until stop_event is set
        3. Receive data with timeout
        4. Put data into queue (non-blocking)
        5. Handle queue full by dropping oldest data
        """
        # Initialize ZMQ socket
        self._init_zmq()

        while not self.stop_event.is_set():
            try:
                # Receive data (with timeout)
                data = self._receive_data()

                if data is not None:
                    self.msg_count += 1
                    self.last_receive_time = time.time()

                    # Try to put data into queue (non-blocking)
                    try:
                        self.data_queue.put_nowait(data)
                    except queue.Full:
                        # Queue full: drop oldest data, keep newest
                        try:
                            self.data_queue.get_nowait()  # Drop oldest
                            self.data_queue.put_nowait(data)  # Keep newest
                        except queue.Empty:
                            pass  # Queue already cleared by main thread

            except zmq.error.Again:
                # Timeout, no data available
                pass
            except Exception as e:
                # Other errors (connection error, parsing error, etc.)
                if not self.stop_event.is_set():
                    self.error_count += 1
                    print(f"⚠️ [{self.channel_name}] Receiver error: {e}")
                    time.sleep(0.1)  # Brief sleep to avoid rapid retries

    def _init_zmq(self) -> None:
        """Initialize ZMQ context and socket"""
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.connect(self.address)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all messages
        self.socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
        print(f"  [{self.channel_name}] ZMQ socket connected to {self.address}")

    def _cleanup_zmq(self) -> None:
        """Cleanup ZMQ resources"""
        if self.socket is not None:
            self.socket.close()
            self.socket = None

        if self.context is not None:
            self.context.term()
            self.context = None

    @abstractmethod
    def _receive_data(self) -> Optional[Any]:
        """
        Receive and parse data from ZMQ socket

        This method must be implemented by subclasses to handle
        specific data formats (JSON, BSON, binary, etc.)

        Returns:
            Parsed data, or None if no data available

        Raises:
            zmq.error.Again: Timeout (no data available)
            Exception: Parsing error or other errors
        """
        pass

    def __repr__(self) -> str:
        return (f"<{self.__class__.__name__} "
                f"channel={self.channel_name} "
                f"address={self.address} "
                f"running={self.receiver_thread is not None and self.receiver_thread.is_alive()}>")
