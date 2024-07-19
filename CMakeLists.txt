cmake_minimum_required(VERSION 3.10)
project(OBBDemo)

set(CMAKE_CXX_STANDARD 17)

find_package(cppzmq)

add_executable(sender sender.cpp)
target_link_libraries(sender PRIVATE cppzmq)
