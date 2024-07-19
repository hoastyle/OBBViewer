#include <chrono>
#include <iostream>
#include <nlohmann/json.hpp>
#include <random>
#include <thread>
#include <vector>
#include <zmq.hpp>

using json = nlohmann::json;

struct OBB
{
    std::string type;
    std::array<double, 3> position;
    std::array<double, 3> rotation;
    std::array<double, 3> size;
};

std::vector<OBB> generateRandomOBBs(int count)
{
    std::vector<OBB> obbs;
    // std::random_device rd;
    // std::mt19937 gen(rd());
    // std::uniform_real_distribution<> dis(-10.0, 10.0);
    // std::uniform_real_distribution<> size_dis(0.5, 2.0);

    // Generate A type OBB
    obbs.push_back({"A",
        // {dis(gen), dis(gen), dis(gen)},
        // {dis(gen), dis(gen), dis(gen)},
        // {size_dis(gen), size_dis(gen), size_dis(gen)}
        {0.0, 0.0, 0.0}, {0.0, 0.0, 0.0}, {5.0, 5.0, 5.0}});

    // Generate B type OBBs
    for (int i = 1; i <= count; ++i) {
        obbs.push_back({"B",
            // {dis(gen), dis(gen), dis(gen)},
            // {dis(gen), dis(gen), dis(gen)},
            // {size_dis(gen), size_dis(gen), size_dis(gen)}
            {2.0, 2.0, 2.0}, {0.0, 0.0, 0.0}, {1.0, 1.0, 1.0}});
    }

    return obbs;
}

int main()
{
    zmq::context_t context(1);
    zmq::socket_t publisher(context, ZMQ_PUB);
    publisher.bind("tcp://*:5555");

    int index = 0;
    while (true) {
        // auto obbs = generateRandomOBBs(100);
        auto obbs = generateRandomOBBs(1);
        json j;
        for (const auto& obb : obbs) {
            j.push_back({{"type", obb.type}, {"position", obb.position}, {"rotation", obb.rotation},
                {"size", obb.size}});
        }

        std::string msg = j.dump();
        zmq::message_t zmq_msg(msg.size());
        memcpy(zmq_msg.data(), msg.data(), msg.size());
        publisher.send(zmq_msg, zmq::send_flags::dontwait);

        std::cout << "Send OBB " << index << std::endl;
        ++index;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return 0;
}
