cmake_minimum_required(VERSION 3.10)
project(OBBDemo)

set(CMAKE_CXX_STANDARD 17)

# 使用 Git Submodule 管理 cppzmq
# 禁用 cppzmq 测试，避免下载 Catch2（加速 CMake 配置 10-45秒 → <1秒）
set(CPPZMQ_BUILD_TESTS OFF CACHE BOOL "Disable cppzmq tests" FORCE)
add_subdirectory(thirdparty/cppzmq)

# 查找 zlib 库（用于压缩模式）
find_package(ZLIB REQUIRED)

add_executable(sender sender.cpp)
target_link_libraries(sender PRIVATE cppzmq ZLIB::ZLIB)

# 新增：sendOBB 发送端 (参考 LCPS 实现)
add_executable(sendOBB sendOBB.cpp)
target_link_libraries(sendOBB PRIVATE cppzmq ZLIB::ZLIB)
