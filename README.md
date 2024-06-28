### Setup

```bash
# install git and python3-dev
sudo apt-get install python3-dev git
# clone repo
git clone https://github.com/zackoch/dual-adxl345.git
# create virtual environment
python3 -m venv venv
# activate venv
source ./venv/bin/activate
# install requirements
pip install -r requirements.txt
# run
python main.py
```

### Connections to Raspberry Pi 5

#### ADXL345_0

| Pin  | Raspberry Pi Pin |
|------|------------------|
| GND  | GND              |
| VCC  | 3.3V             |
| CS   | GPIO8            |
| SD0  | GPIO9            |
| SDA  | GPIO10           |
| SCL  | GPIO11           |

#### ADXL345_1

| Pin  | Raspberry Pi Pin |
|------|------------------|
| GND  | GND              |
| VCC  | 3.3V             |
| CS   | GPIO18           |
| SD0  | GPIO19           |
| SDA  | GPIO20           |
| SCL  | GPIO21           |

#### Button

| Pin    | Raspberry Pi Pin |
|--------|------------------|
| Pole A | GND              |
| Pole B | GPIO26           |

### Setting the Data Rate

The available data rates for the ADXL345's are defined in a dictionary as follows:

```python
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
```
To set the data rate, you need to modify the data_rate variable. The data_rate variable should be set to one of the values from the avail_data_rates dictionary. For example, to set the data rate to 3200 Hz, you would set the data_rate variable as follows:

```python
data_rate = avail_data_rates['3200hz']
```
To change the data rate, simply replace '3200hz' with the desired rate from the dictionary. For instance, if you want to set the data rate to 100 Hz, you would use:
```python
data_rate = avail_data_rates['100hz']
```
Make sure to choose the appropriate data rate for your specific application needs.

### Output Data
Data is stored in three folders:
#### ./data
- contains the database - each run creates a new timestamped database
- db columns include:
    - timestamp (unix)
    - sensor "id" (0,1)
    - x-value
    - y-value
    - z-value
- database is not overwritten
- database contains entire run data
#### ./plot
- graph with last **180 seconds** of data from `button press` or `ctrl+c`
#### ./plot_overlay
- graph with both sensors on the same graph of last **180 seconds** of data from `button press` or `ctrl+c`

