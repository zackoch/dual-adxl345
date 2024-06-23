import spidev
import time
import struct
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import signal
import RPi.GPIO as GPIO
import atexit
from datetime import datetime

BUTTON_PIN = 26
REG_DEVID = 0x00
REG_POWER_CTL = 0x2D
REG_DATAX0 = 0x32
REG_DATA_RATE = 0x2C

db_name = f"./data/ride_{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.db"

spi0 = spidev.SpiDev()
spi0.open(0, 0)
spi0.max_speed_hz = 5000000
spi0.mode = 0b11

spi1 = spidev.SpiDev()
spi1.open(1, 0)
spi1.max_speed_hz = 5000000
spi1.mode = 0b11

def write_register(spi, register, value):
    spi.xfer2([register, value])

def read_register(spi, register):
    response = spi.xfer2([register | 0x80, 0x00])
    return response[1]

def read_bytes(spi, register, length):
    response = spi.xfer2([register | 0xC0] + [0x00] * length)
    return bytes(response[1:])

def init_adxl345(spi, data_rate):
    devid = read_register(spi, REG_DEVID)
    if devid != 0xE5:
        raise Exception(f"ADXL345 not connected, got DEVID: {devid:#04x}")
    write_register(spi, REG_POWER_CTL, 0x08)
    write_register(spi, REG_DATA_RATE, data_rate)

def convert_to_g(raw_value):
    return raw_value * 0.004

should_stop = False

def collect_data(precision=3, data_rate=9):
    global should_stop
    init_adxl345(spi0, data_rate)
    init_adxl345(spi1, data_rate)

    print("timestamp,sensor,x_g,y_g,z_g")
    while not should_stop:
        timestamp = time.time()
        x_g0, y_g0, z_g0 = read_accelerometer(spi0, 0)
        x_g1, y_g1, z_g1 = read_accelerometer(spi1, 1)

        with sqlite3.connect(f'{db_name}') as conn:
            cursor = conn.cursor()
            cursor.execute('CREATE TABLE IF NOT EXISTS acceleration (timestamp REAL, sensor_id INTEGER, x_g REAL, y_g REAL, z_g REAL)')
            cursor.execute('INSERT INTO acceleration (timestamp, sensor_id, x_g, y_g, z_g) VALUES (?, ?, ?, ?, ?)', (timestamp, 0, x_g0, y_g0, z_g0))
            cursor.execute('INSERT INTO acceleration (timestamp, sensor_id, x_g, y_g, z_g) VALUES (?, ?, ?, ?, ?)', (timestamp, 1, x_g1, y_g1, z_g1))
            conn.commit()
        
        format_str = f"{timestamp},sensor0,{x_g0:.{precision}f},{y_g0:.{precision}f},{z_g0:.{precision}f}"
        print(format_str)
        format_str = f"{timestamp},sensor1,{x_g1:.{precision}f},{y_g1:.{precision}f},{z_g1:.{precision}f}"
        print(format_str)

def read_accelerometer(spi, sensor_id):
    bytes_data = read_bytes(spi, REG_DATAX0, 6)
    if len(bytes_data) != 6:
        raise Exception(f"Error reading accelerometer data, got {len(bytes_data)} bytes: {bytes_data}")
    x = struct.unpack('<h', bytes_data[0:2])[0]
    y = struct.unpack('<h', bytes_data[2:4])[0]
    z = struct.unpack('<h', bytes_data[4:6])[0]
    x_g = convert_to_g(x)
    y_g = convert_to_g(y)
    z_g = convert_to_g(z)
    return x_g, y_g, z_g

