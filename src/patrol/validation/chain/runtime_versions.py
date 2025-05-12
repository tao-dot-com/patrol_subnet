import json
from pathlib import Path


class RuntimeVersions:
    def __init__(self, versions: dict | None = None):
        if not versions:
            with open(Path(__file__).parents[2] / "chain_data" / "runtime_versions.json", "rt") as f:
                self.versions = json.load(f)

        else:
            self.versions = versions

    def runtime_version_for_block(self, block_number: int) -> int:
        version = next((k for k, v in self.versions.items() if v['block_number_min'] <= block_number <= v['block_number_max']), None)
        return int(version) if version else None