import asyncio
import itertools

from bt_decode.bt_decode import AxonInfo

from patrol.protocol import HotkeyOwnershipSynapse, Edge
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient

import networkx as nx

class HotkeyOwnershipChallenge:

    def __init__(
            self, miner_client: HotkeyOwnershipMinerClient,
            chain_reader: ChainReader
    ):
        self.miner_client = miner_client
        self.hotkey_ownership_scoring = None
        self.chain_reader = chain_reader

    async def execute_challenge(self, miner: AxonInfo, target_hotkey):
        synapse = HotkeyOwnershipSynapse(hotkey_ss58=target_hotkey)
        response = await self.miner_client.execute_task(miner, synapse)
        self._validate_graph(response)

        await self._validate_edges(target_hotkey, response.subgraph_output.edges)


    def _validate_graph(self, synapse: HotkeyOwnershipSynapse):
        HotkeyOwnershipSynapse.model_validate(synapse, strict=True)

        subgraph = synapse.subgraph_output
        assert subgraph, "Missing graph"
        assert subgraph.nodes, "Zero nodes"

        graph = nx.MultiDiGraph()
        for node in subgraph.nodes:
            assert node.id not in graph, f"Duplicate node [{node.id}]"
            graph.add_node(node.id)

        for edge in subgraph.edges:
            assert edge.coldkey_source in graph.nodes, f'Edge source [{edge.coldkey_source}] is not a node'
            assert edge.coldkey_destination in graph.nodes, f"Edge destination [{edge.coldkey_destination}] is not a node"

            assert not graph.has_edge(edge.coldkey_source, edge.coldkey_destination, key=edge.evidence.effective_block_number),\
                f"Duplicate edge (from={edge.coldkey_source}, to={edge.coldkey_destination}, block={edge.evidence.effective_block_number})"

            graph.add_edge(edge.coldkey_source, edge.coldkey_destination, key=edge.evidence.effective_block_number)

        assert nx.is_weakly_connected(graph), "Graph is not fully connected"


    async def _validate_edges(self, hotkey: str, edges: list[Edge]):

        async def chain_validation(block_number: int, expected_owning_coldkey: str):
            actual_owner = await self.chain_reader.get_hotkey_owner(hotkey, block_number)
            assert actual_owner == expected_owning_coldkey,\
                f"Expected hotkey_owner [{expected_owning_coldkey}]; actual [{actual_owner}] for block [{block_number}]"

        evidences = itertools.chain.from_iterable([
            chain_validation(e.evidence.effective_block_number - 1, e.coldkey_source),
            chain_validation(e.evidence.effective_block_number + 1, e.coldkey_destination),
        ] for e in edges)

        await asyncio.gather(*evidences)

