import logging
from typing import Dict, Any, List
import asyncio
import time

from patrol import constants
from patrol.protocol import GraphPayload, Edge, Node, StakeEvidence, TransferEvidence

from patrol.validation.graph_validation.event_checker import EventChecker
from patrol.validation.scoring import ValidationResult
from patrol.validation.graph_validation.errors import PayloadValidationError, SingleNodeResponse

logger = logging.getLogger(__name__)

class BittensorValidationMechanism:

    def __init__(self, event_checker: EventChecker):
        self.event_checker = event_checker

    async def validate_payload(self, uid: int, payload: Dict[str, Any] = None, target: str = None, max_block_number: int = None) -> ValidationResult:
        start_time = time.time()
        logger.info(f"{uid}: Starting validation")

        if not payload:
            return ValidationResult(validated=False, message="Empty/Null Payload received.", volume=0)
                
        original_volume = 0

        try:
            graph_payload = self._parse_graph_payload(payload)
            original_volume = len(graph_payload.nodes) + len(graph_payload.edges)
            self._verify_target_in_graph(target, graph_payload)
            self._verify_graph_connected(graph_payload)

            verified_edges = await self._verify_edge_data(graph_payload, max_block_number)

            validated_volume = self._calculate_validated_volume(verified_edges, target)

            if validated_volume < original_volume:
                message = f"Validation passed with some edges unverifiable or zero rao amount for certain edges found: Original Volume:{original_volume}, Validated Volume: {validated_volume}"
            else:
                message = "Validation passed."

        except SingleNodeResponse as e:
            logger.info(f"{uid}: Validation skipped - {e}")
            return ValidationResult(validated=False, message=f"Validation skipped for uid {uid}: {e}", volume=original_volume)

        except Exception as e: 
            logger.info(f"{uid}: Validation error - {e}")
            return ValidationResult(validated=False, message=f"Validation error for uid {uid}: {e}", volume=original_volume)

        validation_time = time.time() - start_time
        logger.info(f"{uid}: Validation finished - {message}. Completed in {validation_time:.2f} seconds")

        return ValidationResult(validated=True, message=message, volume=validated_volume)

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

    async def _verify_block_ranges(self, block_numbers: List[int], max_block_number: int):

        min_block = constants.Constants.LOWER_BLOCK_LIMIT

        invalid_blocks = [b for b in block_numbers if not (min_block <= b <= max_block_number)]
        if invalid_blocks:
            raise PayloadValidationError(
                f"Found {len(invalid_blocks)} invalid block(s) outside the allowed range "
                f"[{min_block}, {max_block_number}]: {invalid_blocks}"
            )
        
    @staticmethod
    def _convert_edges_to_event_data(graph_payload: GraphPayload) -> List[Dict[str, Any]]:
        """
        Convert edges from GraphPayload to event data format required by check_events_by_hash
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
                    "rao_amount": edge.evidence.rao_amount,
                    "destination_net_uid": None,
                    "source_net_uid": None,
                    "alpha_amount": None,
                    "delegate_hotkey_source": None,
                    "delegate_hotkey_destination": None,
                })
            elif edge.category == "staking":
                event_data.update({
                    "rao_amount": edge.evidence.rao_amount,
                    "destination_net_uid": edge.evidence.destination_net_uid,
                    "source_net_uid": edge.evidence.source_net_uid,
                    "alpha_amount": edge.evidence.alpha_amount,
                    "delegate_hotkey_source": edge.evidence.delegate_hotkey_source,
                    "delegate_hotkey_destination": edge.evidence.delegate_hotkey_destination,
                })
            
            event_data_list.append(event_data)
        
        return event_data_list
    
    async def _verify_edge_data(self, graph_payload: GraphPayload, max_block_number: int) -> List[dict]:

        block_numbers = {edge.evidence.block_number for edge in graph_payload.edges}
        
        await self._verify_block_ranges(block_numbers, max_block_number)
    
        events = self._convert_edges_to_event_data(graph_payload)

        validated_edges = await self.event_checker.check_events_by_hash(events)

        if len(validated_edges) == 0:
            raise PayloadValidationError("No matching edges found in payload.")
        else:
            return validated_edges
        
    def _generate_adjacency_graph_from_events(self, events: List[Dict]) -> Dict:

        graph = {}

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

        return graph
    
    def _generate_subgraph_volume_from_adjacency_graph(self, adjacency_graph: dict, target_address: str) -> Dict:

        seen_nodes = set()
        seen_edges = set()
        queue = [target_address]

        while queue:
            current = queue.pop(0)

            if current not in seen_nodes:
                seen_nodes.add(current)

            for conn in adjacency_graph.get(current, []):
                neighbor = conn["neighbor"]
                event = conn["event"]
                edge_key = (
                    event.get('coldkey_source'),
                    event.get('coldkey_destination'),
                    event.get('edge_category'),
                    event.get('edge_type'),
                    event.get('rao_amount'),
                    event.get('block_number')
                )

                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)

                if neighbor not in seen_nodes and neighbor not in queue:
                    queue.append(neighbor)

        return len(seen_nodes) + len(seen_edges)

    def _calculate_validated_volume(self, validated_edges: List[dict], target_address: str) -> int:

        adjacency_graph = self._generate_adjacency_graph_from_events(validated_edges)

        volume = self._generate_subgraph_volume_from_adjacency_graph(adjacency_graph, target_address)

        return volume

# Example usage:
if __name__ == "__main__":

    import json

    async def main():

        class MockEventChecker:

            async def check_events_by_hash(self, event_data_list: List[Dict[str, Any]]) -> List[Dict]:

                return event_data_list
        
        event_checker = MockEventChecker()

        validator = BittensorValidationMechanism(event_checker=event_checker)

        file_path = "subgraph_output_1.json"
        with open(file_path, "r") as f:
            payload = json.load(f)

        output = await validator.validate_payload(uid=1, payload=payload['subgraph_output'], target="5FyCncAf9EBU8Nkcm5gL1DQu3hVmY7aphiqRn3CxwoTmB1cZ", max_block_number=4179351)

        print(output)

    asyncio.run(main())