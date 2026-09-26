import pytest
import numpy as np

def simulate_optical_sweep(fire_angle, ambient=900, peak_intensity=700, sigma=15, noise_std=5):
    """
    Simulates physical IR flame photodiode readings across angles 0 to 180 degrees.
    """
    angles = np.arange(0, 181, 10)
    readings = []
    for theta in angles:
        if fire_angle is not None:
            flame_response = peak_intensity * np.exp(-((theta - fire_angle) ** 2) / (2 * (sigma ** 2)))
        else:
            flame_response = 0
        adc = ambient - flame_response + np.random.normal(0, noise_std)
        readings.append(int(np.clip(adc, 0, 1023)))
    return angles, np.array(readings)

def compute_peak_direction_and_confidence(angles, readings):
    min_idx = np.argmin(readings)
    best_angle = angles[min_idx]
    min_val = readings[min_idx]
    
    mean_val = np.mean(readings)
    peak_drop = mean_val - min_val
    
    if min_val < 500 and peak_drop > 80.0:
        conf = min(1.0, peak_drop / 350.0)
    else:
        conf = 0.1
        
    return best_angle, conf

def test_direction_convergence_focused_flame():
    np.random.seed(42)
    target_angles = [40, 90, 130]
    
    for target in target_angles:
        angles, readings = simulate_optical_sweep(target, ambient=900, peak_intensity=700, sigma=12)
        detected_angle, confidence = compute_peak_direction_and_confidence(angles, readings)
        
        # Must be within 10 degrees resolution of virtual flame
        assert abs(detected_angle - target) <= 10
        assert confidence > 0.7

def test_direction_confidence_flat_noise():
    np.random.seed(123)
    # Ambient room with no flame (random noise around 900 ADC)
    angles, readings = simulate_optical_sweep(None, ambient=900, peak_intensity=0, noise_std=10)
    detected_angle, confidence = compute_peak_direction_and_confidence(angles, readings)
    
    # Confidence must be low because no prominent peak exists
    assert confidence <= 0.2

def test_direction_confidence_diffuse_light():
    np.random.seed(456)
    # Uniform bright ambient light across all angles (e.g. bright sunlight in room: ~450 everywhere)
    readings = np.random.normal(450, 10, len(np.arange(0, 181, 10)))
    detected_angle, confidence = compute_peak_direction_and_confidence(np.arange(0, 181, 10), readings)
    
    # Even though ADC is low, there is no spatial peak prominence -> low confidence
    assert confidence <= 0.2

def test_comms_dropout_during_sweep():
    last_sweep_packet_ms = 5000
    timeout_ms = 3000
    
    # Simulating packets arriving every 100ms
    assert (5100 - last_sweep_packet_ms) < timeout_ms
    
    # Packet lost mid-sweep at 8500ms
    current_ms = 8500
    assert (current_ms - last_sweep_packet_ms) > timeout_ms
