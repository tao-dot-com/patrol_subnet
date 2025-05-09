import asyncio
from collections import namedtuple
from datetime import datetime, UTC
import itertools
import uuid
from uuid import UUID

from patrol.protocol import HotkeyOwnershipSynapse, Edge
from patrol.validation.chain.chain_reader import ChainReader
from patrol.validation.hotkey_ownership.hotkey_ownership_miner_client import HotkeyOwnershipMinerClient, \
    MinerTaskException

import networkx as nx

from patrol.validation.hotkey_ownership.hotkey_ownership_scoring import HotkeyOwnershipScoring
from patrol.validation.scoring import MinerScore, MinerScoreRepository

class ValidationException(Exception):
    pass

class HotkeyOwnershipValidator:

    def __init__(self, chain_reader: ChainReader):
        self.chain_reader = chain_reader

    async def validate(self, response: HotkeyOwnershipSynapse, hotkey: str):
        self._validate_graph(response)
        await self._validate_edges(hotkey, response.subgraph_output.edges)

    def _validate_graph(self, synapse: HotkeyOwnershipSynapse):
        HotkeyOwnershipSynapse.model_validate(synapse, strict=True)

        subgraph = synapse.subgraph_output
        if not subgraph:
            raise ValidationException("Missing graph")
        if not subgraph.nodes:
            raise ValidationException("Zero nodes")

        graph = nx.MultiDiGraph()
        for node in subgraph.nodes:
            if node.id in graph:
                raise ValidationException(f"Duplicate node [{node.id}]")
            graph.add_node(node.id)

        for edge in subgraph.edges:
            if edge.coldkey_source not in graph.nodes:
                raise ValidationException(f'Edge source [{edge.coldkey_source}] is not a node')
            if edge.coldkey_destination not in graph.nodes:
                raise ValidationException(f"Edge destination [{edge.coldkey_destination}] is not a node")

            if graph.has_edge(edge.coldkey_source, edge.coldkey_destination, key=edge.evidence.effective_block_number):
                raise ValidationException(f"Duplicate edge (from={edge.coldkey_source}, to={edge.coldkey_destination}, block={edge.evidence.effective_block_number})")

            graph.add_edge(edge.coldkey_source, edge.coldkey_destination, key=edge.evidence.effective_block_number)

        if not nx.is_weakly_connected(graph):
            raise ValidationException("Graph is not fully connected")


    async def _validate_edges(self, hotkey: str, edges: list[Edge]):

        async def chain_validation(block_number: int, expected_owning_coldkey: str):
            actual_owner = await self.chain_reader.get_hotkey_owner(hotkey, block_number)
            if actual_owner != expected_owning_coldkey:
                raise ValidationException(f"Expected hotkey_owner [{expected_owning_coldkey}]; actual [{actual_owner}] for block [{block_number}]")

        evidences = itertools.chain.from_iterable([
            chain_validation(e.evidence.effective_block_number - 1, e.coldkey_source),
            chain_validation(e.evidence.effective_block_number + 1, e.coldkey_destination),
        ] for e in edges)

        await asyncio.gather(*evidences)


Miner = namedtuple("Miner", ["axon_info", "uid"])

class HotkeyOwnershipChallenge:

    def __init__(
            self, miner_client: HotkeyOwnershipMinerClient,
            scoring: HotkeyOwnershipScoring,
            validator: HotkeyOwnershipValidator,
            score_repository: MinerScoreRepository
    ):
        self.miner_client = miner_client
        self.scoring = scoring
        self.validator = validator
        self.score_repository = score_repository
        self.moving_average_denominator = 20

    async def execute_challenge(self, miner: Miner, target_hotkey, batch_id: UUID):
        task_id = uuid.uuid4()
        synapse = HotkeyOwnershipSynapse(target_hotkey_ss58=target_hotkey)

        try:
            response, response_time_seconds = await self.miner_client.execute_task(miner.axon_info, synapse)

            try:
                await self.validator.validate(response, target_hotkey)
                score = await self._calculate_score(batch_id, task_id, miner, response_time_seconds)
            except ValidationException as ex:
                error = str(ex)
                score = await self._calculate_zero_score(batch_id, task_id, miner, response_time_seconds, error)

        except MinerTaskException as ex:
            error = str(ex)
            score = await self._calculate_zero_score(batch_id, task_id, miner, 0, error)

        await self.score_repository.add(score)
        return task_id


    async def _moving_average(self, overall_score, miner: Miner):
        previous_scores =  await self.score_repository.find_latest_overall_scores((miner.axon_info.hotkey, miner.uid), self.moving_average_denominator - 1)
        return (sum(previous_scores) + overall_score) / self.moving_average_denominator

    async def _calculate_zero_score(self, batch_id: uuid.UUID, task_id: UUID, miner: Miner, response_time: float, error_message: str) -> MinerScore:
        moving_average = await self._moving_average(0, miner)
        return MinerScore(
            id=task_id, batch_id=batch_id, created_at=datetime.now(UTC),
            uid=miner.uid,
            hotkey=miner.axon_info.hotkey,
            coldkey=miner.axon_info.coldkey,
            overall_score=0.0,
            responsiveness_score=0,
            overall_score_moving_average=moving_average,
            response_time_seconds=response_time,
            volume=0,
            novelty_score=0,
            volume_score=0,
            validation_passed=False,
            error_message=error_message
        )

    async def _calculate_score(self, batch_id: UUID, task_id: UUID, miner: Miner, response_time: float) -> MinerScore:
        score = self.scoring.score(True, response_time)
        moving_average = await self._moving_average(score.overall, miner)
        return MinerScore(
            id=task_id, batch_id=batch_id, created_at=datetime.now(UTC),
            uid=miner.uid,
            hotkey=miner.axon_info.hotkey,
            coldkey=miner.axon_info.coldkey,
            overall_score=score.overall,
            responsiveness_score=score.response_time,
            overall_score_moving_average=moving_average,
            response_time_seconds=response_time,
            volume=0,
            novelty_score=0,
            volume_score=1.0,
            validation_passed=True,
        )

