"""
Sensor + GPS reading layer.

By default this SIMULATES sensors so you can run and test the whole
pipeline on a laptop with no hardware attached. Flip USE_REAL_HARDWARE
in config/settings.py once you have a Raspberry Pi wired up, and fill in
the marked sections below with your actual device code.
"""

import random

from config.settings import USE_REAL_HARDWARE


def get_gps_location() -> dict:
    """Returns {"lat": float, "lon": float}."""
    if USE_REAL_HARDWARE:
        # --- Real hardware version (NEO-6M GPS module over UART) ---
        # import serial, pynmea2
        # gps = serial.Serial('/dev/ttyS0', baudrate=9600, timeout=1)
        # while True:
        #     line = gps.readline().decode('ascii', errors='replace')
        #     if line.startswith('$GPGGA'):
        #         msg = pynmea2.parse(line)
        #         return {"lat": msg.latitude, "lon": msg.longitude}
        raise NotImplementedError("Fill in real GPS code above, then remove this line.")

    # --- Simulated location (fixed test point, e.g. Pune) ---
    return {"lat": 18.5204 + random.uniform(-0.001, 0.001),
            "lon": 73.8567 + random.uniform(-0.001, 0.001)}


def read_sensors() -> dict:
    """
    Returns raw physical readings:
    - water_level_cm: distance from an ultrasonic sensor down to water
                       surface. LOWER number = HIGHER water = more danger.
    - rain_rate_mm_hr: from a tipping-bucket rain gauge.
    - pressure_hpa: from a barometric sensor (e.g. BME280).
    - vibration_g: peak acceleration from an accelerometer (e.g. MPU6050),
                    used for the earthquake STA/LTA check.
    """
    if USE_REAL_HARDWARE:
        # --- Real hardware version ---
        # water_level_cm = read_hcsr04()
        # rain_rate_mm_hr = read_rain_gauge()
        # pressure_hpa = read_bme280().pressure
        # vibration_g = read_mpu6050_peak()
        raise NotImplementedError("Fill in real sensor code above, then remove this line.")

    # simultor
    danger_roll = random.random()

    if danger_roll < 0.15:
        water_level_cm = random.uniform(20, 60)
        rain_rate_mm_hr = random.uniform(35, 70)
        pressure_hpa = random.uniform(995, 1002)
    else:
        water_level_cm = random.uniform(90, 150)
        rain_rate_mm_hr = random.uniform(0, 15)
        pressure_hpa = random.uniform(1008, 1015)

    if danger_roll > 0.9:
        vibration_g = random.uniform(0.4, 1.2)
    else:
        vibration_g = random.uniform(0.0, 0.03)

    if danger_roll < 0.05:
        wind_speed_kmh = random.uniform(75, 115)
    else:
        wind_speed_kmh = random.uniform(3, 28)

    # This represents a coastal tide gauge, not the ordinary water-level
    # sensor above. Real deployments should only enable it at coastal sites.
    sea_level_change_cm = random.uniform(-3, 3)
    if danger_roll > 0.985:
        sea_level_change_cm = random.uniform(55, 120)

    return {
        "water_level_cm": round(water_level_cm, 1),
        "rain_rate_mm_hr": round(rain_rate_mm_hr, 1),
        "pressure_hpa": round(pressure_hpa, 1),
        "vibration_g": round(vibration_g, 3),
        "wind_speed_kmh": round(wind_speed_kmh, 1),
        "sea_level_change_cm": round(sea_level_change_cm, 1),
    }
