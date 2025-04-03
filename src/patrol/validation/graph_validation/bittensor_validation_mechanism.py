from typing import Dict, Any
import bittensor as bt
import traceback
import asyncio
import time

from patrol.validation.graph_validation.validation_models import GraphPayload, Edge, Node, StakeEvidence, TransferEvidence
from patrol.chain_data import get_block_events
from patrol.constants import Constants
# Configure logging to print to console
bt.logging( 
    debug=True,
    trace=True,
    record_log=False,
    logging_dir=None  # Disable file logging
)

class BittensorValidationMechanism:
    def __init__(self):
        self.graph_payload = None

    async def validate_payload(self, uid: int, payload: Dict[str, Any] = None, target: str = None, target_block_number: int = None) -> Dict[str, Any]:
        start_time = time.time()
        bt.logging.info(f"Starting validation process for uid: {uid}")

        try:
            # Validate and parse the payload
            self.parse_graph_payload(payload)
            
            # check connected 
            self.verify_graph_connected()
            # validate the data in edges (indirectly this will validate the nodes as well)
            b = time.time()
            await self.verify_edge_data()
            edge_time = time.time() - b
            bt.logging.info(f"Finished verify data in: {edge_time}")

        except Exception as e: 
            bt.logging.error(f"Validation error for uid {uid}: {e}")
            traceback.print_exc()
            return {"error": str(e)}

        validation_time = time.time() - start_time
        bt.logging.info(f"Validation passed for {uid}. Completed in {validation_time:.2f} seconds")

        return self.return_validated_payload()

    def parse_graph_payload(self, payload: dict) -> GraphPayload:
        """
        Parses a dictionary into a GraphPayload data structure.
        This will raise an error if required fields are missing, if there are extra fields,
        or if a duplicate edge is found.
        """
        try:
            # Convert list of node dictionaries into Node objects
            nodes = [Node(**node) for node in payload['nodes']]
            
            edges = []
            seen_edges = set()  # To track unique edges
            for edge in payload['edges']:
                # Create a key tuple from the edge properties
                evidence = edge.get('evidence')
                if evidence is None:
                    raise ValueError("Edge is missing the 'evidence' field.")
                
                key = (
                    edge.get('source'),
                    edge.get('destination'),
                    edge.get('type'),
                    evidence.get('amount'),
                    evidence.get('block_number')
                )
                
                # Check for duplicate edge
                if key in seen_edges:
                    raise ValueError(f"Duplicate edge detected: {key}")
                seen_edges.add(key)

                if edge.get('type') == "transfer":                
                    edges.append(
                        Edge(
                            source=edge['source'],
                            destination=edge['destination'],
                            type=edge['type'],
                            evidence=TransferEvidence(**edge['evidence'])
                        )
                    )
                elif edge.get('type') == "staking":
                    edges.append(
                        Edge(
                            source=edge['source'],
                            destination=edge['destination'],
                            type=edge['type'],
                            evidence=StakeEvidence(**edge['evidence'])
                        )
                    )

        except TypeError as e:
            raise ValueError(f"Payload validation error: {e}")
        
        self.graph_payload = GraphPayload(nodes=nodes, edges=edges)
        return self.graph_payload
    
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
            if edge.source not in parent or edge.destination not in parent:
                raise ValueError("Edge refers to a node not in the payload")
            union(edge.source, edge.destination)

        # Check that all nodes have the same root
        roots = {find(node.id) for node in self.graph_payload.nodes}
        if len(roots) != 1:
            raise ValueError("Graph is not fully connected.")
    
    async def verify_edge_data(self):

        block_number_set = set()

        start_time = time.time()

        async with bt.AsyncSubtensor(network=Constants.ARCHIVE_NODE_ADDRESS) as subtensor:

            tasks = []

            for edge in self.graph_payload.edges:
                # Can we perform this without needing to initialise substrateinterface?
                dest_valid = subtensor.substrate.is_valid_ss58_address(edge.destination)
                source_valid = subtensor.substrate.is_valid_ss58_address(edge.source)

                if not dest_valid or not source_valid:
                    raise ValueError("Invalid address in an included edge")
                
                if edge.evidence.block_number not in block_number_set:

                    # here we need to check the block is greater than the limit
                    block_number_set.add(edge.evidence.block_number)

                    task = subtensor.substrate.get_block_hash(block_id=edge.evidence.block_number)
                    tasks.append(task)

            hashes = await asyncio.gather(*tasks)

        start_time = time.time()

        events = await get_block_events(hashes)

        for block_hash, value in events.items():
            print(f"Block {block_hash}: {value}")

        set_time = time.time() - start_time
        bt.logging.info(f"Finished fetching block events in: {set_time}")


        # Process the gathered events, computing hashes for each Transfer event
        # event_sets = set()
        # for block_number, events in events_list:
        #     for event in events:
        #         # Check if the event is a Transfer event
        #         if event['event'].value['event_id'] == "Transfer":
        #             attributes = event['event'].value['attributes']
        #             # Adjust keys as needed; here we assume they are named 'from', 'to', and 'amount'
        #             source = attributes['from']
        #             destination = attributes['to']
        #             amount = attributes['amount']
        #             evt_hash = (source, destination, amount, block_number)
        #             event_sets.add(evt_hash)
        #         # elif "Stake" in event['event'].value['event_id']:
        #         #     attributes = event['event'].value['attributes']
        #         #     # Adjust keys as needed; here we assume they are named 'from', 'to', and 'amount'
        #         #     source = attributes['from']
        #         #     destination = attributes['to']
        #         #     amount = attributes['amount']
        #         #     evt_hash = (source, destination, amount, block_number)
        #         #     event_sets.add(evt_hash)

        # set_time = time.time() - start_time
        # bt.logging.info(f"Finished building edge set in: {set_time}")

        # start_time = time.time()

        # for edge in self.graph_payload.edges:
        #     # We only check Transfer type edges (adjust case as needed)
        #     if edge.type.lower() == "transfer":
        #         expected_set = (edge.source, edge.destination, edge.evidence.amount, edge.evidence.block_number)
        #         if expected_set not in event_sets:
        #             raise ValueError(f"Missing event for edge: {expected_set}")
                
        # set_time = time.time() - start_time
        # bt.logging.info(f"Finished checking edges against set in: {set_time}")

        # bt.logging.info("All edge events verified successfully.")

    def return_validated_payload(self):
        return self.graph_payload

