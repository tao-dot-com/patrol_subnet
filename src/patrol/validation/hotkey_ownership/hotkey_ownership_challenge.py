from bt_decode.bt_decode import AxonInfo

from patrol.protocol import HotkeyOwnershipSynapse
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient
from patrol.validation.scoring import MinerScoreRepository

import networkx as nx

class HotkeyOwnershipChallenge:

    def __init__(self, miner_client: HotkeyOwnershipMinerClient, miner_score_repository: MinerScoreRepository):
        self.miner_client = miner_client
        self.miner_score_repository = miner_score_repository
        self.hotkey_ownership_scoring = None

    async def execute_challenge(self, miner: AxonInfo, target_hotkey):
        synapse = HotkeyOwnershipSynapse(hotkey_ss58=target_hotkey)
        response = await self.miner_client.execute_task(miner, synapse)
        self._validate(response)


    def _validate(self, synapse: HotkeyOwnershipSynapse):
        subgraph = synapse.subgraph_output
        graph = nx.Graph()
        for node in subgraph.nodes:
            if node.id in graph:
                raise ValueError(f"Duplicate node: {node.id}")
            graph.add_node(node.id)

        for edge in subgraph.edges:
            if (edge.coldkey_source not in graph.nodes) or (edge.coldkey_destination not in graph.nodes):
                raise ValueError("Edge refers to an absent node.")
            graph.add_edge(edge.coldkey_source, edge.coldkey_destination)

        if not nx.is_connected(graph):
            raise ValueError("Graph is not fully connected.")

