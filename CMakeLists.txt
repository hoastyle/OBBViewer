cmake_minimum_required(VERSION 3.10)
project(OBBDemo)

set(CMAKE_CXX_STANDARD 17)

# 使用 Git Submodule 管理 cppzmq
add_subdirectory(thirdparty/cppzmq)

add_executable(sender sender.cpp)
target_link_libraries(sender PRIVATE cppzmq)
