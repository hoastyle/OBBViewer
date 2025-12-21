cmake_minimum_required(VERSION 3.10)
project(OBBDemo)

set(CMAKE_CXX_STANDARD 17)

# 使用 Git Submodule 管理 cppzmq
add_subdirectory(thirdparty/cppzmq)

# 查找 zlib 库（用于压缩模式）
find_package(ZLIB REQUIRED)

add_executable(sender sender.cpp)
target_link_libraries(sender PRIVATE cppzmq ZLIB::ZLIB)
