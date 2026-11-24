import threading
import time
from typing import Any

from mecom import MeComSerial
from serial import SerialException

from .discovery import find_meerstetter_port
from .errors import DEVICE_STATUS_NAMES, MEERSTETTER_ERRORS, DeviceStatus

_MIN_INTER_CMD_SEC = 0.030


class MeerstetterTEC:
    """Convenience, protection, and timing guard wrapper over official Meerstetter pyMeCom.

    Features:
    - Thread-safe serial operations guarded by a reentrant lock.
    - Automatic enforcement of the 30ms inter-command guard time required by Meerstetter micro-UARTs.
    - Ergonomic high-level methods: get_temperature, set_temperature, enable, disable, get_status, reset.
    - Dual-channel support (Channel 1 = Lower Block, Channel 2 = Upper Block).
    - Drop-in backward compatibility with `.instance = 1/2` property assignment.
    - Direct, unrestricted low-level passthrough via get_parameter() and set_parameter().
    """

    def __init__(
        self,
        port: str | None = None,
        baudrate: int = 57600,
        timeout: float = 1.0,
        auto_connect: bool = True,
        channel: int = 1,
        address: int = 0,
    ):
        self.baudrate = baudrate
        self.timeout = timeout
        self.channel = channel
        self.address = address
        self.port: str | None = port
        self.session: MeComSerial | None = None

        self._lock = threading.RLock()
        self._last_cmd_timestamp = 0.0

        if auto_connect:
            self.connect(port)

    # ------------------------------------------------------------------
    # Backward Compatibility Properties
    # ------------------------------------------------------------------
    @property
    def instance(self) -> int:
        """Alias for channel number (backward compatibility with legacy rorlib)."""
        return self.channel

    @instance.setter
    def instance(self, val: int) -> None:
        self.channel = int(val)

    @property
    def raw_session(self) -> MeComSerial | None:
        """Direct access to the underlying official pyMeCom MeComSerial instance."""
        return self.session

    # ------------------------------------------------------------------
    # Timing Guard
    # ------------------------------------------------------------------
    def _respect_guard_time(self) -> None:
        """Enforce a minimum 30ms guard time between consecutive MeCom serial transactions."""
        now = time.monotonic()
        elapsed = now - self._last_cmd_timestamp
        if elapsed < _MIN_INTER_CMD_SEC:
            time.sleep(_MIN_INTER_CMD_SEC - elapsed)
        self._last_cmd_timestamp = time.monotonic()

    # ------------------------------------------------------------------
    # Connection Lifecycle
    # ------------------------------------------------------------------
    def connect(self, port: str | None = None) -> str:
        """Discover (if not provided) and connect the Meerstetter controller serial port."""
        with self._lock:
            if port is None:
                port = find_meerstetter_port()

            self._close_existing_session()

            self.session = MeComSerial(serialport=port, baudrate=self.baudrate, timeout=self.timeout)
            self.port = port
            self._last_cmd_timestamp = time.monotonic()

            # Ensure default Independent / Single operating mode (Parameter 2040 = 0)
            try:
                self._respect_guard_time()
                self.session.set_parameter(value=0, parameter_id=2040, address=self.address, parameter_instance=1)
            except Exception:
                pass

            return port

    def reconnect(self) -> str:
        """Safely reconnect to the current or newly scanned Meerstetter COM port."""
        with self._lock:
            return self.connect(self.port)

    def close(self) -> None:
        """Safely close active MeCom communication session."""
        with self._lock:
            self._close_existing_session()

    def _close_existing_session(self) -> None:
        if self.session is not None:
            try:
                ser = getattr(self.session, "ser", None) or getattr(self.session, "_ser", None)
                if ser is not None and hasattr(ser, "close"):
                    ser.close()
            except Exception:
                pass
            self.session = None

    # ------------------------------------------------------------------
    # High-Level Convenience Methods
    # ------------------------------------------------------------------
    def get_temperature(self, channel: int | None = None) -> float:
        """Read measured object temperature in °C (MeCom Parameter 1000)."""
        ch = self.channel if channel is None else channel
        val = self.get_parameter(parameter_id=1000, channel=ch)
        return float(val)

    def set_temperature(self, temp_c: float, channel: int | None = None) -> None:
        """Set target object temperature in °C (MeCom Parameter 3000)."""
        ch = self.channel if channel is None else channel
        self.set_parameter(value=float(temp_c), parameter_id=3000, channel=ch)

    def enable(self, channel: int | None = None) -> None:
        """Enable output stage for specified channel (MeCom Parameter 2010 = 1)."""
        ch = self.channel if channel is None else channel
        self.set_parameter(value=1, parameter_id=2010, channel=ch)

    def disable(self, channel: int | None = None) -> None:
        """Disable output stage for specified channel (MeCom Parameter 2010 = 0)."""
        ch = self.channel if channel is None else channel
        self.set_parameter(value=0, parameter_id=2010, channel=ch)

    def set_general_operating_mode(self, mode: int = 0) -> None:
        """Set General Operating Mode (MeCom Parameter 2040: 0 = Single / Independent)."""
        self.set_parameter(value=int(mode), parameter_id=2040, channel=1)

    def get_status(self, channel: int | None = None) -> DeviceStatus:
        """Query MeCom Parameter 104 (Device Status) and Error Code / Instance.

        Returns DeviceStatus dataclass detailing state (Init/Ready/Run/Error) and
        whether an Error 108 (Supply Undervoltage due to 24V switch OFF) is latched.
        """
        ch = self.channel if channel is None else channel
        try:
            status_val = self.get_parameter(parameter_id=104, channel=ch)
            status_int = int(status_val)
        except Exception:
            return DeviceStatus(
                status=0,
                status_name="Normal / Unqueried",
                error_number=0,
                error_instance=ch,
                error_name="No Error",
                is_error=False,
                is_undervoltage=False,
            )

        status_name = DEVICE_STATUS_NAMES.get(status_int, f"Unknown ({status_int})")
        err_num = 0
        err_inst = ch

        if status_int == 3:  # Error state latched in firmware
            try:
                err_val = self.get_parameter(parameter_id=105, channel=ch)
                if err_val is not None:
                    err_num = int(err_val)
            except Exception:
                pass
            try:
                inst_val = self.get_parameter(parameter_id=106, channel=ch)
                if inst_val is not None:
                    err_inst = int(inst_val)
            except Exception:
                pass

        err_name = MEERSTETTER_ERRORS.get(err_num, f"Error Code {err_num}")
        is_undervoltage = (status_int == 3 and err_num == 108)

        return DeviceStatus(
            status=status_int,
            status_name=status_name,
            error_number=err_num,
            error_instance=err_inst,
            error_name=err_name,
            is_error=(status_int == 3),
            is_undervoltage=is_undervoltage,
        )

    def reset(self) -> bool:
        """Issue native System Reset (Parameter 50000 = 1) to reboot the controller.

        Clears latched Error 108 once 24V DC power is restored and reloads
        calibrations stored in Flash.
        """
        with self._lock:
            try:
                self._respect_guard_time()
                if self.session is not None:
                    self.session.set_parameter(value=1, parameter_id=50000, address=self.address, parameter_instance=1)
            except Exception:
                pass
            time.sleep(0.50)  # Settle time for controller reboot
            try:
                self.reconnect()
                return True
            except Exception:
                return False

    # ------------------------------------------------------------------
    # Low-Level Passthrough
    # ------------------------------------------------------------------
    def get_parameter(
        self,
        parameter_id: int | str,
        channel: int = 1,
        address: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Thread-safe, timing-guarded read of any MeCom parameter register."""
        addr = self.address if address is None else address
        with self._lock:
            if self.session is None:
                raise SerialException("MeerstetterTEC is not connected")
            self._respect_guard_time()
            try:
                if isinstance(parameter_id, int):
                    return self.session.get_parameter(
                        parameter_id=parameter_id,
                        address=addr,
                        parameter_instance=channel,
                        *args,
                        **kwargs,
                    )
                else:
                    return self.session.get_parameter(
                        parameter_name=parameter_id,
                        address=addr,
                        parameter_instance=channel,
                        *args,
                        **kwargs,
                    )
            finally:
                self._last_cmd_timestamp = time.monotonic()

    def set_parameter(
        self,
        value: Any,
        parameter_id: int | str,
        channel: int = 1,
        address: int | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Thread-safe, timing-guarded write to any MeCom parameter register."""
        addr = self.address if address is None else address
        with self._lock:
            if self.session is None:
                raise SerialException("MeerstetterTEC is not connected")
            self._respect_guard_time()
            try:
                if isinstance(parameter_id, int):
                    return bool(
                        self.session.set_parameter(
                            value=value,
                            parameter_id=parameter_id,
                            address=addr,
                            parameter_instance=channel,
                            *args,
                            **kwargs,
                        )
                    )
                else:
                    return bool(
                        self.session.set_parameter(
                            value=value,
                            parameter_name=parameter_id,
                            address=addr,
                            parameter_instance=channel,
                            *args,
                            **kwargs,
                        )
                    )
            finally:
                self._last_cmd_timestamp = time.monotonic()
