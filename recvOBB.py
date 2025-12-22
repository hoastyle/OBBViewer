#!/usr/bin/env python3
"""
OBB 数据接收器 (参考 recv.py 实现)

接收 sendOBB.cpp 发送的 OBB 数据并显示
支持普通模式和压缩模式 (zlib + BSON)
支持可视化模式 (PyOpenGL + Pygame)
"""

import argparse
import json
import queue
import sys
import threading
import time
import zlib
from typing import Dict, List, Any, Optional

import bson
import zmq
import numpy as np

# 可视化相关导入（可选）
try:
    import pygame
    from pygame.math import Vector3
    from pygame.locals import *
    from OpenGL.GL import *
    from OpenGL.GLU import *
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("⚠️ 可视化库未安装，将禁用可视化模式")
    print("   安装方法: pip install pygame PyOpenGL")


# ===== 可视化相关类和函数 =====

class OBB:
    """OBB 3D 对象（用于可视化）"""
    def __init__(self, type, position, rotation, size, collision):
        self.type = type
        if VISUALIZATION_AVAILABLE:
            self.position = Vector3(position)
            self.size = Vector3(size)
        else:
            self.position = position
            self.size = size
        self.rotation = rotation
        self.color = (1, 1, 1, 1)  # 默认白色
        self.collision = collision


def quaternion_to_matrix(q):
    """四元数转旋转矩阵"""
    w, x, y, z = q
    r = [
        1 - 2 * y * y - 2 * z * z,
        2 * x * y - 2 * z * w,
        2 * x * z + 2 * y * w,
        0,
        2 * x * y + 2 * z * w,
        1 - 2 * x * x - 2 * z * z,
        2 * y * z - 2 * x * w,
        0,
        2 * x * z - 2 * y * w,
        2 * y * z + 2 * x * w,
        1 - 2 * x * x - 2 * y * y,
        0,
        0,
        0,
        0,
        1,
    ]
    return np.array(r).reshape(4, 4).T


def draw_wire_cube(size=1.0, color=(1, 1, 1)):
    """绘制线框立方体"""
    if not VISUALIZATION_AVAILABLE:
        return

    half_size = size / 2
    glBegin(GL_LINES)
    glColor3f(*color)

    # 前面
    glVertex3f(-half_size, -half_size, half_size)
    glVertex3f(half_size, -half_size, half_size)
    glVertex3f(half_size, -half_size, half_size)
    glVertex3f(half_size, half_size, half_size)
    glVertex3f(half_size, half_size, half_size)
    glVertex3f(-half_size, half_size, half_size)
    glVertex3f(-half_size, half_size, half_size)
    glVertex3f(-half_size, -half_size, half_size)

    # 后面
    glVertex3f(-half_size, -half_size, -half_size)
    glVertex3f(half_size, -half_size, -half_size)
    glVertex3f(half_size, -half_size, -half_size)
    glVertex3f(half_size, half_size, -half_size)
    glVertex3f(half_size, half_size, -half_size)
    glVertex3f(-half_size, half_size, -half_size)
    glVertex3f(-half_size, half_size, -half_size)
    glVertex3f(-half_size, -half_size, -half_size)

    # 连接前后面
    glVertex3f(-half_size, -half_size, half_size)
    glVertex3f(-half_size, -half_size, -half_size)
    glVertex3f(half_size, -half_size, half_size)
    glVertex3f(half_size, -half_size, -half_size)
    glVertex3f(half_size, half_size, half_size)
    glVertex3f(half_size, half_size, -half_size)
    glVertex3f(-half_size, half_size, half_size)
    glVertex3f(-half_size, half_size, -half_size)

    glEnd()


def draw_obb(obb):
    """绘制 OBB"""
    if not VISUALIZATION_AVAILABLE:
        return

    glPushMatrix()
    glTranslatef(*obb.position)
    rotation = obb.rotation.flatten()
    glMultMatrixf(rotation)
    glColor4f(*obb.color)
    glScale(*obb.size)
    draw_wire_cube(1.0, obb.color)
    glPopMatrix()


