from typing import Dict, Type

from .T2259 import T2259
from .base import RobovacModelDetails

ROBOVAC_MODELS: Dict[str, Type[RobovacModelDetails]] = {
    "T2259": T2259,
}
