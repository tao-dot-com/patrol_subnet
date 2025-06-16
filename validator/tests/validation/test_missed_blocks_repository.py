import pytest
import asyncio
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select

from patrol.validation.persistence import Base
from patrol.validation.persistence.missed_blocks_repository import MissedBlocksRepository, MissedBlock


@pytest.fixture
async def memory_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Close engine
    await engine.dispose()


@pytest.fixture
async def missed_blocks_repository(memory_db_engine):
    """Create a MissedBlocksRepository with an in-memory database."""
    repository = MissedBlocksRepository(memory_db_engine)
    yield repository


@pytest.mark.asyncio
async def test_add_missed_blocks(missed_blocks_repository):
    """Test adding missed blocks to the repository."""
    block_numbers = [4267256, 4267356, 4267456]
    await missed_blocks_repository.add_missed_blocks(block_numbers, "Test error message")
    
    # Verify the blocks were added using a direct query
    async with missed_blocks_repository.LocalAsyncSession() as session:
        query = select(MissedBlock)
        result = await session.execute(query)
        blocks = result.scalars().all()
        
        # Check that we got all blocks
        assert len(blocks) == 3
        block_nums = [block.block_number for block in blocks]
        assert sorted(block_nums) == sorted(block_numbers)
        
        # Verify they all have the same error message
        for block in blocks:
            assert block.error_message == "Test error message"
            assert block.created_at is not None


@pytest.mark.asyncio
async def test_get_all_missed_blocks(missed_blocks_repository):
    """Test retrieving all missed blocks."""
    # Initially there should be no missed blocks
    blocks = await missed_blocks_repository.get_all_missed_blocks()
    assert len(blocks) == 0
    
    # Add some blocks
    await missed_blocks_repository.add_missed_blocks([4267256, 4267356, 4267456])
    
    # Now there should be 3 blocks
    blocks = await missed_blocks_repository.get_all_missed_blocks()
    assert len(blocks) == 3
    assert 4267256 in blocks
    assert 4267356 in blocks
    assert 4267456 in blocks


@pytest.mark.asyncio
async def test_get_all_missed_blocks_handles_duplicates(missed_blocks_repository):
    """Test that get_all_missed_blocks returns unique block numbers even if there are duplicates in the table."""
    # Add the same block number multiple times (as might happen in production)
    await missed_blocks_repository.add_missed_blocks([4267256], "First error")
    await missed_blocks_repository.add_missed_blocks([4267256], "Second error")
    await missed_blocks_repository.add_missed_blocks([4267356], "Another error")
    
    # There should still be only 2 unique block numbers
    blocks = await missed_blocks_repository.get_all_missed_blocks()
    assert len(blocks) == 2
    assert 4267256 in blocks
    assert 4267356 in blocks


@pytest.mark.asyncio
async def test_remove_blocks(missed_blocks_repository):
    """Test removing blocks from the repository."""
    # Add some blocks
    await missed_blocks_repository.add_missed_blocks([4267256, 4267356, 4267456, 4267556])
    
    # Remove some of them
    await missed_blocks_repository.remove_blocks([4267256, 4267456])
    
    # Verify only the non-removed blocks remain
    blocks = await missed_blocks_repository.get_all_missed_blocks()
    assert len(blocks) == 2
    assert 4267356 in blocks
    assert 4267556 in blocks
    assert 4267256 not in blocks
    assert 4267456 not in blocks
