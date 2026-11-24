from typing import Any
from serial import SerialException
from serial.tools.list_ports import comports

DEFAULT_VID_PID = (0x0403, 0x6015)


def list_meerstetter_devices(vid_pid: tuple[int, int] = DEFAULT_VID_PID) -> list[dict[str, Any]]:
    """Scan all system serial ports and return metadata for any connected Meerstetter devices."""
    devices = []
    target_vid, target_pid = vid_pid
    for port in comports():
        if port.vid == target_vid and port.pid == target_pid:
            devices.append({
                "port": port.device,
                "vid": port.vid,
                "pid": port.pid,
                "serial_number": getattr(port, "serial_number", None),
                "description": getattr(port, "description", None),
            })
    return devices


def find_meerstetter_port(vid_pid: tuple[int, int] = DEFAULT_VID_PID) -> str:
    """Find and return the COM port name of the connected Meerstetter TEC controller.

    Raises SerialException if no matching hardware is detected.
    """
    devices = list_meerstetter_devices(vid_pid)
    if not devices:
        raise SerialException(
            f"No connected Meerstetter TEC controller found matching VID:PID {vid_pid[0]:04X}:{vid_pid[1]:04X}"
        )
    return str(devices[0]["port"])
