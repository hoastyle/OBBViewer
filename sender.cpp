#include <chrono>
#include <iostream>
#include <nlohmann/json.hpp>
#include <random>
#include <thread>
#include <vector>
#include <zmq.hpp>
#include <zlib.h>
#include <cstring>

using json = nlohmann::json;

struct OBB
{
    std::string type;
    std::array<double, 3> position;
    std::array<double, 4> rotation;  // Quaternion [w, x, y, z]
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
        {0.0, 0.0, 0.0},           // position
        {1.0, 0.0, 0.0, 0.0},      // rotation (identity quaternion: no rotation)
        {5.0, 5.0, 5.0}});         // size

    // Generate B type OBBs
    for (int i = 1; i <= count; ++i) {
        obbs.push_back({"B",
            {2.0, 2.0, 2.0},       // position
            {1.0, 0.0, 0.0, 0.0},  // rotation (identity quaternion: no rotation)
            {1.0, 1.0, 1.0}});     // size
    }

    return obbs;
}

// Compress JSON string using zlib
std::vector<uint8_t> compressData(const std::string& json_str)
{
    uLongf compressed_size = compressBound(json_str.size());
    std::vector<uint8_t> compressed_data(compressed_size + 4);  // +4 for size prefix

    // Store original size in first 4 bytes (big-endian)
    uint32_t orig_size = json_str.size();
    compressed_data[0] = (orig_size >> 24) & 0xFF;
    compressed_data[1] = (orig_size >> 16) & 0xFF;
    compressed_data[2] = (orig_size >> 8) & 0xFF;
    compressed_data[3] = orig_size & 0xFF;

    // Compress data
    int result = compress(compressed_data.data() + 4, &compressed_size,
                         reinterpret_cast<const uint8_t*>(json_str.data()),
                         json_str.size());

    if (result != Z_OK) {
        std::cerr << "Compression failed!" << std::endl;
        return {};
    }

    compressed_data.resize(compressed_size + 4);
    return compressed_data;
}

int main(int argc, char* argv[])
{
    // Parse command line arguments
    std::string mode = "normal";  // default mode
    for (int i = 1; i < argc; i++) {
        if (std::string(argv[i]) == "-m" && i + 1 < argc) {
            mode = argv[i + 1];
            if (mode != "normal" && mode != "n" && mode != "compressed" && mode != "c") {
                std::cerr << "Invalid mode. Use 'normal'/'n' or 'compressed'/'c'" << std::endl;
                return 1;
            }
            break;
        }
    }

    bool use_compression = (mode == "compressed" || mode == "c");
    std::cout << "Sender mode: " << (use_compression ? "compressed" : "normal") << std::endl;

    zmq::context_t context(1);
    zmq::socket_t publisher(context, ZMQ_PUB);
    publisher.bind("tcp://*:5555");

    int index = 0;
    while (true) {
        // auto obbs = generateRandomOBBs(100);
        auto obbs = generateRandomOBBs(1);

        // Get current timestamp (microsecond precision)
        auto now = std::chrono::system_clock::now();
        auto duration = now.time_since_epoch();
        double timestamp = std::chrono::duration<double>(duration).count();

        // Build message following LCPS Data Protocol
        json j = json::object();

        // Header
        j["header"] = {
            {"version", "1.0"},
            {"timestamp", timestamp},
            {"seq_id", index},
            {"source", "sender_cpp"}
        };

        // Payload
        json obbs_array = json::array();
        for (const auto& obb : obbs) {
            obbs_array.push_back({
                {"type", obb.type},
                {"position", obb.position},
                {"rotation", obb.rotation},
                {"size", obb.size},
                {"collision_status", 0}
            });
        }

        j["payload"] = {
            {"type", "obb_list"},
            {"frame_id", "laser_frame"},
            {"count", obbs.size()},
            {"obbs", obbs_array}
        };

        if (use_compression) {
            // Compressed mode
            std::string json_str = j.dump();
            auto compressed = compressData(json_str);

            if (compressed.empty()) {
                std::cerr << "Compression failed, skipping..." << std::endl;
                continue;
            }

            zmq::message_t zmq_msg(compressed.size());
            memcpy(zmq_msg.data(), compressed.data(), compressed.size());
            publisher.send(zmq_msg, zmq::send_flags::dontwait);

            std::cout << "Send compressed OBB " << index
                      << " (original: " << json_str.size()
                      << " bytes, compressed: " << compressed.size() << " bytes)" << std::endl;
        } else {
            // Normal mode (LCPS protocol format)
            std::string msg = j.dump();
            zmq::message_t zmq_msg(msg.size());
            memcpy(zmq_msg.data(), msg.data(), msg.size());
            publisher.send(zmq_msg, zmq::send_flags::dontwait);

            std::cout << "Send OBB " << index << " (timestamp: " << timestamp << ")" << std::endl;
        }

        ++index;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return 0;
}
