from fastapi import FastAPI
import bittensor as bt
import logging
import json

from patrol.protocol import PatrolSynapse, GraphPayload, Node, Edge, TransferEvidence, StakeEvidence
from patrol.validation.graph_validation.errors import PayloadValidationError

def parse_graph_payload(payload: dict) -> GraphPayload:
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
        
        return GraphPayload(nodes=nodes, edges=edges)

with open('example_subgraph_output.json', 'r') as file:
    payload = json.load(file)

subgraph_payload = parse_graph_payload(payload)

app = FastAPI()

bt.debug()

@app.post("/PatrolSynapse")
async def handle_patrol_synapse(patrol: PatrolSynapse):
    # Log the incoming request
    bt.logging.info(f"Received request with payload: {patrol.model_dump_json()}")
    
    patrol.subgraph_output = subgraph_payload
    return patrol