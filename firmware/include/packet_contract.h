#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

#define PACKET_HEADER_MAGIC 0xAA
#define PACKET_TIMEOUT_MS   1500

#pragma pack(push, 1)
struct FireDataPacket {
    uint8_t  header;       // Magic header: 0xAA
    uint8_t  fire;         // 1 = fire detected / activate response, 0 = safe / standby
    uint8_t  angle;        // Threat direction: 0-180 degrees
    uint32_t packetID;     // Monotonic packet sequence counter
    uint8_t  fireState;    // 0=NORMAL, 1=WARNING, 2=PRE_FIRE, 3=FIRE, 4=CRITICAL
    uint8_t  riskScore;    // Assessed risk level: 0-100
    char     zoneId[8];    // Physical zone identifier (e.g. "ZONE_1")
    uint8_t  checksum;     // XOR checksum of all preceding bytes
};
#pragma pack(pop)

inline uint8_t calculate_packet_checksum(const struct FireDataPacket* pkt) {
    const uint8_t* bytes = (const uint8_t*)pkt;
    uint8_t cs = 0;
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
