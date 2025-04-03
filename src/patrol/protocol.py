import typing
import bittensor as bt

class PatrolSynapse(bt.Synapse):
    """
    A simple event graph protocol that inherits from bt.Synapse.
    This protocol handles event graph request and response communication between
    the miner and the validator.
    """

    target: typing.Optional[str] = None
    target_block_number: typing.Optional[int] = None


    subgraph_output: typing.Optional[dict] = None

    
class MinerPingSynapse(bt.Synapse):
    """
    A simple ping synapse that inherits from bt.Synapse.
    This synapse handles ping request and response communication between
    the miner and the validator.
    """
    is_available: typing.Optional[bool] = False



