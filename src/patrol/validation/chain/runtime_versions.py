import json
from pathlib import Path


class RuntimeVersions:
    def __init__(self):
        with open(Path(__file__).parents[2] / "chain_data" / "runtime_versions.json", "rt") as f:
            runtime_versions = json.load(f)

        self.versions = runtime_versions.items()


    def runtime_version_for_block(self, block_number: int) -> int:
        version = next((k for k, v in self.versions if v['block_number_min'] <= block_number <= v['block_number_max']), None)
        return int(version) if version else None