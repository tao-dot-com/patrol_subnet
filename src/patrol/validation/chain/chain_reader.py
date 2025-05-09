import asyncio
from datetime import datetime, UTC
from collections import namedtuple
from typing import Iterable, Any

import bittensor.core.chain_data

from patrol.chain_data.substrate_client import SubstrateClient
from bittensor.core.async_subtensor import AsyncSubstrateInterface

from patrol.validation.chain import ChainEvent
from patrol.validation.chain.runtime_versions import RuntimeVersions

import logging

logger = logging.getLogger(__name__)

PreprocessedTuple = namedtuple("PreprocessedTuple", ["block_number", "block_hash", "event"])


class ChainReader:
    def __init__(self, substrate_client: SubstrateClient, runtime_versions: RuntimeVersions):
        self._substrate_client = substrate_client
        self._runtime_versions = runtime_versions

    async def _preprocess_system_events(self, runtime_version: int, block_number: int) -> PreprocessedTuple:
        _, block_hash = await self._get_block_hash(block_number, runtime_version)

        return PreprocessedTuple(block_number, block_hash, await self._substrate_client.query(
            "_preprocess",
            runtime_version,
            None,
            block_hash,
            module="System",
            storage_function="Events"
        ))

    async def find_block_events(self, runtime_version: int, block_numbers: list[int]) -> Iterable[Any]:

        logger.info("Querying blockchain for events in blocks %s to %s", block_numbers[0], block_numbers[-1])

        preprocessed_tasks = [self._preprocess_system_events(runtime_version, it) for it in block_numbers]
        preprocessed_events = await asyncio.gather(*preprocessed_tasks)

        block_numbers_by_hash = {it.block_hash: it.block_number for it in preprocessed_events}

        def make_payload(preprocessed: PreprocessedTuple):
            return AsyncSubstrateInterface.make_payload(
                preprocessed.block_hash,
                preprocessed.event.method,
                [preprocessed.event.params[0], preprocessed.block_hash]
            )

        rpc_request_payloads = [make_payload(it) for it in preprocessed_events]
        value_scale_type = preprocessed_events[0].event.value_scale_type
        storage_item = preprocessed_events[0].event.storage_item

        raw_events = await self._substrate_client.query(
                "_make_rpc_request",
                runtime_version,
                rpc_request_payloads,
                value_scale_type,
                storage_item
            )

        events = await self._chain_events_for(raw_events, block_numbers_by_hash)
        logger.info("Found %s events in blocks %s to %s", len(events), block_numbers[0], block_numbers[-1])
        return events

    async def get_current_block(self) -> int:
        current_block = await self._substrate_client.query("get_block", None)
        return current_block["header"]["number"]

    async def _get_block_hash(self, block_number: int, runtime_version: int) -> tuple[int, str]:
        return block_number, await self._substrate_client.query(
            "get_block_hash",
            runtime_version,
            block_number
        )

    async def _chain_events_for(self, raw_events: dict[str, list[tuple[dict]]], block_numbers: dict[str, int]):

        def transform(event_tuple: tuple):
            return [it['event'] for it in event_tuple]

        event_data = (((k, transform(v[0])) for k, v in raw_events.items()))

        chain_event_builders = []

        for block_hash, events in event_data:
            block_number = block_numbers[block_hash]
            for event in events:
                chain_event_builders.append(self.make_chain_event_for(block_number, event))

        chain_events = await asyncio.gather(*chain_event_builders)
        return list(filter(lambda it: it is not None, chain_events))

    async def make_chain_event_for(self, block_number: int, event: dict):
        if "SubtensorModule" in event:
            if "NeuronRegistered" in event["SubtensorModule"][0]:
                return await self._make_neuron_registered_event(event, block_number)
            elif "ColdkeySwapScheduled" in event["SubtensorModule"][0]:
                return await self._make_coldkey_swap_scheduled_event(event, block_number)
            else:
                return None
        else:
            return None

    async def _make_neuron_registered_event(self, event, block_number: int):
        neuron_registered = event["SubtensorModule"][0]["NeuronRegistered"]
        hotkey = bittensor.core.chain_data.decode_account_id(neuron_registered[2])
        coldkey = await self.get_hotkey_owner(hotkey, block_number)

        return ChainEvent(
            created_at=datetime.now(UTC),
            edge_category="SubtensorModule",
            edge_type="NeuronRegistered",
            block_number=block_number,
            coldkey_destination=coldkey,
        )

    @staticmethod
    async def _make_coldkey_swap_scheduled_event(event, block_number: int):
        swap = event["SubtensorModule"][0]["ColdkeySwapScheduled"]
        execution_block = swap['execution_block']
        old_coldkey = bittensor.core.chain_data.decode_account_id(swap['old_coldkey'])
        new_coldkey = bittensor.core.chain_data.decode_account_id(swap['new_coldkey'])

        return ChainEvent(
            created_at=datetime.now(UTC),
            edge_category="SubtensorModule",
            edge_type="ColdkeySwapScheduled",
            block_number=block_number,
            coldkey_source=old_coldkey,
            coldkey_destination=new_coldkey,
            #delegate_hotkey_source=
        )

    async def get_hotkey_owner(self, hotkey: str, block_number: int = None) -> str:
        """
        Helper to fetch owner at exactly `block_number`.
        """
        if block_number is None:
            block_number = self.get_current_block()

        runtime_version = self._runtime_versions.runtime_version_for_block(block_number)
        _, block_hash = await self._get_block_hash(block_number, runtime_version)

        return await self._substrate_client.query(
            "query",
            runtime_version,
            "SubtensorModule",
            "Owner",
            [hotkey],
            block_hash=block_hash
        )