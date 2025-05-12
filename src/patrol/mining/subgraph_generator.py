import time
import asyncio
from typing import Dict, List

import bittensor as bt

from patrol.constants import Constants
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.event_processor import EventProcessor
from patrol.protocol import GraphPayload, Node, Edge, TransferEvidence, StakeEvidence

class SubgraphGenerator:
    
    # These parameters control the subgraph generation:
    # - _max_future_events: The number of events into the past you will collect
    # - _max_past_events: The number of events into the future you will collect
    # - _batch_size: The number of events fetched in one go from the block chain
    # Adjust these based on your needs - higher values give higher chance of being able to find and deliver larger subgraphs, 
    # but will require more time and resources to generate
    
    def __init__(self,  event_fetcher: EventFetcher, event_processor: EventProcessor, max_future_events: int = 50, max_past_events: int = 50, batch_size: int = 25, timeout=10):
        self.event_fetcher = event_fetcher
        self.event_processor = event_processor
        self._max_future_events = max_future_events
        self._max_past_events = max_past_events
        self._batch_size = batch_size
        self.timeout = timeout
    
    async def generate_block_numbers(self, target_block: int, upper_block_limit: int, lower_block_limit: int = Constants.LOWER_BLOCK_LIMIT) -> List[int]:

        bt.logging.info(f"Generating block numbers for target block: {target_block}")

        start_block = max(target_block - self._max_past_events, lower_block_limit)
        end_block = min(target_block + self._max_future_events, upper_block_limit)

        return list(range(start_block, end_block + 1))

    def generate_adjacency_graph_from_events(self, events: List[Dict]) -> Dict:

        start_time = time.time()
        graph = {}

        # Iterate over the events and add edges based on available keys.
        # We look for 'coldkey_source', 'coldkey_destination' and 'coldkey_owner'
        for event in events:
            if event.get('evidence', {}).get('rao_amount') == 0:
                continue
            src = event.get("coldkey_source")
            dst = event.get("coldkey_destination")
            ownr = event.get("coldkey_owner")

            connections = []
            if src and dst:
                connections.append((src, dst))
                connections.append((dst, src))
            if src and ownr:
                connections.append((src, ownr))
                connections.append((ownr, src))
            if dst and ownr:
                connections.append((dst, ownr))
                connections.append((ownr, dst))

            for a, b in connections:
                if a not in graph:
                    graph[a] = []
                graph[a].append({"neighbor": b, "event": event})

        bt.logging.info(f"Adjacency graph created in {time.time() - start_time} seconds.")
        return graph

    def generate_subgraph_from_adjacency_graph(self, adjacency_graph: Dict, target_address: str) -> Dict:
        start_time = time.time()

        nodes = []
        edges = []

        seen_nodes = set()
        seen_edges = set()
        queue = [target_address]

        while queue:
            current = queue.pop(0)

            if current not in seen_nodes:
                nodes.append(
                    Node(
                        id=current,
                        type="wallet",
                        origin="bittensor"
                    ))
                seen_nodes.add(current)

            for conn in adjacency_graph.get(current, []):
                neighbor = conn["neighbor"]
                event = conn["event"]
                evidence = event['evidence']
                edge_key = (
                    event.get('coldkey_source'),
                    event.get('coldkey_destination'),
                    event.get('category'),
                    event.get('type'),
                    evidence.get('rao_amount'),
                    evidence.get('block_number')
                )

                try:
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        if event.get('category') == "balance":  
                            edges.append(
                                Edge(
                                    coldkey_source=event['coldkey_source'],
                                    coldkey_destination=event['coldkey_destination'],
                                    category=event['category'],
                                    type=event['type'],
                                    evidence=TransferEvidence(**event['evidence'])
                                )
                            )
                        elif event.get('category') == "staking":
                            edges.append(
                                Edge(
                                    coldkey_source=event['coldkey_source'],
                                    coldkey_destination=event['coldkey_destination'],
                                    coldkey_owner=event.get('coldkey_owner'),
                                    category=event['category'],
                                    type=event['type'],
                                    evidence=StakeEvidence(**event['evidence'])
                                )
                            )
                except Exception as e:
                    bt.logging.debug(f"Issue with adding edge to subgraph, skipping for now. Error: {e}")

                if neighbor not in seen_nodes and neighbor not in queue:
                    queue.append(neighbor)

        subgraph_length = len(nodes) + len(edges)
        bt.logging.info(f"Subgraph graph of length {subgraph_length} created in {time.time() - start_time} seconds.")

        return GraphPayload(nodes=nodes, edges=edges)


    async def run(self, target_address:str, target_block:int, max_block_number: int):

        block_numbers = await self.generate_block_numbers(target_block, upper_block_limit=max_block_number)

        events = await self.event_fetcher.fetch_all_events(block_numbers)

        processed_events = await self.event_processor.process_event_data(events)

        adjacency_graph = self.generate_adjacency_graph_from_events(processed_events)

        subgraph = self.generate_subgraph_from_adjacency_graph(adjacency_graph, target_address)

        return subgraph

if __name__ == "__main__":

    from patrol.chain_data.coldkey_finder import ColdkeyFinder

    async def example():

        bt.debug()

        from patrol.chain_data.substrate_client import SubstrateClient
        from patrol.chain_data.runtime_groupings import load_versions

        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        
        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        await client.initialize()
            
        start_time = time.time()

        target = "5FyCncAf9EBU8Nkcm5gL1DQu3hVmY7aphiqRn3CxwoTmB1cZ"
        target_block = 4179349

        fetcher = EventFetcher(substrate_client=client)
        coldkey_finder = ColdkeyFinder(substrate_client=client)
        event_processor = EventProcessor(coldkey_finder=coldkey_finder)

        subgraph_generator = SubgraphGenerator(event_fetcher=fetcher, event_processor=event_processor, max_future_events=50, max_past_events=50, batch_size=50)
        subgraph = await subgraph_generator.run(target, target_block, max_block_number=4179351)

        volume = len(subgraph.nodes) + len(subgraph.edges)

        import dataclasses
        import json
        output = dataclasses.asdict(subgraph)

        with open("subgraph_output.json", "w") as f:
            json.dump(output, f, indent=2)

        # bt.logging.info(output)
        bt.logging.info(f"Finished: {time.time() - start_time} with volume: {volume}")

    asyncio.run(example())


