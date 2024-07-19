import pygame
from pygame.math import Vector3
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import zmq
import json
import math

class OBB:
    def __init__(self, type, position, rotation, size):
        self.type = type
        self.position = Vector3(position)
        self.rotation = Vector3(rotation)
        self.size = Vector3(size)
        self.color = (1, 1, 1, 1)  # Default white

def draw_wire_cube(size=1.0):
    half_size = size / 2
    glBegin(GL_LINES)
    glColor3f(1, 1, 1)  # 白色线框
    
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
    glPushMatrix()
    glTranslatef(*obb.position)
    glRotatef(obb.rotation.x, 1, 0, 0)
    glRotatef(obb.rotation.y, 0, 1, 0)
    glRotatef(obb.rotation.z, 0, 0, 1)
    glColor4f(*obb.color)
    glScale(*obb.size)
    #  glutWireCube(1)
    #  draw_wire_cube()
    draw_wire_cube(1.0)  # 绘制单位立方体
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

def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)
    glTranslatef(0.0, 0.0, -5)

    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://192.168.71.38:5555")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    clock = pygame.time.Clock()

    rotation = [0, 0]
    translation = [0, 0, 0]
    scale = 1.0

    dragging = False
    last_pos = None

    obbs = []

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button
                    dragging = True
                    last_pos = pygame.mouse.get_pos()
                elif event.button == 4:  # Scroll up
                    scale *= 1.1
                elif event.button == 5:  # Scroll down
                    scale /= 1.1
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

        try:
            message = socket.recv(flags=zmq.NOBLOCK)
            data = json.loads(message)
            obbs = [OBB(obb['type'], obb['position'], obb['rotation'], obb['size']) for obb in data]
        except zmq.Again:
            pass  # No message available

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glPushMatrix()
        glTranslatef(*translation)
        glRotatef(rotation[0], 1, 0, 0)
        glRotatef(rotation[1], 0, 1, 0)
        glScalef(scale, scale, scale)

        draw_coordinate_system()

        a_obb = next((obb for obb in obbs if obb.type == 'A'), None)
        if a_obb:
            for obb in obbs:
                if obb.type == 'B':
                    if check_collision(a_obb, obb):
                        obb.color = (1, 0, 0, 1)  # Red
                    else:
                        obb.color = (0, 1, 0, 1)  # Green

        #  print(len(obbs))
        for obb in obbs:
            #  print(obb.type)
            draw_obb(obb)

        glPopMatrix()
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
