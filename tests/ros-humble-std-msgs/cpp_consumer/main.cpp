#include <iostream>

#include <std_msgs/msg/string.hpp>

int main()
{
  std_msgs::msg::String msg;
  msg.data = "hello";
  std::cout << "std_msgs C++ consumer started fine: " << msg.data << std::endl;
  return 0;
}
