from abc import ABC, abstractmethod


class BlockCheckpoint(ABC):

    @abstractmethod
    async def find_latest_processed_block(self, event_type) -> int:
        pass

    @abstractmethod
    async def find_missing_blocks(self, event_type):
        pass

    @abstractmethod
    async def set_checkpoint(self, event_type, block_number: int):
        pass