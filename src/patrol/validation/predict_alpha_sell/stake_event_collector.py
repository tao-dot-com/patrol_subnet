from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.predict_alpha_sell import AlphaSellChallengeMiner, AlphaSellEventRepository

batch_size = 1000


class StakeEventCollector:
    def __init__(self, chain_reader: ChainReader, alpha_sell_event_repository: AlphaSellEventRepository):
        self.chain_reader = chain_reader
        self.alpha_sell_event_repository = alpha_sell_event_repository

    async def collect_events(self):
        previous_block = await self.chain_reader.get_current_block() - 1
        most_recent_block_collected = await self.alpha_sell_event_repository.find_most_recent_block_collected()
        if not most_recent_block_collected:
            most_recent_block_collected = previous_block - 7200

        blocks_to_collect = range(most_recent_block_collected, previous_block)

        def block_batches():
            for i in range(0, len(blocks_to_collect), batch_size):
                yield blocks_to_collect[i:i + batch_size]

        for batch in block_batches():
            events = await self.chain_reader.find_stake_events(batch)
            await self.alpha_sell_event_repository.add(events)