def save_plot():
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        time_threshold = time.time() - PLOT_DURATION 
        cursor.execute('SELECT * FROM acceleration WHERE timestamp >= ?', (time_threshold,))
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['timestamp', 'sensor_id', 'x_g', 'y_g', 'z_g'])

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        y_lim_adjustments = {
            0xF: 2.5,  # 3200 Hz: ±2.5g
            0xE: 2.0,  # 1600 Hz: ±2g
            0xD: 1.5,  # 800 Hz: ±1.5g
            0xC: 1.0,  # 400 Hz: ±1g
            0xB: 0.75, # 200 Hz: ±0.75g
            0xA: 0.5,  # 100 Hz: ±0.5g
            0x9: 0.4,  #  50 Hz: ±0.4g
            0x8: 0.3,  #  25 Hz: ±0.3g
            0x7: 0.2,  # 12.5 Hz: ±0.2g
            0x6: 0.1,   #  6.25 Hz: ±0.1g
            0x5: 0.1,   #  3.13 Hz: ±0.1g
            0x4: 0.1,   #  1.56 Hz: ±0.1g
            0x3: 0.1,   #  0.78 Hz: ±0.1g
            0x2: 0.1,   #  0.39 Hz: ±0.1g
            0x1: 0.1,   #  0.20 Hz: ±0.1g
            0x0: 0.1   #  0.10 Hz: ±0.1g
        }
        
        y_lim = y_lim_adjustments.get(data_rate, 2.0)  # default to ±2g

        fig, axes = plt.subplots(nrows=2, figsize=(10, 8))
        for sensor_id, group in df.groupby('sensor_id'):
            axes[sensor_id].plot(group['timestamp'], group['x_g'], label='x')
            axes[sensor_id].plot(group['timestamp'], group['y_g'], label='y')
            axes[sensor_id].plot(group['timestamp'], group['z_g'], label='z')
            axes[sensor_id].set_title(f"Sensor {sensor_id} Acceleration (Last {PLOT_DURATION}s)")
            axes[sensor_id].legend()
            axes[sensor_id].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            axes[sensor_id].xaxis.set_major_locator(mdates.AutoDateLocator())
            fig.autofmt_xdate() 
            axes[sensor_id].set_ylim([-y_lim, y_lim])  

        plt.xlabel("Time")
        plt.ylabel("Acceleration (g)")
        plt.savefig(f"./plot/acceleration_plot_subplots_last_{PLOT_DURATION}s-{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.png")

        # overlaid
        plt.figure(figsize=(10, 8))
        for sensor_id, group in df.groupby('sensor_id'):
            plt.plot(group['timestamp'], group['x_g'], label=f'Sensor {sensor_id} - x')
            plt.plot(group['timestamp'], group['y_g'], label=f'Sensor {sensor_id} - y')
            plt.plot(group['timestamp'], group['z_g'], label=f'Sensor {sensor_id} - z')

        plt.xlabel("Time")
        plt.ylabel("Acceleration (g)")
        plt.title(f"Acceleration Data (Last {PLOT_DURATION}s) - Overlaid")
        plt.legend()
        plt.xticks(rotation=45) 
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.tight_layout()
        plt.savefig(f"./plot_overlay/acceleration_plot_overlay_last_{PLOT_DURATION}s-{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.png")
        plt.pause(0.5)

def cleanup():
    spi0.close()
    spi1.close()
    GPIO.cleanup()
    exit(0) 

def button_callback(channel):
    print("Button pressed!")
    save_plot()
    cleanup()

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    save_plot()
    cleanup()
    
if __name__ == "__main__":
    PLOT_DURATION = 180  

    signal.signal(signal.SIGINT, signal_handler)
    atexit.register(cleanup)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

    avail_data_rates = {
        "3200hz": 0xF,
        "1600hz": 0xE,
        "800hz": 0xD,
        "400hz": 0xC,
        "200hz": 0xB,
        "100hz": 0xA,
        "50hz": 0x9,
        "25hz": 0x8,
        "12.5hz": 0x7,
        "6.25hz": 0x6,
        "3.13hz": 0x5,
        "1.56hz": 0x4,
        "0.78hz": 0x3,
        "0.39hz": 0x2,
        "0.20hz": 0x1,
        "0.10hz": 0x0,
    }
    data_rate=avail_data_rates['3200hz']
    collect_data(data_rate=data_rate)

