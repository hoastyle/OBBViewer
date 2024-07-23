import pygame
from pygame.math import Vector3
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import zmq
import json
import math

import numpy as np


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


dragging = False
last_pos = None


def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL | RESIZABLE)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -5)

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    #  socket.connect("tcp://192.168.71.38:5555")
    socket.connect("tcp://localhost:5555")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    clock = pygame.time.Clock()

    rotation = [0, 0]
    translation = [0, 0, 0]
    # Use list to make it mutable
    scale = [1.0]

    obbs = []

    while True:
        event_handler(scale, rotation)
        recv_obb(socket, obbs)

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glPushMatrix()
        glTranslatef(*translation)
        glRotatef(rotation[0], 1, 0, 0)
        glRotatef(rotation[1], 0, 1, 0)
        glScalef(scale[0], scale[0], scale[0])

        draw_coordinate_system()

        for obb in obbs:
            if obb.type == "spreader" or obb.type == "sprCntr":
                obb.color = (1, 1, 1, 1)
            elif obb.type == "obs":
                if obb.collision == 1:
                    obb.color = (1, 1, 0, 1)  # Red
                elif obb.collision == 2:
                    obb.color = (1, 0, 0, 1)  # Red
                else:
                    obb.color = (1, 1, 1, 1)
            draw_obb(obb)

        glPopMatrix()
        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
