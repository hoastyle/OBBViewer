import pygame
from pygame.math import Vector3
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import zmq
import json
import math

import numpy as np
import time
import zlib
import bson
import sys

import argparse


class OBB:
    def __init__(self, type, position, rotation, size, collision):
        self.type = type
        self.position = Vector3(position)
        self.rotation = rotation
        self.size = Vector3(size)
        # Default white
        self.color = (1, 1, 1, 1)
        self.collision = collision


def draw_wire_cube(size=1.0, color=(1, 1, 1)):
    half_size = size / 2
    glBegin(GL_LINES)
    #  glColor3f(1, 1, 1)  # 白色线框
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


def quaternion_to_matrix(q):
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


def draw_obb(obb):
    glPushMatrix()
    glTranslatef(*obb.position)
    # 注意：OpenGL 使用列主序，而 numpy 数组是行主序，所以我们需要转置矩阵
    rotation = obb.rotation.flatten()
    glMultMatrixf(rotation)
    glColor4f(*obb.color)
    glScale(*obb.size)
    #  glutWireCube(1)
    #  draw_wire_cube()
    draw_wire_cube(1.0, obb.color)  # 绘制单位立方体
    glScalef(*obb.size)  # 缩放到 OBB 的实际大小

    glPopMatrix()


def draw_coordinate_system():
    glBegin(GL_LINES)
    # X axis (red)
    glColor3f(1, 0, 0)
    glVertex3f(0, 0, 0)
    glVertex3f(1, 0, 0)
    # Y axis (green)
    glColor3f(0, 1, 0)
    glVertex3f(0, 0, 0)
    glVertex3f(0, 1, 0)
    # Z axis (blue)
    glColor3f(0, 0, 1)
    glVertex3f(0, 0, 0)
    glVertex3f(0, 0, 1)
    glEnd()


def check_collision(obb1, obb2):
    # Simplified collision check (just checking distance)
    distance = obb1.position.distance_to(obb2.position)
    return distance < max(obb1.size.length(), obb2.size.length())


def resize(width, height):
    print(f"resize to {width} * {height}")
    if height == 0:
        height = 1
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, (width / height), 0.1, 50.0)
    glMatrixMode(GL_MODELVIEW)
    # Add following two expression to ensure display well
    glLoadIdentity()
    glTranslatef(0.0, 0.0, -5)


def event_handler(scale, rotation):
    global dragging
    global last_pos
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            return
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                dragging = True
                last_pos = pygame.mouse.get_pos()
            elif event.button == 4:  # Scroll up
                scale[0] *= 1.1
            elif event.button == 5:  # Scroll down
                scale[0] /= 1.1
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:  # Left mouse button
                dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if dragging:
                new_pos = pygame.mouse.get_pos()
                dx = new_pos[0] - last_pos[0]
                dy = new_pos[1] - last_pos[1]
                rotation[0] += dy * 0.5
                rotation[1] += dx * 0.5
                last_pos = new_pos
        elif event.type == VIDEORESIZE:
            resize(event.w, event.h)


def recv_obb(socket, obbs):
    try:
        message = socket.recv(flags=zmq.NOBLOCK)
        data = json.loads(message)
        if debug_info:
            print(f"Normal json message size1: {sys.getsizeof(message)/1024:.2f}KB")
        obbs[:] = [
            OBB(
                obb["type"],
                obb["position"],
                quaternion_to_matrix(obb["rotation"]),
                obb["size"],
                obb["collision_status"],
            )
            for obb in data
        ]
    except zmq.Again:
        pass  # No message available


