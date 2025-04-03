import bittensor as bt
import time
import asyncio
from typing import Dict, List
from datetime import datetime

from patrol.constants import Constants
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.event_parser import process_event_data
from patrol.chain_data.coldkey_finder import ColdkeyFinder

class SubgraphGenerator:
    
    # These parameters control the subgraph generation:
    # - _max_future_events: The number of events into the past you will collect
    # - _max_historic_events: The number of events into the future you will collect
    # Adjust these based on your needs - higher values give higher chance of being able to find and deliver larger subgraphs, 
    # but will require more time and resources to generate
    def __init__(self,  event_fetcher: EventFetcher, coldkey_finder: ColdkeyFinder, max_future_events=900, max_historic_events=900, timeout=Constants.MAX_RESPONSE_TIME):
        self.event_fetcher = event_fetcher
        self.coldkey_finder = coldkey_finder
        self._max_future_events = max_future_events
        self._max_historic_events = max_historic_events
        self.timeout = timeout
        self.start_time = None
    
    def generate_block_numbers(self, target_block: int, upper_block_limit: int, lower_block_limit: int = Constants.LOWER_BLOCK_LIMIT) -> List[int]:

        bt.logging.info(f"Generating block numbers for target block: {target_block}")

        # Calculate range of blocks
        start_block = max(target_block - self._max_historic_events, lower_block_limit)
        end_block = min(target_block + self._max_future_events, upper_block_limit)

        return list(range(start_block, end_block + 1))

    def generate_adjacency_graph_from_events(self, events: List[Dict]) -> Dict:

        start_time = time.time()
        # Build an undirected graph as an adjacency list.
        graph = {}

        # Iterate over the events and add edges based on available keys.
        # We look for 'coldkey_source', 'coldkey_destination' and 'coldkey_owner'
        for event in events:
            src = event.get("coldkey_source")
            dst = event.get("coldkey_destination")
            ownr = event.get("coldkey_owner")

            connections = []
            if src and dst and src != dst:
                connections.append((src, dst))
                connections.append((dst, src))
            if src and ownr and src != ownr:
                connections.append((src, ownr))
                connections.append((ownr, src))

            for a, b in connections:
                if a not in graph:
                    graph[a] = []
                graph[a].append({"neighbor": b, "event": event})

        bt.logging.info(f"Adjacency graph created in {time.time() - start_time} seconds.")
        return graph

    def generate_subgraph_from_adjacency_graph(self, adjacency_graph: Dict, target_address: str) -> Dict:
        start_time = time.time()

        subgraph = {
            "nodes": [],
            "edges": []
        }
        seen_nodes = set()
        seen_edges = set()
        queue = [target_address]

        while queue:
            current = queue.pop(0)

            if current not in seen_nodes:
                subgraph["nodes"].append({
                    "id": current,
                    "type": "wallet",
                    "origin": "bittensor"
                })
                seen_nodes.add(current)

            for conn in adjacency_graph.get(current, []):
                neighbor = conn["neighbor"]
                event = conn["event"]
                edge_key = (current, neighbor, event.get('id', id(event)))

                if edge_key not in seen_edges:
                    subgraph["edges"].append({
                        "source": current,
                        "target": neighbor,
                        "event": event
                    })
                    seen_edges.add(edge_key)

                if neighbor not in seen_nodes and neighbor not in queue:
                    queue.append(neighbor)

        subgraph_length = len(subgraph['nodes']) + len(subgraph['edges'])
        bt.logging.info(f"Subgraph graph of length {subgraph_length} created in {time.time() - start_time} seconds.")

        return subgraph


    async def run(self, target_address:str, target_block:int, current_block: int):

        block_numbers = self.generate_block_numbers(target_block, current_block)

        events = await self.event_fetcher.fetch_all_events(block_numbers)

        processed_events = await process_event_data(events, self.coldkey_finder)

        adjacency_graph = self.generate_adjacency_graph_from_events(processed_events)

        subgraph = self.generate_subgraph_from_adjacency_graph(adjacency_graph, target_address)

        return subgraph

if __name__ == "__main__":

    from async_substrate_interface import AsyncSubstrateInterface
    from patrol.constants import Constants

    async def example():

        bt.debug()

        fetcher = EventFetcher()
        await fetcher.initialise_substrate_connections()

        start_time = time.time()

        target = "5HBtpwxuGNL1gwzwomwR7sjwUt8WXYSuWcLYN6f9KpTZkP4k"
        target_block = 5163655
        current_block = 6000000

        async with AsyncSubstrateInterface(url=Constants.ARCHIVE_NODE_ADDRESS) as substrate:
            coldkey_finder = ColdkeyFinder(substrate)

            subgraph_generator = SubgraphGenerator(event_fetcher=fetcher, coldkey_finder=coldkey_finder, max_future_events=1000, max_historic_events=1000)
            output = await subgraph_generator.run(target, target_block, current_block)

        volume = len(output['nodes']) + len(output['edges'])

        # print(f"Volume: {volume}")

        # bt.logging.info(output)
        bt.logging.info(f"Finished: {time.time() - start_time} with volume: {volume}")

    asyncio.run(example())


