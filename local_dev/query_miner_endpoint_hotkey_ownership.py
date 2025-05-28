import asyncio
import time
import bittensor as bt
import uuid
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from collections import namedtuple
from patrol.chain_data.substrate_client import SubstrateClient
from patrol.chain_data.runtime_groupings import load_versions
from patrol.validation.chain.runtime_versions import RuntimeVersions
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_challenge import HotkeyOwnershipValidator
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient, MinerTaskException
from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.hotkey_ownership.hotkey_target_generation import HotkeyTargetGenerator
from patrol.protocol import HotkeyOwnershipSynapse

# Simple data class to store detailed validation results
@dataclass
class ValidationResult:
    target_hotkey: str
    challenge_id: str
    timestamp: datetime
    is_valid: bool
    error_message: str = None
    response_time: float = 0
    overall_score: float = 0
    responsiveness_score: float = 0
    node_count: int = 0
    edge_count: int = 0

# Custom JSON encoder to handle UUID and datetime objects
class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

class DebugMinerClient(HotkeyOwnershipMinerClient):
    """Wraps the standard client with additional logging and error handling"""
    
    async def execute_task(self, axon_info, synapse):
        """Execute task with extended debugging"""
        print(f"Sending request to {axon_info.ip}:{axon_info.port}")
        print(f"Target hotkey: {synapse.target_hotkey_ss58}")
        
        # Add empty subgraph_output to avoid None error on server side
        if not hasattr(synapse, 'subgraph_output') or synapse.subgraph_output is None:
            synapse.subgraph_output = {"nodes": [], "edges": []}
        
        start_time = time.perf_counter()
        try:
            # Forward the request using dendrite client
            response = await self._dendrite.forward(
                axon_info,
                synapse,
                deserialize=True,
                timeout=60
            )
            response_time = time.perf_counter() - start_time
            
            # Basic error checking on response
            if hasattr(response, 'is_failure') and response.is_failure:
                raise MinerTaskException(f"Error: {response.dendrite.status_message}; status {response.dendrite.status_code}")
            
            return response, response_time
            
        except Exception as e:
            print(f"Request error: {type(e).__name__}: {str(e)}")
            raise

