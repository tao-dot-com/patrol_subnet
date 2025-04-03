from async_substrate_interface import AsyncSubstrateInterface

async def get_current_block(substrate: AsyncSubstrateInterface) -> int:
    
    current_block = await substrate.get_block()

    return current_block['header']['number']