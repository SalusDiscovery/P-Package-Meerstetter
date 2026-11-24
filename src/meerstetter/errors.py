from dataclasses import dataclass
from typing import Any

MEERSTETTER_ERRORS: dict[int, str] = {
    0: "No Error",
    1: "Unknown Error",
    2: "Communication Error",
    100: "Lower Sensor (E1) Fault / Open / Short",
    101: "Upper Sensor (E2) Fault / Open / Short",
    102: "Heat Sink Sensor Fault",
    103: "Sensor Fault / Open Circuit",
    104: "Sensor Fault / Short Circuit",
    105: "Thermal Runaway / Overtemperature",
    106: "Object Temperature Limit Exceeded",
    107: "Heat Sink Temperature Limit Exceeded",
    108: "Supply Voltage / PID Limit (24V DC Power Missing)",
}

DEVICE_STATUS_NAMES: dict[int, str] = {
    0: "Init",
    1: "Ready",
    2: "Run",
    3: "Error",
}


@dataclass
class DeviceStatus:
    status: int
    status_name: str
    error_number: int
    error_instance: int
    error_name: str
    is_error: bool
    is_undervoltage: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "status_name": self.status_name,
            "error_number": self.error_number,
            "error_instance": self.error_instance,
            "error_name": self.error_name,
            "is_error": self.is_error,
            "is_undervoltage": self.is_undervoltage,
        }
