cmake_minimum_required(VERSION 3.20)
project(std_msgs_cpp_consumer CXX)

find_package(std_msgs REQUIRED)

add_executable(std_msgs_cpp_consumer main.cpp)
target_link_libraries(std_msgs_cpp_consumer ${std_msgs_TARGETS})
