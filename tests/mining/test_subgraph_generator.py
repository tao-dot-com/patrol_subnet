import pytest
from unittest.mock import AsyncMock
from patrol.mining.subgraph_generator import SubgraphGenerator
from patrol.protocol import Node, Edge, GraphPayload, StakeEvidence, TransferEvidence

@pytest.mark.asyncio
async def test_generate_block_numbers():

    gen = SubgraphGenerator(event_fetcher=AsyncMock(), event_processor=AsyncMock(), max_future_events=10, max_past_events=10)
    result = await gen.generate_block_numbers(5000000, lower_block_limit=4990000, upper_block_limit=6000000)

    assert result[0] == 4999990
    assert result[-1] == 5000010

def test_generate_adjacency_graph():
    gen = SubgraphGenerator(event_fetcher=None, event_processor=None)
    sample_events = [
        {"coldkey_source": "A", "coldkey_destination": "B", "evidence": {"rao_amount": 100, "block_number": 1}},
        {"coldkey_source": "B", "coldkey_owner": "C", "evidence": {"rao_amount": 200, "block_number": 2}},
    ]
    graph = gen.generate_adjacency_graph_from_events(sample_events)
    assert set(graph.keys()) == {"A", "B", "C"}
    assert any(conn["neighbor"] == "B" for conn in graph["A"])

def test_generate_subgraph_from_adjacency_graph():
    gen = SubgraphGenerator(event_fetcher=None, event_processor=None)
    adjacency_graph = {
        "X": [{"neighbor": "Y", "event": {
            "coldkey_source": "X",
            "coldkey_destination": "Y",
            "category": "balance",
            "type": "transfer",
            "evidence": {"rao_amount": 10, "block_number": 1}
        }}],
        "Y": [{"neighbor": "Z", "event": {
            "coldkey_source": "Y",
            "coldkey_destination": "Z",
            "coldkey_owner": "X",
            "category": "staking",
            "type": "add",
            "evidence": {
                "rao_amount": 20,
                "block_number": 2,
                "delegate_hotkey_destination": "Z",
                "alpha_amount": 1,
                "destination_net_uid": 42
            }
        }}]
    }

    result = gen.generate_subgraph_from_adjacency_graph(adjacency_graph, target_address="X")
    assert isinstance(result, GraphPayload)
    assert len(result.nodes) == 3
    assert len(result.edges) == 2
    assert any(isinstance(e.evidence, TransferEvidence) for e in result.edges)
    assert any(isinstance(e.evidence, StakeEvidence) for e in result.edges)