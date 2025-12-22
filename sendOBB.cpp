/**
 * @file sendOBB.cpp
 * @brief OBB data sender using ZeroMQ (参考 LCPS 实现)
 *
 * 发送 OBB (Oriented Bounding Box) 数据到订阅者
 * 支持普通模式和压缩模式 (zlib + BSON)
 */

#include <chrono>
#include <cstring>
#include <iostream>
#include <nlohmann/json.hpp>
#include <thread>
#include <vector>
#include <zmq.hpp>
#include <zlib.h>

using json = nlohmann::json;

/**
 * @struct OBB
 * @brief Oriented Bounding Box 数据结构
 */
struct OBB {
    std::string type;                   // OBB 类型 (如 "obs", "sprWarn", "sprStop")
    std::array<double, 3> position;     // 位置 [x, y, z]
    std::array<double, 4> rotation;     // 四元数旋转 [w, x, y, z]
    std::array<double, 3> size;         // 尺寸 [width, height, depth]
    uint8_t collision_status;           // 碰撞状态 (0: 无碰撞, 1: 碰撞)
};

/**
 * @brief 生成测试用的 OBB 数据
 * @param count 生成 B 类型 OBB 的数量
 * @return OBB 向量
 */
std::vector<OBB> generateTestOBBs(int count) {
    std::vector<OBB> obbs;

    // 生成 A 类型 OBB (大型静态障碍物)
    obbs.push_back({
        "obs",                          // type
        {0.0, 0.0, 0.0},               // position
        {1.0, 0.0, 0.0, 0.0},          // rotation (identity quaternion)
        {5.0, 5.0, 5.0},               // size
        0                               // collision_status
    });

    // 生成 B 类型 OBB (动态障碍物)
    for (int i = 0; i < count; ++i) {
        obbs.push_back({
            "sprWarn",                  // type
            {2.0, 2.0, 2.0},           // position
            {1.0, 0.0, 0.0, 0.0},      // rotation
            {1.0, 1.0, 1.0},           // size
            i % 2                       // collision_status (交替)
        });
    }

    return obbs;
}

/**
 * @brief 将 OBB 序列化为 JSON (参考 LCPS::serializeOBB2Json)
 * @param obb OBB 对象
 * @param jsonSerializer JSON 对象引用
 */
void serializeOBB2Json(const OBB& obb, json& jsonSerializer) {
    json obbJson = {
        {"type", obb.type},
        {"position", obb.position},
        {"rotation", obb.rotation},
        {"size", obb.size},
        {"collision_status", obb.collision_status}
    };

    // 添加到 data 数组
    if (!jsonSerializer.contains("data")) {
        jsonSerializer["data"] = json::array();
    }
    jsonSerializer["data"].push_back(obbJson);
}

/**
 * @brief 使用 zlib 压缩数据 (参考 LCPS::compress_data)
 * @param data 原始数据
 * @return 压缩后的数据
 */
std::vector<uint8_t> compressData(const std::vector<uint8_t>& data) {
    uLongf compressed_size = compressBound(data.size());
    std::vector<uint8_t> compressed_data(compressed_size);

    int result = compress2(
        compressed_data.data(), &compressed_size,
        data.data(), data.size(),
        Z_BEST_COMPRESSION  // 使用最佳压缩级别
    );

    if (result != Z_OK) {
        throw std::runtime_error("Compression failed");
    }

    compressed_data.resize(compressed_size);
    return compressed_data;
}

/**
 * @brief 发送 OBB 数据 (参考 LCPS::sendOBB)
 * @param publisher ZMQ 发布者 socket
 * @param obbs OBB 数据向量
 * @param use_compression 是否使用压缩模式
 * @param index 消息索引（用于日志）
 */
void sendOBB(zmq::socket_t& publisher, const std::vector<OBB>& obbs,
             bool use_compression, int index) {
    json jsonSerializer;

    // 序列化所有 OBB 到 JSON
    for (const auto& obb : obbs) {
        serializeOBB2Json(obb, jsonSerializer);
    }

    zmq::send_result_t result;

    if (use_compression) {
        // 压缩模式: JSON → BSON → zlib 压缩 → ZMQ 发送
        std::vector<uint8_t> bson = json::to_bson(jsonSerializer);
        std::vector<uint8_t> compressed_bson = compressData(bson);

        zmq::message_t zmq_msg(compressed_bson.size());
        std::memcpy(zmq_msg.data(), compressed_bson.data(), compressed_bson.size());

        result = publisher.send(zmq_msg, zmq::send_flags::dontwait);

        std::cout << "[" << index << "] Sent compressed OBB data: "
                  << bson.size() << " bytes → "
                  << compressed_bson.size() << " bytes ("
                  << (100.0 * compressed_bson.size() / bson.size()) << "%)"
                  << std::endl;
    } else {
        // 普通模式: JSON → ZMQ 发送
        std::string msg = jsonSerializer.dump();
        zmq::message_t zmq_msg(msg.size());
        std::memcpy(zmq_msg.data(), msg.data(), msg.size());

        result = publisher.send(zmq_msg, zmq::send_flags::dontwait);

        std::cout << "[" << index << "] Sent normal OBB data: "
                  << msg.size() << " bytes"
                  << std::endl;
    }
}

/**
 * @brief 主函数
 */
int main(int argc, char* argv[]) {
    // 解析命令行参数
    std::string mode = "normal";
    int obb_count = 1;  // 默认生成 1 个 B 类型 OBB

    for (int i = 1; i < argc; i++) {
        if (std::string(argv[i]) == "-m" && i + 1 < argc) {
            mode = argv[i + 1];
            if (mode != "normal" && mode != "n" && mode != "compressed" && mode != "c") {
                std::cerr << "Invalid mode. Use 'normal'/'n' or 'compressed'/'c'" << std::endl;
                return 1;
            }
            i++;
        } else if (std::string(argv[i]) == "-c" && i + 1 < argc) {
            obb_count = std::stoi(argv[i + 1]);
            i++;
        }
    }

    bool use_compression = (mode == "compressed" || mode == "c");

    std::cout << "=== OBB Sender (参考 LCPS 实现) ===" << std::endl;
    std::cout << "Mode: " << (use_compression ? "compressed (BSON + zlib)" : "normal (JSON)") << std::endl;
    std::cout << "OBB count: " << (obb_count + 1) << " (1 obs + " << obb_count << " sprWarn)" << std::endl;
    std::cout << "Publishing to: tcp://*:5555" << std::endl;
    std::cout << "======================================" << std::endl;

    // 初始化 ZMQ
    zmq::context_t context(1);
    zmq::socket_t publisher(context, ZMQ_PUB);
    publisher.bind("tcp://*:5555");

    // 等待订阅者连接
    std::cout << "Waiting for subscribers..." << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(1));

    // 发送循环
    int index = 0;
    while (true) {
        auto obbs = generateTestOBBs(obb_count);
        sendOBB(publisher, obbs, use_compression, index);

        ++index;
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return 0;
}
