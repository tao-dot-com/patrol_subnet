import logging
from collections import deque
from typing import Tuple, Iterable, Deque
from typing import Dict, Any, List
import asyncio
import time
import json

from patrol import constants
from patrol.protocol import GraphPayload, Edge, Node, StakeEvidence, TransferEvidence
from patrol.validation.persistence.event_store_repository import DatabaseEventStoreRepository
from patrol.validation.scoring import ValidationResult
from patrol.validation.graph_validation.errors import PayloadValidationError, SingleNodeResponse
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.event_processor import EventProcessor

logger = logging.getLogger(__name__)

class BittensorValidationMechanism:

    def __init__(self,  event_fetcher: EventFetcher, event_processor: EventProcessor, event_store_repository: DatabaseEventStoreRepository, buffer_size: int = 500):
        self.event_fetcher = event_fetcher
        self.event_processor = event_processor
        self.event_store_repository = event_store_repository
        self.buffer_size = buffer_size

    async def validate_payload(self, uid: int, payload: Dict[str, Any] = None, target: str = None, max_block_number: int = None) -> ValidationResult:
        start_time = time.time()
        logger.info(f"Starting validation process for uid: {uid}")

        if not payload:
            return ValidationResult(validated=False, message="Empty/Null Payload received.", volume=0)

        try:
            graph_payload = self._parse_graph_payload(payload)
            volume = len(graph_payload.nodes) + len(graph_payload.edges)
            self._verify_target_in_graph(target, graph_payload)
            self._verify_graph_connected(graph_payload)

            await self._verify_edge_data(graph_payload, max_block_number)

        except SingleNodeResponse as e:
            logger.info(f"Validation skipped for uid {uid}: {e}")
            return ValidationResult(validated=False, message=f"Validation skipped for uid {uid}: {e}", volume=volume)

        except Exception as e: 
            logger.info(f"Validation error for uid {uid}: {e}")
            return ValidationResult(validated=False, message=f"Validation error for uid {uid}: {e}", volume=volume)

        validation_time = time.time() - start_time
        logger.info(f"Validation finished for {uid}. Completed in {validation_time:.2f} seconds")

        return ValidationResult(validated=True, message="Validation Passed", volume=volume)

    def _parse_graph_payload(self, payload: dict) -> GraphPayload:
        """
        Parses a dictionary into a GraphPayload data structure.
        This will raise an error if required fields are missing, if there are extra fields,
        or if a duplicate edge is found.
        """
        nodes = []
        edges = []
        try:
            seen_nodes = set()
            for node in payload['nodes']:
                node_id = node.get("id")
                if node_id in seen_nodes:
                    raise PayloadValidationError(f"Duplicate node detected: {node_id}")
                seen_nodes.add(node_id)
                nodes.append(Node(**node))
            
            seen_edges = set()
            for edge in payload['edges']:
                evidence = edge.get('evidence')
                if evidence is None:
                    raise PayloadValidationError("Edge is missing the 'evidence' field.")
                
                key = (
                    edge.get('coldkey_source'),
                    edge.get('coldkey_destination'),
                    edge.get('category'),
                    edge.get('type'),
                    evidence.get('rao_amount'),
                    evidence.get('block_number')
                )

                if key in seen_edges:
                    raise PayloadValidationError(f"Duplicate edge detected: {key}")
                seen_edges.add(key)

                if edge.get('category') == "balance":                
                    edges.append(
                        Edge(
                            coldkey_source=edge['coldkey_source'],
                            coldkey_destination=edge['coldkey_destination'],
                            category=edge['category'],
                            type=edge['type'],
                            evidence=TransferEvidence(**edge['evidence'])
                        )
                    )
                elif edge.get('category') == "staking":
                    edges.append(
                        Edge(
                            coldkey_source=edge['coldkey_source'],
                            coldkey_destination=edge['coldkey_destination'],
                            coldkey_owner=edge.get('coldkey_owner'),
                            category=edge['category'],
                            type=edge['type'],
                            evidence=StakeEvidence(**edge['evidence'])
                        )
                    )

        except TypeError as e:
            raise PayloadValidationError(f"Payload validation error: {e}")
        
        return GraphPayload(nodes=nodes, edges=edges)
    
    @staticmethod
    def _convert_edges_to_event_data(graph_payload: GraphPayload) -> List[Dict[str, Any]]:
        """
        Convert edges from GraphPayload to event data format required by check_events_by_hash
        
        Args:
            graph_payload: The graph payload containing edges
            node_info: Dictionary with node_id, node_type, and node_origin
        
        Returns:
            List of event data dictionaries
        """
        event_data_list = []
        
        for edge in graph_payload.edges:
            # Common fields for all edges
            event_data = {
                "node_id": f"node_{edge.coldkey_source}",
                "node_type": "account",
                "node_origin": "bittensor",
                "coldkey_source": edge.coldkey_source,
                "coldkey_destination": edge.coldkey_destination,
                "edge_category": edge.category,
                "edge_type": edge.type,
                "coldkey_owner": edge.coldkey_owner,
                "block_number": edge.evidence.block_number,
            }
            
            # Handle different evidence types
            if edge.category == "balance":
                event_data.update({
                    "evidence_type": "transfer",
                    "rao_amount": edge.evidence.rao_amount,
                    "destination_net_uid": None,
                    "source_net_uid": None,
                    "alpha_amount": None,
                    "delegate_hotkey_source": None,
                    "delegate_hotkey_destination": None,
                })
            elif edge.category == "staking":
                event_data.update({
                    "evidence_type": "stake",
                    "rao_amount": edge.evidence.rao_amount,
                    "destination_net_uid": edge.evidence.destination_net_uid,
                    "source_net_uid": edge.evidence.source_net_uid,
                    "alpha_amount": edge.evidence.alpha_amount,
                    "delegate_hotkey_source": edge.evidence.delegate_hotkey_source,
                    "delegate_hotkey_destination": edge.evidence.delegate_hotkey_destination,
                })
            
            event_data_list.append(event_data)
        
        return event_data_list

    def _verify_target_in_graph(self, target: str, graph_payload: GraphPayload) -> None:

        if len(graph_payload.nodes) < 2:
            raise SingleNodeResponse("Only single node provided.")

        def find_target(target):
            for edge in graph_payload.edges:
                if edge.coldkey_destination == target:
                    return True
                elif edge.coldkey_source == target:
                    return True
                elif edge.coldkey_owner == target:
                    return True
            return False
        
        if not find_target(target):
            raise PayloadValidationError("Target not found in payload.")

    def _verify_graph_connected(self, graph_payload: GraphPayload):
        """
        Checks whether the graph is fully connected using a union-find algorithm (iterative find).
        Raises a ValueError if the graph is not fully connected.
        """
        parent = {}
        size = {}

        def find(x: str) -> str:
            root = x
            while parent[root] != root:
                root = parent[root]
            while x != root:
                parent[x], x = root, parent[x]
            return root

        def union(x: str, y: str):
            rootX = find(x)
            rootY = find(y)

            if rootX != rootY:
                # Always attach the smaller tree under the larger one
                if size[rootX] < size[rootY]:
                    parent[rootX] = rootY
                    size[rootY] += size[rootX]
                else:
                    parent[rootY] = rootX
                    size[rootX] += size[rootY]

        for node in graph_payload.nodes:
            parent[node.id] = node.id
            size[node.id] = 1

        for edge in graph_payload.edges:
            src = edge.coldkey_source
            dst = edge.coldkey_destination
            own = edge.coldkey_owner

            if src not in parent or dst not in parent:
                raise PayloadValidationError("Edge refers to a node not in the payload")

            union(src, dst)

            if own:
                if own not in parent:
                    raise PayloadValidationError("Edge owner refers to a node not in the payload")
                union(src, own)
                union(dst, own)

        # Check that all nodes have the same root
        roots = {find(node.id) for node in graph_payload.nodes}
        if len(roots) != 1:
            raise PayloadValidationError("Graph is not fully connected.")
    
        event_keys = set()
        validation_block_numbers = set()
        queue = asyncio.Queue()

        async def process_buffered_events(buffer: Deque[Tuple[int, Any]]) -> None:
            if not buffer:
                return
            to_process = dict(buffer)
            processed_batch = await self.event_processor.process_event_data(to_process)
            logger.info(f"Received and processed {len(processed_batch)} events.")
            for event in processed_batch:
                key, block_number = self._make_event_key(event)
                event_keys.add(key)
                validation_block_numbers.add(block_number)

        async def consumer_event_queue() -> None:
            buffer: Deque[Tuple[int, Any]] = deque()

            while True:
                events = await queue.get()
                if events is None:
                    break

                buffer.extend(events.items())
                while len(buffer) >= self.buffer_size:
                    temp_buffer = deque(buffer.popleft() for _ in range(self.buffer_size))
                    await process_buffered_events(temp_buffer)

            await process_buffered_events(buffer)

        producer_task = asyncio.create_task(self.event_fetcher.stream_all_events(block_numbers, queue, batch_size=25))
        consumer_task = asyncio.create_task(consumer_event_queue())

        await asyncio.gather(producer_task, consumer_task)
        return event_keys, validation_block_numbers

    async def _verify_edge_data(self, graph_payload: GraphPayload):
        events = self._convert_edges_to_event_data(graph_payload)

        unmatched_count = self.check_events_by_hash(events)

        if unmatched_count == 0:
            logger.debug("All edges matched with on-chain events.")
        else:
            logger.error(f"{unmatched_count} edges unmatched with on-chain events.")
            raise PayloadValidationError("Unmatched edges in payload.")


# Example usage:
if __name__ == "__main__":

    import json

    from patrol.chain_data.coldkey_finder import ColdkeyFinder
    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions

    async def main():

        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        
        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        await client.initialize()

        fetcher = EventFetcher(client)
        coldkey_finder = ColdkeyFinder(client)
        event_processor = EventProcessor(coldkey_finder=coldkey_finder)
        event_store_repository = DatabaseEventStoreRepository()

        validator = BittensorValidationMechanism(fetcher, event_processor, event_store_repository)

        file_path = "subgraph_output_3.json"
        with open(file_path, "r") as f:
            payload = json.load(f)

        tasks = [validator.validate_payload(uid=1, payload=payload, target="5Ck5g3MaG7Ho29ZqmcTFgq8zTxmnrwxs6FR94RsCEquT6nLy", max_block_number=5352419) for _ in range(8)]

        await asyncio.gather(*tasks)

    asyncio.run(main())