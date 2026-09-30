#pragma once
#include <stdint.h>
#include <stdbool.h>

#define PACKET_HEADER_MAGIC 0xAA
#define PACKET_TIMEOUT_MS   3000

#pragma pack(push, 1)
struct FireDataPacket {
    uint8_t  header;       // Magic header: 0xAA
    uint8_t  fire;         // 1 = fire detected, 0 = safe
    uint8_t  angle;        // Aim angle: 0-180 degrees
    uint32_t packetID;     // Monotonic counter
    uint8_t  riskScore;    // Assessed risk: 0-100
    uint16_t flameRaw;     // Raw ADC reading
    uint8_t  checksum;     // Simple XOR checksum of preceding bytes
};
#pragma pack(pop)

inline uint8_t calculate_packet_checksum(const struct FireDataPacket* pkt) {
    const uint8_t* bytes = (const uint8_t*)pkt;
    uint8_t cs = 0;
    // XOR all bytes except the last checksum byte
    for (size_t i = 0; i < sizeof(struct FireDataPacket) - 1; ++i) {
        cs ^= bytes[i];
    }
    return cs;
}

inline bool validate_packet(const struct FireDataPacket* pkt) {
    if (pkt->header != PACKET_HEADER_MAGIC) return false;
    if (pkt->angle > 180) return false;
    return (calculate_packet_checksum(pkt) == pkt->checksum);
}
