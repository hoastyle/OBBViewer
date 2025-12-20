import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *

# 定义三角形的顶点
vertices = [
    (1, -1, 0),
    (1, 1, 0),
    (-1, 1, 0),
]

# 定义三角形的边
edges = [
    (0, 1),
    (1, 2),
    (2, 0),
]

# 绘制三角形
def draw_triangle():
    glBegin(GL_LINES)  # 使用线段绘制
    for edge in edges:
        for vertex in edge:
            glVertex3fv(vertices[vertex])
    glEnd()

# 初始化 Pygame 和 OpenGL
def main():
    pygame.init()
    display = (800, 600)
    pygame.display.set_mode(display, DOUBLEBUF | OPENGL)
    gluPerspective(45, (display[0] / display[1]), 0.1, 50.0)  # 设置透视
    glTranslatef(0.0, 0.0, -5)  # 移动视点

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return

        #  glRotatef(1, 0, 1, 0)  # 旋转
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)  # 清除缓冲区
        draw_triangle()  # 绘制三角形
        pygame.display.flip()  # 更新显示
        pygame.time.wait(10)  # 等待一段时间

if __name__ == "__main__":
    main()
