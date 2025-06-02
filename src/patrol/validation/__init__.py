from typing import NamedTuple

from bittensor import AxonInfo


class Miner(NamedTuple):
    axon_info: AxonInfo
    uid: int

class ValidationException(Exception):
    pass
