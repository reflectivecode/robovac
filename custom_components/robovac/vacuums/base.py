from enum import IntEnum, StrEnum
from typing import Protocol, Dict, Any


class RoboVacEntityFeature(IntEnum):
    """Supported features of the RoboVac entity."""

    CLEANING_TIME = 4
    CLEANING_AREA = 8
    DO_NOT_DISTURB = 16
    AUTO_RETURN = 32


class RobovacCommand(StrEnum):
    START_PAUSE = "start_pause"
    DIRECTION = "direction"
    MODE = "mode"
    STATUS = "status"
    RETURN_HOME = "return_home"
    FAN_SPEED = "fan_speed"
    LOCATE = "locate"
    BATTERY = "battery"
    ERROR = "error"
    CLEANING_AREA = "cleaning_area"
    CLEANING_TIME = "cleaning_time"
    AUTO_RETURN = "auto_return"
    DO_NOT_DISTURB = "do_not_disturb"


class TuyaCodes(StrEnum):
    """Default DPS codes for Tuya-based vacuums.

    These codes can be overridden in model-specific implementations.
    """
    START_PAUSE = "2"
    DIRECTION = "3"
    MODE = "5"
    STATUS = "15"
    RETURN_HOME = "101"
    FAN_SPEED = "102"
    LOCATE = "103"
    BATTERY_LEVEL = "104"
    ERROR_CODE = "106"
    DO_NOT_DISTURB = "107"
    CLEANING_TIME = "109"
    CLEANING_AREA = "110"
    AUTO_RETURN = "135"


class RobovacModelDetails(Protocol):
    homeassistant_features: int
    robovac_features: int
    commands: Dict[RobovacCommand, Any]
