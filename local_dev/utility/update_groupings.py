import json
import bittensor as bt
from typing import Dict, Any

# Input file path and output file path
INPUT_FILE = "runtime_versions.json"
OUTPUT_FILE = "version_blocks_with_hashes.json"

def load_versions(filepath: str) -> Dict[str, Dict[str, int]]:
    with open(filepath, 'r') as f:
        return json.load(f)

def fetch_block_hash(subtensor: bt.subtensor, block_number: int) -> str:
    return subtensor.substrate.get_block_hash(block_id=block_number)

def enrich_versions_with_hashes(versions: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, Any]]:
    subtensor = bt.subtensor(network="finney")
    enriched: Dict[str, Dict[str, Any]] = {}

    for version, bounds in versions.items():
        block_min = bounds["min"]
        block_max = bounds["max"]

        hash_min = fetch_block_hash(subtensor, block_min)
        hash_max = fetch_block_hash(subtensor, block_max)

        enriched[version] = {
            "block_number_min": block_min,
            "block_hash_min": hash_min,
            "block_number_max": block_max,
            "block_hash_max": hash_max
        }

    return enriched

def save_to_file(data: Dict[str, Any], filepath: str) -> None:
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    versions = load_versions(INPUT_FILE)
    enriched_versions = enrich_versions_with_hashes(versions)
    save_to_file(enriched_versions, OUTPUT_FILE)
    print(f"Saved enriched block hashes to {OUTPUT_FILE}")