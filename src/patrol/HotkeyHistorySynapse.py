from dataclasses import field
from typing import Optional

import bittensor as bt

from patrol.protocol import GraphPayload


class HotkeyOwnershipSynapse(bt.Synapse):
    hotkey_ss58: Optional[str] = field(default=None)

    subgraph_output: Optional[GraphPayload] = field(default=None)