async def test_miner(num_requests):
    bt.debug()
    
    # # Define server endpoints
    # MINER_IP = "127.0.0.1"  # Use localhost instead of 0.0.0.0
    # MINER_PORT = 8000

    MINER_IP = "miner-alb-864990047.eu-west-2.elb.amazonaws.com"
    MINER_PORT = 5081
    
    # Connect to substrate chain
    network_url = "ws://5.9.118.137:9944"
    versions = load_versions()
    client = SubstrateClient(runtime_mappings=versions, network_url=network_url)
    
    # Initialize substrate connections
    await client.initialize()
    
    # Set up chain reader and validator components
    chain_reader = ChainReader(client, RuntimeVersions())
    
    # Generate real hotkey targets from the chain
    target_generator = HotkeyTargetGenerator(substrate_client=client)
    max_block_number = 5551978
    hotkey_addresses = await target_generator.generate_targets(num_targets=num_requests, max_block_number=max_block_number)
    
    # Create wallets for testing
    wallet_vali = bt.wallet(name="validator", hotkey="vali_1")
    wallet_vali.create_if_non_existent(False, False)
    
    wallet_miner = bt.wallet(name="miners", hotkey="miner_1")
    wallet_miner.create_if_non_existent(False, False)
    
    # Create validator and scoring components
    validator = HotkeyOwnershipValidator(chain_reader)
    scoring = HotkeyOwnershipScoring()
    
    # Create dendrite for client requests
    dendrite = bt.dendrite(wallet=wallet_vali)
    
    # Create the miner client
    miner_client = DebugMinerClient(dendrite=dendrite)
    
    # Create axon info for the miner we're connecting to
    axon_info = bt.axon(wallet=wallet_miner).info()
    axon_info.ip = MINER_IP
    axon_info.port = MINER_PORT
    
    # List to collect all validation results
    all_results = []
    
    # Process responses and validate them
    for i in range(min(num_requests, len(hotkey_addresses))):
        target_hotkey = hotkey_addresses[i % len(hotkey_addresses)]
        
        batch_id = uuid.uuid4()
        challenge_id = uuid.uuid4()
        
        print(f"Request {i+1}/{num_requests} for hotkey: {target_hotkey}")
        print(f"Challenge ID: {challenge_id}")
        
        try:
            # Create the synapse object for the request
            request_synapse = HotkeyOwnershipSynapse(
                target_hotkey_ss58=target_hotkey,
                max_block_number=max_block_number,
                batch_id=str(batch_id),
                task_id=str(challenge_id)
            )
            
            # Send request using client and time it
            try:
                start_time = time.perf_counter()
                
                # Set timeout for the operation
                response_synapse, response_time = await asyncio.wait_for(
                    miner_client.execute_task(axon_info, request_synapse),
                    timeout=60.0  # 60 second timeout
                )
                
                # Validate the response
                try:
                    await validator.validate(
                        response_synapse, 
                        target_hotkey,
                        max_block_number
                    )
                    is_valid = True
                    error = None
                except Exception as e:
                    is_valid = False
                    error = str(e)
                
                # Score the results
                score = scoring.score(is_valid, response_time)
                
                # Get node and edge counts from the response
                subgraph = response_synapse.subgraph_output
                nodes = subgraph.get("nodes", []) if isinstance(subgraph, dict) else getattr(subgraph, "nodes", [])
                edges = subgraph.get("edges", []) if isinstance(subgraph, dict) else getattr(subgraph, "edges", [])
                node_count = len(nodes) if nodes is not None else 0
                edge_count = len(edges) if edges is not None else 0
                
                # Create a validation result
                validation_result = ValidationResult(
                    target_hotkey=target_hotkey,
                    challenge_id=str(challenge_id),
                    timestamp=datetime.now(),
                    is_valid=is_valid,
                    error_message=error,
                    response_time=response_time,
                    overall_score=score.overall,
                    responsiveness_score=score.response_time,
                    node_count=node_count,
                    edge_count=edge_count
                )
                
                # Add to results
                all_results.append(validation_result)
                
                # Log validation results
                print(f"Request completed successfully")
                print(f"Response validates: {is_valid}")
                if is_valid:
                    print(f"Score: {score.overall}")
                else:
                    print(f"Validation error: {error}")
                print(f"Subgraph contains {node_count} nodes and {edge_count} edges")
                
            except asyncio.TimeoutError:
                print(f"Request timed out after 60 seconds")
                validation_result = ValidationResult(
                    target_hotkey=target_hotkey,
                    challenge_id=str(challenge_id),
                    timestamp=datetime.now(),
                    is_valid=False,
                    error_message="Request timed out"
                )
                all_results.append(validation_result)
                
        except Exception as e:
            print(f"Error in request {i+1}: {str(e)}")
            
            # Create an error result
            validation_result = ValidationResult(
                target_hotkey=target_hotkey,
                challenge_id=str(challenge_id),
                timestamp=datetime.now(),
                is_valid=False,
                error_message=str(e)
            )
            all_results.append(validation_result)
    
    # Convert results to dictionaries for JSON serialization
    scores_dict_list = [asdict(result) for result in all_results]
    
    # Save the list of dictionaries to a JSON file using the custom encoder
    output_filename = f"hotkey_ownership_scores_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_filename, "w") as f:
        json.dump(scores_dict_list, f, indent=4, cls=CustomEncoder)
    
    print(f"\nSaved {len(all_results)} validation results to {output_filename}")
    
    return all_results
    
if __name__ == "__main__":
    bt.debug()
    REQUESTS = 100
    asyncio.run(test_miner(REQUESTS))