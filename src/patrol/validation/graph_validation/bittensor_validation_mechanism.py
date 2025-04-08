import logging
from typing import Dict, Any
import bittensor as bt
import asyncio
import time
import json

from patrol import constants
from patrol.protocol import GraphPayload, Edge, Node, StakeEvidence, TransferEvidence
from patrol.validation.graph_validation.errors import PayloadValidationError, ErrorPayload, SingleNodeResponse
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.event_processor import EventProcessor

logger = logging.getLogger(__name__)

class BittensorValidationMechanism:

    def __init__(self,  event_fetcher: EventFetcher, event_processer: EventProcessor):
        self.graph_payload = None
        self.event_fetcher = event_fetcher
        self.event_processer = event_processer

    async def validate_payload(self, uid: int, payload: Dict[str, Any] = None, target: str = None) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Starting validation process for uid: {uid}")

        try:
            if not payload:
                raise PayloadValidationError("Empty/Null Payload recieved.")
            
            self.parse_graph_payload(payload)
            
            self.verify_target_in_graph(target)

            self.verify_graph_connected()

            await self.verify_edge_data()

        except SingleNodeResponse as e:
            logger.error(f"Validation skipped for uid {uid}: {e}")
            return ErrorPayload(message=f"Error: {str(e)}")

        except Exception as e: 
            logger.error(f"Validation error for uid {uid}: {e}")
            return ErrorPayload(message=f"Error: {str(e)}")

        validation_time = time.time() - start_time
        logger.info(f"Validation finished for {uid}. Completed in {validation_time:.2f} seconds")

        return self.graph_payload

    def parse_graph_payload(self, payload: dict) -> None:
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
            
            seen_edges = set()  # To track unique edges
            for edge in payload['edges']:
                # Create a key tuple from the edge properties
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
                
                # Check for duplicate edge
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
        
        self.graph_payload = GraphPayload(nodes=nodes, edges=edges)
    
    def verify_target_in_graph(self, target: str) -> None:

        if len(self.graph_payload.nodes) < 2:
            raise SingleNodeResponse("Only single node provided.")

        def find_target(target):
            for edge in self.graph_payload.edges:
                if edge.coldkey_destination == target:
                    return True
                elif edge.coldkey_source == target:
                    return True
                elif edge.coldkey_owner == target:
                    return True
            return False
        
        if not find_target(target):
            raise PayloadValidationError("Target not found in payload.")

    def verify_graph_connected(self):
        """
        Checks whether the graph is fully connected using a union-find algorithm.
        Raises a ValueError if the graph is not fully connected.
        """
        # Initialize union-find parent dictionary for each node
        parent = {}

        def find(x: str) -> str:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: str, y: str):
            rootX = find(x)
            rootY = find(y)
            if rootX != rootY:
                parent[rootY] = rootX

        # Initialize each node's parent to itself
        for node in self.graph_payload.nodes:
            parent[node.id] = node.id

        # Process all edges, treating them as undirected connections
        for edge in self.graph_payload.edges:
            src = edge.coldkey_source
            dst = edge.coldkey_destination
            own = edge.coldkey_owner

            if src not in parent or dst not in parent:
                raise ValueError("Edge refers to a node not in the payload")

            union(src, dst)

            if own:
                if own not in parent:
                    raise ValueError("Edge owner refers to a node not in the payload")
                union(src, own)
                union(dst, own)

        # Check that all nodes have the same root
        roots = {find(node.id) for node in self.graph_payload.nodes}
        if len(roots) != 1:
            raise ValueError("Graph is not fully connected.")
    
    async def verify_block_ranges(self, block_numbers):

        current_block = await self.event_fetcher.get_current_block()
        min_block = constants.Constants.LOWER_BLOCK_LIMIT

        invalid_blocks = [b for b in block_numbers if not (min_block <= b <= current_block)]
        if invalid_blocks:
            raise PayloadValidationError(
                f"Found {len(invalid_blocks)} invalid block(s) outside the allowed range "
                f"[{min_block}, {current_block}]: {invalid_blocks}"
            )

    async def verify_edge_data(self):

        block_numbers = []

        for edge in self.graph_payload.edges:
            block_numbers.append(edge.evidence.block_number)

        await self.verify_block_ranges(block_numbers)

        events = await self.event_fetcher.fetch_all_events(block_numbers)

        processed_events = await self.event_processer.process_event_data(events)

        validation_block_numbers = []

        event_keys = set()
        for event in processed_events:
            evidence = event.get('evidence', {})
            event_key = json.dumps({
                "coldkey_source": event.get("coldkey_source"),
                "coldkey_destination": event.get("coldkey_destination"),
                "coldkey_owner": event.get("coldkey_owner"),
                "category": event.get("category"),
                "type": event.get("type"),
                "rao_amount": evidence.get("rao_amount"),
                "block_number": evidence.get("block_number"),
                "destination_net_uid": evidence.get("destination_net_uid"),
                "source_net_uid": evidence.get("source_net_uid"),
                "alpha_amount": evidence.get("alpha_amount"),
                "delegate_hotkey_source": evidence.get("delegate_hotkey_source"),
                "delegate_hotkey_destination": evidence.get("delegate_hotkey_destination"),
            }, sort_keys=True)
            validation_block_numbers.append(evidence.get("block_number"))
            event_keys.add(event_key)

        # Check each graph edge against processed chain events
        missing_edges = []
        for edge in self.graph_payload.edges:
            ev = vars(edge.evidence)
            edge_key = json.dumps({
                "coldkey_source": edge.coldkey_source,
                "coldkey_destination": edge.coldkey_destination,
                "coldkey_owner": edge.coldkey_owner,
                "category": edge.category,
                "type": edge.type,
                "rao_amount": ev.get("rao_amount"),
                "block_number": ev.get("block_number"),
                "destination_net_uid": ev.get("destination_net_uid"),
                "source_net_uid": ev.get("source_net_uid"),
                "alpha_amount": ev.get("alpha_amount"),
                "delegate_hotkey_source": ev.get("delegate_hotkey_source"),
                "delegate_hotkey_destination": ev.get("delegate_hotkey_destination"),
            }, sort_keys=True)

            if edge_key not in event_keys:
                block_number = ev.get("block_number")
                if block_number not in validation_block_numbers:
                    continue  # Skip this edge; block was never fetched
                else:
                    missing_edges.append(edge_key)  # Block was fetched, but the edge did not match any event

        if missing_edges:
            raise PayloadValidationError(f"{len(missing_edges)} edges not found in on-chain events.")

        logger.debug("All edges matched with on-chain events.")

# Example usage:
if __name__ == "__main__":

    import json

    from patrol.chain_data.coldkey_finder import ColdkeyFinder
    from patrol.chain_data.substrate_client import SubstrateClient
    from patrol.chain_data.runtime_groupings import load_versions
    bt.debug()

    file_path = "example_subgraph_output.json"
    with open(file_path, "r") as f:
        payload = json.load(f)

    async def main():

        network_url = "wss://archive.chain.opentensor.ai:443/"
        versions = load_versions()
        
        client = SubstrateClient(runtime_mappings=versions, network_url=network_url, max_retries=3)
        await client.initialize()

        fetcher = EventFetcher(client)
        coldkey_finder = ColdkeyFinder(client)
        event_processor = EventProcessor(coldkey_finder=coldkey_finder)

        validator = BittensorValidationMechanism(fetcher, event_processor)
        
        # Run the validation
        result = await validator.validate_payload(uid=1, payload=payload, target="5EPdHVcvKSMULhEdkfxtFohWrZbFQtFqwXherScM7B9F6DUD")
            # bt.logging.info("Validated Payload:", result)

    asyncio.run(main())