def draw_coordinate_system():
    """绘制坐标系"""
    if not VISUALIZATION_AVAILABLE:
        return

    glBegin(GL_LINES)
    # X 轴 (红色)
    glColor3f(1, 0, 0)
    glVertex3f(0, 0, 0)
    glVertex3f(1, 0, 0)
    # Y 轴 (绿色)
    glColor3f(0, 1, 0)
    glVertex3f(0, 0, 0)
    glVertex3f(0, 1, 0)
    # Z 轴 (蓝色)
    glColor3f(0, 0, 1)
    glVertex3f(0, 0, 0)
    glVertex3f(0, 0, 1)
    glEnd()


# ===== OBB 接收器类 =====

class OBBReceiver:
    """OBB 数据接收器类"""

    def __init__(self, address: str, mode: str, visualize: bool = False):
        """
        初始化接收器

        Args:
            address: ZMQ 地址 (如 "localhost:5555")
            mode: 接收模式 ("normal" 或 "compressed")
            visualize: 是否启用可视化模式
        """
        self.address = address
        self.mode = mode
        self.use_compression = (mode in ["compressed", "c"])
        self.visualize = visualize and VISUALIZATION_AVAILABLE

        # 初始化 ZMQ
        self.context = zmq.Context()
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect(f"tcp://{address}")
        self.subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
        self.subscriber.setsockopt(zmq.RCVTIMEO, 100)  # 100ms 超时

        # 统计信息
        self.msg_count = 0
        self.total_bytes_received = 0
        self.total_bytes_decompressed = 0
        self.type_counts = {}  # 类型统计 {type_name: count}
        self.collision_count = 0  # 碰撞计数
        self.safe_count = 0  # 安全计数

        # 可视化相关
        self.obbs = []  # 当前 OBB 列表
        self.rotation = [0.0, 0.0]  # 视角旋转
        self.scale = [1.0]  # 缩放
        self.dragging = False
        self.last_pos = (0, 0)

        # 多线程架构（接收和渲染分离）
        self.data_queue = queue.Queue(maxsize=10)  # 线程安全的数据缓冲
        self.stop_event = threading.Event()  # 优雅退出信号
        self.receiver_thread = None  # 接收线程

        print("=== OBB Receiver (参考 recv.py 实现) ===")
        print(f"Mode: {'compressed (BSON + zlib)' if self.use_compression else 'normal (JSON)'}")
        print(f"Visualize: {'enabled (PyOpenGL)' if self.visualize else 'disabled (text only)'}")
        print(f"Subscribing to: tcp://{address}")
        print(f"Threading: {'enabled (receive/render separation)' if self.visualize else 'disabled (text mode)'}")
        print("========================================")
        print()

        # 初始化可视化环境
        if self.visualize:
            self._init_visualization()

    def receive_normal(self) -> Dict[str, Any]:
        """
        接收普通模式数据 (JSON)

        Returns:
            解析后的 JSON 数据字典
        """
        message = self.subscriber.recv()
        self.total_bytes_received += len(message)

        try:
            data = json.loads(message.decode('utf-8'))
        except UnicodeDecodeError:
            print("\n❌ 错误: 无法解码数据为 UTF-8")
            print("可能原因: 发送端使用了压缩模式 (-m c)，但接收端使用了普通模式 (-m n)")
            print("解决方案: 确保发送端和接收端的 -m 参数一致")
            print("  示例: ./sendOBB -m n  配合  python recvOBB.py -a localhost:5555 -m n\n")
            raise RuntimeError("模式不匹配: 接收端使用 normal mode，但数据似乎是压缩格式")

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

    def _init_visualization(self) -> None:
        """初始化可视化环境（PyOpenGL + Pygame）"""
        if not VISUALIZATION_AVAILABLE:
            return

        pygame.init()
        display = (800, 600)
        pygame.display.set_mode(display, DOUBLEBUF | OPENGL | RESIZABLE)
        pygame.display.set_caption("OBB Receiver - Visualization Mode")

        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef(0.0, 0.0, -5)

    def _handle_events(self) -> bool:
        """处理 Pygame 事件

        Returns:
            如果用户关闭窗口返回 False，否则返回 True
        """
        if not VISUALIZATION_AVAILABLE:
            return True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键
                    self.dragging = True
                    self.last_pos = pygame.mouse.get_pos()
                elif event.button == 4:  # 滚轮向上
                    self.scale[0] *= 1.1
                elif event.button == 5:  # 滚轮向下
                    self.scale[0] /= 1.1
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if self.dragging:
                    new_pos = pygame.mouse.get_pos()
                    dx = new_pos[0] - self.last_pos[0]
                    dy = new_pos[1] - self.last_pos[1]
                    self.rotation[0] += dy * 0.5
                    self.rotation[1] += dx * 0.5
                    self.last_pos = new_pos
            elif event.type == VIDEORESIZE:
                glViewport(0, 0, event.w, event.h)
                glMatrixMode(GL_PROJECTION)
                glLoadIdentity()
                gluPerspective(45, (event.w / event.h), 0.1, 50.0)
                glMatrixMode(GL_MODELVIEW)
        return True

    def _render_scene(self) -> None:
        """渲染 3D 场景"""
        if not VISUALIZATION_AVAILABLE:
            return

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glPushMatrix()

        # 应用用户旋转和缩放
        glScalef(self.scale[0], self.scale[0], self.scale[0])
        glRotatef(self.rotation[0], 1, 0, 0)
        glRotatef(self.rotation[1], 0, 1, 0)

        # 绘制坐标系
        draw_coordinate_system()

        # 绘制所有 OBB
        for obb in self.obbs:
            draw_obb(obb)

        glPopMatrix()
        pygame.display.flip()

    def _update_type_statistics(self, data: Dict[str, Any]) -> None:
        """更新 OBB 类型和碰撞状态统计

        Args:
            data: 接收到的 OBB 数据字典
        """
        if not data or "data" not in data:
            return

        obbs_data = data["data"]
        for obb_dict in obbs_data:
            # 统计类型
            obb_type = obb_dict.get("type", "unknown")
            self.type_counts[obb_type] = self.type_counts.get(obb_type, 0) + 1

            # 统计碰撞状态
            collision_status = obb_dict.get("collision_status", 0)
            if collision_status == 1:
                self.collision_count += 1
            else:
                self.safe_count += 1

    def _update_obbs_from_data(self, data: Dict[str, Any]) -> None:
        """从接收的数据更新 OBB 列表

        Args:
            data: 接收到的 OBB 数据字典
        """
        if not data or "data" not in data:
            return

        # 更新类型统计
        self._update_type_statistics(data)

        obbs_data = data["data"]
        self.obbs = []

        for obb_dict in obbs_data:
            obb = OBB(
                obb_dict.get("type", "unknown"),
                obb_dict.get("position", [0, 0, 0]),
                quaternion_to_matrix(obb_dict.get("rotation", [1, 0, 0, 0])),
                obb_dict.get("size", [1, 1, 1]),
                obb_dict.get("collision_status", 0)
            )

            # 根据碰撞状态设置颜色
            if obb.collision == 1:
                obb.color = (1, 0, 0, 1)  # 红色（碰撞）
            else:
                obb.color = (0, 1, 0, 1)  # 绿色（安全）

            self.obbs.append(obb)

    def display_obb_data(self, data: Dict[str, Any]) -> None:
        """
        显示接收到的 OBB 数据

        Args:
            data: OBB 数据字典
        """
        if not data or "data" not in data:
            print(f"[{self.msg_count}] ❌ Invalid data format")
            return

        # 更新类型统计
        self._update_type_statistics(data)

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
        if self.visualize:
            self._run_visualized()
        else:
            self._run_text_mode()

    def _run_text_mode(self) -> None:
        """运行文本模式（原有功能）"""
        try:
            while True:
                try:
                    # 接收数据
                    if self.use_compression:
                        data = self.receive_compressed()
                    else:
                        data = self.receive_normal()

                    # 显示数据
                    self.display_obb_data(data)

                    self.msg_count += 1

                except zmq.error.Again:
                    # 超时但无数据，继续等待
                    pass

        except KeyboardInterrupt:
            print("\n\n=== 接收统计 ===")
            print(f"Total messages: {self.msg_count}")
            print(f"Total bytes received: {self.total_bytes_received}")
            if self.use_compression:
                print(f"Total bytes decompressed: {self.total_bytes_decompressed}")
                if self.total_bytes_decompressed > 0:
                    compression_ratio = (1 - self.total_bytes_received / self.total_bytes_decompressed) * 100
                    print(f"Overall compression ratio: {compression_ratio:.1f}%")

            # 显示类型统计
            if self.type_counts:
                print("\nOBB 类型统计:")
                total_obbs = sum(self.type_counts.values())
                for obb_type, count in sorted(self.type_counts.items()):
                    percentage = (count / total_obbs * 100) if total_obbs > 0 else 0
                    print(f"  {obb_type}: {count} ({percentage:.1f}%)")
                print(f"  总计: {total_obbs}")

            # 显示碰撞状态统计
            if self.collision_count > 0 or self.safe_count > 0:
                total_status = self.collision_count + self.safe_count
                print("\n碰撞状态统计:")
                safe_pct = (self.safe_count / total_status * 100) if total_status > 0 else 0
                collision_pct = (self.collision_count / total_status * 100) if total_status > 0 else 0
                print(f"  🟢 安全: {self.safe_count} ({safe_pct:.1f}%)")
                print(f"  🔴 碰撞: {self.collision_count} ({collision_pct:.1f}%)")

            print("=================")
            self.cleanup()

    def _receiver_thread_func(self) -> None:
        """接收线程主函数（I/O 操作，不阻塞渲染）"""
        while not self.stop_event.is_set():
            try:
                # 接收数据（非阻塞，100ms 超时）
                if self.use_compression:
                    data = self.receive_compressed()
                else:
                    data = self.receive_normal()

                if data:
                    # 尝试放入队列（非阻塞）
                    try:
                        self.data_queue.put_nowait(data)
                    except queue.Full:
                        # 队列满，清空最旧数据，放入最新数据
                        try:
                            self.data_queue.get_nowait()  # 丢弃最旧数据
                            self.data_queue.put_nowait(data)  # 放入最新数据
                        except queue.Empty:
                            pass  # 队列已被主线程清空

            except zmq.error.Again:
                # 超时但无数据，继续等待
                pass
            except Exception as e:
                # 其他异常（如连接错误），打印并继续
                if not self.stop_event.is_set():
                    print(f"⚠️ Receiver thread error: {e}")
                    time.sleep(0.1)  # 短暂休眠避免快速重试

    def _run_visualized(self) -> None:
        """运行可视化模式（多线程架构）"""
        if not VISUALIZATION_AVAILABLE:
            print("❌ 可视化模式不可用，退回到文本模式")
            self._run_text_mode()
            return

        print("🎨 可视化模式启动（多线程架构）")
        print("   - 主线程: Pygame 主循环 + OpenGL 渲染（60 FPS）")
        print("   - 接收线程: ZMQ 数据接收和解析（I/O 操作不阻塞渲染）")
        print("   - 左键拖动: 旋转视角")
        print("   - 滚轮: 缩放")
        print("   - ESC/关闭窗口: 退出")
        print()

        # 启动接收线程
        self.receiver_thread = threading.Thread(
            target=self._receiver_thread_func,
            daemon=True,
            name="OBB-Receiver"
        )
        self.receiver_thread.start()
        print("✅ 接收线程已启动")

        try:
            clock = pygame.time.Clock()
            running = True

            while running:
                # 处理事件
                running = self._handle_events()

                # 从队列获取数据（非阻塞）
                try:
                    data = self.data_queue.get_nowait()

                    if data:
                        self._update_obbs_from_data(data)
                        self.msg_count += 1

                        # 打印简洁的接收信息
                        obbs = data.get("data", [])
                        type_summary = {}
                        for obb in obbs:
                            obb_type = obb.get("type", "unknown")
                            type_summary[obb_type] = type_summary.get(obb_type, 0) + 1

                        summary_str = ", ".join([f"{t}:{c}" for t, c in sorted(type_summary.items())])
                        print(f"[{self.msg_count}] Received {len(obbs)} OBB(s) - {summary_str}")

                except queue.Empty:
                    pass  # 队列为空，继续渲染

                # 渲染场景（保持 60 FPS）
                self._render_scene()

                # 控制帧率
                clock.tick(60)

                # 更新窗口标题显示 FPS
                fps = clock.get_fps()
                pygame.display.set_caption(f"OBB Receiver - FPS: {fps:.1f} | Messages: {self.msg_count}")

        except KeyboardInterrupt:
            pass
        finally:
            # 停止接收线程
            print("\n🛑 正在停止接收线程...")
            self.stop_event.set()  # 设置停止信号
            if self.receiver_thread and self.receiver_thread.is_alive():
                self.receiver_thread.join(timeout=2)  # 等待线程退出（最多2秒）
                if self.receiver_thread.is_alive():
                    print("⚠️ 接收线程未在超时时间内退出")
                else:
                    print("✅ 接收线程已停止")

            print("\n=== 接收统计 ===")
            print(f"Total messages: {self.msg_count}")
            print(f"Total bytes received: {self.total_bytes_received}")
            if self.use_compression:
                print(f"Total bytes decompressed: {self.total_bytes_decompressed}")
                if self.total_bytes_decompressed > 0:
                    compression_ratio = (1 - self.total_bytes_received / self.total_bytes_decompressed) * 100
                    print(f"Overall compression ratio: {compression_ratio:.1f}%")

            # 显示类型统计
            if self.type_counts:
                print("\nOBB 类型统计:")
                total_obbs = sum(self.type_counts.values())
                for obb_type, count in sorted(self.type_counts.items()):
                    percentage = (count / total_obbs * 100) if total_obbs > 0 else 0
                    print(f"  {obb_type}: {count} ({percentage:.1f}%)")
                print(f"  总计: {total_obbs}")

            # 显示碰撞状态统计
            if self.collision_count > 0 or self.safe_count > 0:
                total_status = self.collision_count + self.safe_count
                print("\n碰撞状态统计:")
                safe_pct = (self.safe_count / total_status * 100) if total_status > 0 else 0
                collision_pct = (self.collision_count / total_status * 100) if total_status > 0 else 0
                print(f"  🟢 安全: {self.safe_count} ({safe_pct:.1f}%)")
                print(f"  🔴 碰撞: {self.collision_count} ({collision_pct:.1f}%)")

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
  # 普通模式（文本输出）
  python3 recvOBB.py -a localhost:5555 -m n

  # 压缩模式（文本输出）
  python3 recvOBB.py -a localhost:5555 -m c

  # 可视化模式（3D 渲染）
  python3 recvOBB.py -a localhost:5555 -m n -v

  # 压缩模式 + 可视化
  python3 recvOBB.py -a localhost:5555 -m c --visualize
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

    parser.add_argument(
        "-v", "--visualize",
        action="store_true",
        help="启用 3D 可视化模式 (需要 PyOpenGL 和 Pygame)"
    )

    args = parser.parse_args()

    # 创建并运行接收器
    receiver = OBBReceiver(args.address, args.mode, visualize=args.visualize)
    receiver.run()


if __name__ == "__main__":
    main()
