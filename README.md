# P-Package-Meerstetter (`meerstetter`)

Python driver and convenience interface for Meerstetter Engineering dual-channel TEC controllers (e.g. TEC-1091 / TEC-1089) built over official [`meerstetter/pyMeCom`](https://github.com/meerstetter/pyMeCom).

## Features

- **Ergonomic Convenience APIs**: Direct, intuitive methods (`get_temperature`, `set_temperature`, `enable`, `disable`, `get_status`, `reset`).
- **Timing & Hardware Protection**: Enforces the required 30ms inter-command guard time with thread-safe locking across all operations to prevent micro-UART buffer collisions.
- **Port Probing**: Automatically detects connected Meerstetter controllers via FTDI VID:PID `0x0403:0x6015`.
- **Dual-Channel Support**: Channel 1 (Lower Block) and Channel 2 (Upper Block) addressing.
- **24V Undervoltage (Error 108) Detection**: Native decoding of Parameter 104 (Device Status) and Parameter 105 (Error Code) for 24V power loss detection.
- **Hardware Reset Recovery**: Parameter 50000 software reboot to clear latched error states after power restoration.
- **Full Passthrough**: Direct access to `get_parameter()`, `set_parameter()`, and the underlying `MeComSerial` session for unrestricted raw protocol control.

## Installation

```bash
pip install git+https://github.com/Salus-Discovery/P-Package-Meerstetter.git@main
```

## Basic Usage

```python
from meerstetter import MeerstetterTEC

# Auto-discovers COM port (VID:PID 0x0403:0x6015) and connects at 57600 baud
tec = MeerstetterTEC()

# Read temperatures
temp1 = tec.get_temperature(channel=1)
temp2 = tec.get_temperature(channel=2)
print(f"Lower Block: {temp1:.1f}°C, Upper Block: {temp2:.1f}°C")

# Set target temperatures and enable output stages
tec.set_temperature(temp_c=60.0, channel=1)
tec.enable(channel=1)

tec.set_temperature(temp_c=50.0, channel=2)
tec.enable(channel=2)

# Check device diagnostic status (checks for Error 108 24V power loss)
status = tec.get_status(channel=1)
if status.is_undervoltage:
    print("Warning: 24V DC instrument power switch is OFF!")

# Software reset after power restored to clear latch
if status.is_error:
    tec.reset()
```