def recv_compressed_data(socket, obbs, points):
    try:
        ori_data = socket.recv(flags=zmq.NOBLOCK)
        original_size = int.from_bytes(ori_data[:4], byteorder="big")
        decompressed_bson = zlib.decompress(ori_data)
        data = bson.loads(decompressed_bson)
        json_data = data["data"]
        if "points" in data:
            json_points = data["points"]
            w_points = True
        else:
            w_points = False

        if debug_info:
            print(
                f"Obstacle compressed message size: {sys.getsizeof(ori_data)/1024:.2f}KB"
            )
        obbs[:] = [
            OBB(
                obb["type"],
                obb["position"],
                quaternion_to_matrix(obb["rotation"]),
                obb["size"],
                obb["collision_status"],
            )
            for obb in json_data
        ]
        if w_points == True:
            points.resize((len(json_points[0]) // 3, 3), refcheck=False)
            points[:] = np.array(json_points, dtype=np.float32).reshape(-1, 3)
    except zmq.Again:
        pass  # No message available


def recv_compressed_obb(socket, obbs):
    try:
        ori_data = socket.recv(flags=zmq.NOBLOCK)
        original_size = int.from_bytes(ori_data[:4], byteorder="big")
        decompressed_bson = zlib.decompress(ori_data)
        data = bson.loads(decompressed_bson)
        json_data = data["data"]

        if debug_info:
            print(
                f"Obstacle compressed message size: {sys.getsizeof(ori_data)/1024:.2f}KB"
            )
        obbs[:] = [
            OBB(
                obb["type"],
                obb["position"],
                quaternion_to_matrix(obb["rotation"]),
                obb["size"],
                obb["collision_status"],
            )
            for obb in json_data
        ]
    except zmq.Again:
        pass  # No message available


def validate_ip_port(value):
    try:
        ip, port = value.split(":")
        port = int(port)
        if port < 1 or port > 65535:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Invalid IP:PORT format. Should be something like 192.168.1.1:8080"
        )
    return value


def draw_points(points):
    glBegin(GL_POINTS)
    for point in points:
        glVertex3fv(point)
    glEnd()


dragging = False
last_pos = None
debug_info = False


def main():
    # 创建 ArgumentParser 对象
    parser = argparse.ArgumentParser(
        description="A program that receives data in normal or compressed mode."
    )

    # 添加是否显示调试信息的参数
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Enable debug mode to show debug information",
    )

    # 添加接收数据模式的参数
    parser.add_argument(
        "-m",
        "--mode",
        choices=["n", "c"],
        default="normal",
        help="Data receiving mode: (n)normal or (c)compressed",
    )

    # 添加 IP 和端口号参数
    parser.add_argument(
        "-a",
        "--address",
        type=validate_ip_port,
        required=True,
        help="IP address and port number in format IP:PORT",
    )

    # 解析命令行参数
    args = parser.parse_args()

    # 使用参数
    if args.debug:
        print("Debug mode is enabled.")
        global debug_info
        debug_info = True

    print(f"Data receiving mode: {args.mode}")

    ip, port = args.address.split(":")
    print(f"IP address: {ip}")
    print(f"Port: {port}")

    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL | RESIZABLE)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -5)

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(f"tcp://{ip}:{port}")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    clock = pygame.time.Clock()

    rotation = [0, 0]
    translation = [0, 0, 0]
    # Use list to make it mutable
    scale = [1.0]

    obbs = []

    points = np.empty((0, 3), dtype=np.float32)

    try:
        while True:
            event_handler(scale, rotation)
            if args.mode == "c":
                recv_compressed_data(socket, obbs, points)
                #  recv_compressed_obb(socket, obbs)
            else:
                recv_obb(socket, obbs)

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            glPushMatrix()
            glTranslatef(*translation)
            glRotatef(rotation[0], 1, 0, 0)
            glRotatef(rotation[1], 0, 1, 0)
            glScalef(scale[0], scale[0], scale[0])

            draw_coordinate_system()

            for obb in obbs:
                if obb.collision == 1:
                    obb.color = (1, 1, 0, 1)  # Red
                elif obb.collision == 2:
                    obb.color = (1, 0, 0, 1)  # Red
                else:
                    obb.color = (1, 1, 1, 1)
                draw_obb(obb)

            draw_points(points)

            glPopMatrix()
            pygame.display.flip()
            clock.tick(60)
    except KeyboardInterrupt:
        print("程序被手动终止")
    finally:
        pygame.quit()
        sys.exit(0)


if __name__ == "__main__":
    main()