# Example usage:
if __name__ == "__main__":
    # Create an example payload
    payload = {
        "nodes": [
            {
                "id": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
                "type": "wallet",
                "origin": "bittensor"
            },
            {
                "id": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
                "type": "wallet",
                "origin": "bittensor"
            },
            {
                "id": "5DfhUJHfYWzUyrLwRtyKjjCdmfY3T2bEZmMHgtvSvo5PWjrz",
                "type": "wallet",
                "origin": "bittensor"
            },
        ],
        "edges": [
            {
                "source": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
                "destination": "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2",
                "type": "transfer",
                "evidence": {
                    "amount": 4990000000,
                    "block_number": 1814458
                }
            },
            {
                "source": "5DfhUJHfYWzUyrLwRtyKjjCdmfY3T2bEZmMHgtvSvo5PWjrz",
                "destination": "5Dtq3wuBRMuZZhkT991wiViQ4iyPGzGnoRQ6D8QzoMfnj7xM",
                "type": "transfer",
                "evidence": {
                    "amount": 5000000000,
                    "block_number": 1806450
                }
            }
        ]
    }

    async def main():
        validator = BittensorValidationMechanism()
        
        # Run the validation
        result = await validator.validate_payload(uid=1, payload=payload)
        print("Validated Payload:", result)

    asyncio.run(main())