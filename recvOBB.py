#!/usr/bin/env python3
"""
OBB 数据接收器 (参考 recv.py 实现)

接收 sendOBB.cpp 发送的 OBB 数据并显示
支持普通模式和压缩模式 (zlib + BSON)
"""

import argparse
import json
import sys
import time
import zlib
from typing import Dict, List, Any

import bson
import zmq


class OBBReceiver:
    """OBB 数据接收器类"""

    def __init__(self, address: str, mode: str):
        """
        初始化接收器

        Args:
            address: ZMQ 地址 (如 "localhost:5555")
            mode: 接收模式 ("normal" 或 "compressed")
        """
        self.address = address
        self.mode = mode
        self.use_compression = (mode in ["compressed", "c"])

        # 初始化 ZMQ
        self.context = zmq.Context()
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect(f"tcp://{address}")
        self.subscriber.setsockopt_string(zmq.SUBSCRIBE, "")

        # 统计信息
        self.msg_count = 0
        self.total_bytes_received = 0
        self.total_bytes_decompressed = 0

        print("=== OBB Receiver (参考 recv.py 实现) ===")
        print(f"Mode: {'compressed (BSON + zlib)' if self.use_compression else 'normal (JSON)'}")
        print(f"Subscribing to: tcp://{address}")
        print("========================================")
        print()

    def receive_normal(self) -> Dict[str, Any]:
        """
        接收普通模式数据 (JSON)

        Returns:
            解析后的 JSON 数据字典
        """
        message = self.subscriber.recv()
        self.total_bytes_received += len(message)

        data = json.loads(message.decode('utf-8'))
        return data

    def receive_compressed(self) -> Dict[str, Any]:
        """
        接收压缩模式数据 (zlib + BSON)

        Returns:
            解析后的数据字典
        """
        compressed_data = self.subscriber.recv()
        self.total_bytes_received += len(compressed_data)

        # 解压缩
        try:
            decompressed_data = zlib.decompress(compressed_data)
            self.total_bytes_decompressed += len(decompressed_data)

            # 解析 BSON
            # 注意：pymongo.bson 使用 BSON() 类或 json.loads(bson.json_util.dumps())
            # 但最简单的方式是用 nlohmann::json to_bson 生成的 BSON 可以直接用 json.loads()
            # 先尝试 JSON 解析（如果 BSON 是 JSON 包装的）
            try:
                data = json.loads(decompressed_data)
                return data
            except:
                # 如果是纯 BSON，使用 bson.decode()
                from bson import decode
                data = decode(decompressed_data)
                return data

        except zlib.error as e:
            print(f"❌ Decompression error: {e}")
            return {}
        except Exception as e:
            print(f"❌ BSON parsing error: {e}")
            return {}

    def display_obb_data(self, data: Dict[str, Any]) -> None:
        """
        显示接收到的 OBB 数据

        Args:
            data: OBB 数据字典
        """
        if not data or "data" not in data:
            print(f"[{self.msg_count}] ❌ Invalid data format")
            return

        obbs = data["data"]
        print(f"[{self.msg_count}] Received {len(obbs)} OBB(s):")

        for i, obb in enumerate(obbs):
            obb_type = obb.get("type", "unknown")
            position = obb.get("position", [0, 0, 0])
            rotation = obb.get("rotation", [1, 0, 0, 0])
            size = obb.get("size", [1, 1, 1])
            collision = obb.get("collision_status", 0)

            collision_status = "🔴 COLLISION" if collision == 1 else "🟢 SAFE"

            print(f"  OBB {i+1}:")
            print(f"    Type: {obb_type}")
            print(f"    Position: [{position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f}]")
            print(f"    Rotation: [w={rotation[0]:.2f}, x={rotation[1]:.2f}, y={rotation[2]:.2f}, z={rotation[3]:.2f}]")
            print(f"    Size: [{size[0]:.2f}, {size[1]:.2f}, {size[2]:.2f}]")
            print(f"    Status: {collision_status}")

        # 显示压缩率（如果是压缩模式）
        if self.use_compression and self.total_bytes_decompressed > 0:
            compression_ratio = (1 - self.total_bytes_received / self.total_bytes_decompressed) * 100
            print(f"  Compression: {self.total_bytes_received} bytes (原始: {self.total_bytes_decompressed} bytes, 压缩率: {compression_ratio:.1f}%)")

        print()

    def run(self) -> None:
        """运行接收循环"""
        try:
            while True:
                # 接收数据
                if self.use_compression:
                    data = self.receive_compressed()
                else:
                    data = self.receive_normal()

                # 显示数据
                self.display_obb_data(data)

                self.msg_count += 1

        except KeyboardInterrupt:
            print("\n\n=== 接收统计 ===")
            print(f"Total messages: {self.msg_count}")
            print(f"Total bytes received: {self.total_bytes_received}")
            if self.use_compression:
                print(f"Total bytes decompressed: {self.total_bytes_decompressed}")
                if self.total_bytes_decompressed > 0:
                    compression_ratio = (1 - self.total_bytes_received / self.total_bytes_decompressed) * 100
                    print(f"Overall compression ratio: {compression_ratio:.1f}%")
            print("=================")
            self.cleanup()

    def cleanup(self) -> None:
        """清理资源"""
        self.subscriber.close()
        self.context.term()
        print("Receiver stopped.")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="OBB 数据接收器 (参考 recv.py 实现)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 普通模式
  python3 recvOBB.py -a localhost:5555 -m n

  # 压缩模式
  python3 recvOBB.py -a localhost:5555 -m c
        """
    )

    parser.add_argument(
        "-a", "--address",
        default="localhost:5555",
        help="ZMQ 订阅地址 (默认: localhost:5555)"
    )

    parser.add_argument(
        "-m", "--mode",
        choices=["n", "normal", "c", "compressed"],
        default="n",
        help="接收模式: n/normal (普通) 或 c/compressed (压缩, 默认: n)"
    )

    args = parser.parse_args()

    # 创建并运行接收器
    receiver = OBBReceiver(args.address, args.mode)
    receiver.run()


if __name__ == "__main__":
    main()
