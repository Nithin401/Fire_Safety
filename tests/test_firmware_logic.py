import struct
import pytest

PACKET_HEADER_MAGIC = 0xAA
PACKET_TIMEOUT_MS = 3000

# Packet format: B (header), B (fire), B (angle), I (packetID), B (riskScore), H (flameRaw), B (checksum)
PACKET_FORMAT = "<BBBIHHB"

def calculate_checksum(data_bytes):
    cs = 0
    for b in data_bytes[:-1]:
        cs ^= b
    return cs

def create_packet(fire, angle, packet_id, risk_score, flame_raw):
    partial = struct.pack("<BBBIHB", PACKET_HEADER_MAGIC, fire, angle, packet_id, risk_score, flame_raw)
    cs = 0
    for b in partial:
        cs ^= b
    return partial + bytes([cs])

def unpack_and_validate(packet_bytes):
    if len(packet_bytes) != 11:
        return False, None
    header, fire, angle, packet_id, risk_score, flame_raw, checksum = struct.unpack("<BBBIHBB", packet_bytes)
    if header != PACKET_HEADER_MAGIC:
        return False, None
    if angle > 180:
        return False, None
    cs = 0
    for b in packet_bytes[:-1]:
        cs ^= b
    if cs != checksum:
        return False, None
    return True, {
        "fire": bool(fire),
        "angle": angle,
        "packetID": packet_id,
        "riskScore": risk_score,
        "flameRaw": flame_raw
    }

def test_packet_contract_serialization_and_validation():
    pkt = create_packet(fire=1, angle=75, packet_id=1024, risk_score=95, flame_raw=180)
    valid, data = unpack_and_validate(pkt)
    assert valid is True
    assert data["fire"] is True
    assert data["angle"] == 75
    assert data["packetID"] == 1024
    assert data["riskScore"] == 95
    assert data["flameRaw"] == 180

def test_packet_contract_corrupted_checksum():
    pkt = bytearray(create_packet(fire=1, angle=75, packet_id=1024, risk_score=95, flame_raw=180))
    pkt[-1] ^= 0xFF  # Corrupt checksum
    valid, data = unpack_and_validate(bytes(pkt))
    assert valid is False
    assert data is None

def test_packet_contract_invalid_angle():
    pkt = bytearray(create_packet(fire=1, angle=200, packet_id=1, risk_score=80, flame_raw=200))
    valid, data = unpack_and_validate(bytes(pkt))
    assert valid is False

def test_failsafe_watchdog_timeout():
    last_packet_ms = 10000
    
    # 2 seconds later -> not timed out (< 3000ms)
    assert not ((12000 - last_packet_ms) > PACKET_TIMEOUT_MS)
    
    # 3.5 seconds later -> timed out! Relay must shut down
    assert ((13500 - last_packet_ms) > PACKET_TIMEOUT_MS)

def test_servo_mapping_and_limits():
    min_angle = 5
    max_angle = 175
    offset = 5
    reverse = False
    
    def map_angle(detected):
        mapped = detected
        if reverse:
            mapped = 180 - mapped
        mapped += offset
        return max(min_angle, min(max_angle, mapped))
        
    assert map_angle(90) == 95
    assert map_angle(0) == 5
    assert map_angle(180) == 175
