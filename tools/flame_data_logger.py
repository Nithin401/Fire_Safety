import serial
import serial.tools.list_ports
import csv
import time
import datetime
import os
import argparse
import sys

def find_arduino_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if 'CH340' in p.description or 'Arduino' in p.description or 'USB-SERIAL' in p.description:
            return p.device
    if len(ports) > 0:
        return ports[0].device
    return None

def main():
    parser = argparse.ArgumentParser(description="Flame Sensor Data Logger")
    parser.add_argument('--port', type=str, help='COM port (e.g., COM3, /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--session', type=str, required=True, help='Session ID (e.g., NORMAL_001, FLAME_TEST_001)')
    parser.add_argument('--condition', type=str, default='NORMAL', choices=['NORMAL', 'FLAME', 'RECOVERY', 'NOISE', 'UNKNOWN'], help='Condition label')
    parser.add_argument('--distance', type=str, default='', help='Distance metadata')
    parser.add_argument('--orientation', type=str, default='', help='Orientation metadata')
    parser.add_argument('--notes', type=str, default='', help='Experimental notes')
    args = parser.parse_args()

    port = args.port if args.port else find_arduino_port()
    if not port:
        print("Error: Could not automatically find a connected serial device.")
        print("Please specify the port manually using --port")
        sys.exit(1)

    print(f"Connecting to {port} at {args.baud} baud...")

    # Determine directory based on session name
    base_dir = "data/real/normal"
    if "FLAME" in args.session.upper():
        base_dir = "data/real/flame_tests"
    elif "RECOVERY" in args.session.upper():
        base_dir = "data/real/recovery"
        
    os.makedirs(base_dir, exist_ok=True)
    
    filename = os.path.join(base_dir, f"{args.session}_{int(time.time())}.csv")

    fields = [
        "pc_timestamp", "esp_timestamp_ms", "device_id", "room_id", 
        "flame_raw", "session_id", "condition", "distance", 
        "orientation", "notes"
    ]

    try:
        ser = serial.Serial(port, args.baud, timeout=2)
        time.sleep(2)  # Wait for ESP to reset
        
        with open(filename, mode='w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fields)
            writer.writeheader()
            
            print(f"Logging data to {filename}")
            print("Press Ctrl+C to stop logging safely.")
            
            rows_written = 0
            
            while True:
                try:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8').strip()
                        
                        # Skip header lines from ESP
                        if line.startswith("timestamp_ms") or not line:
                            continue
                            
                        parts = line.split(',')
                        if len(parts) == 4:
                            esp_ts, dev_id, room_id, flame_raw = parts
                            
                            # Validate
                            if not esp_ts.isdigit() or not flame_raw.isdigit():
                                continue
                                
                            row = {
                                "pc_timestamp": datetime.datetime.now().isoformat(),
                                "esp_timestamp_ms": esp_ts,
                                "device_id": dev_id,
                                "room_id": room_id,
                                "flame_raw": flame_raw,
                                "session_id": args.session,
                                "condition": args.condition,
                                "distance": args.distance,
                                "orientation": args.orientation,
                                "notes": args.notes
                            }
                            
                            writer.writerow(row)
                            csvfile.flush() # Flush to disk continuously
                            
                            rows_written += 1
                            sys.stdout.write(f"\rCollected {rows_written} samples. Current flame_raw: {flame_raw}    ")
                            sys.stdout.flush()
                            
                except serial.SerialException as e:
                    print(f"\nSerial connection error: {e}")
                    break
                except UnicodeDecodeError:
                    # Ignore invalid bytes
                    continue

    except KeyboardInterrupt:
        print(f"\n\nLogging stopped by user. Safely closed file.")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        print(f"Session finished. Total rows saved: {rows_written} to {filename}")

if __name__ == "__main__":
    main()
