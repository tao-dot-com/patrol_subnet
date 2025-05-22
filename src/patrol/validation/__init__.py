from typing import NamedTuple

from bt_decode.bt_decode import AxonInfo

class Miner(NamedTuple):
    axon_info: AxonInfo
    uid: int

class ValidationException(Exception):
    pass
