from unittest.mock import AsyncMock

from async_substrate_interface import AsyncSubstrateInterface

from patrol.validation.chain.chain_utils import ChainUtils


async def test_get_current_block():

    raw_block = {
        'header': {
            'number': 5649525
        }
    }

    mock_substrate = AsyncMock(AsyncSubstrateInterface)
    mock_substrate.get_block = AsyncMock(return_value=raw_block)

    chain_utils = ChainUtils(mock_substrate)
    current_block = await chain_utils.get_current_block()
    assert current_block == 5649525

