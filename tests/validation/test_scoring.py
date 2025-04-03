import pytest
import json
import os
import math
from typing import Dict, Any, List
import bittensor as bt
from patrol.constants import Constants
from patrol.validation.miner_scoring import MinerScoring 

# Fixtures
@pytest.fixture
def scoring():
    """Fixture to create a MinerScoring instance."""
    return MinerScoring()

@pytest.fixture
def sample_payload():
    """Fixture for a sample payload."""
    return {
        'nodes': [
            {'id': 'node1', 'type': 'wallet', 'origin': 'source1'},
            {'id': 'node2', 'type': 'wallet', 'origin': 'source2'}
        ],
        'edges': [
            {'type': 'transfer', 'source': 'node1', 'destination': 'node2', 'evidence': {'amount': 100, 'block_number': 123}}
        ]
    }

@pytest.fixture
def sample_validation_results():
    """Fixture for sample validation results."""
    return {
        'nodes': [True, True],
        'edges': [True],
        'is_connected': True
    }

@pytest.fixture(autouse=True)
def mock_constants(monkeypatch):
    """Fixture to mock Constants.MAX_RESPONSE_TIME."""
    monkeypatch.setattr(Constants, 'MAX_RESPONSE_TIME', 10)

# Tests
def test_init(scoring):
    """Test initialization of MinerScoring."""
    assert scoring.importance['novelty'] == 0.1
    assert scoring.importance['accuracy'] == 0.3
    assert scoring.importance['volume'] == 0.3
    assert scoring.importance['responsiveness'] == 0.2
    assert scoring.importance['is_connected'] == 0.1
    assert sum(scoring.importance.values()) == 1.0
    assert scoring.historical_data == []
    assert scoring.cached_scores is None
    assert scoring.moving_avg_scores == []

def test_calculate_novelty_score(scoring, sample_payload):
    """Test novelty score calculation (placeholder)."""
    score = scoring.calculate_novelty_score(sample_payload)
    assert score == 1.0
    assert 0 <= score <= 1.0

@pytest.mark.parametrize("validation_results, expected", [
    ({'nodes': [True, True], 'edges': [True]}, 1.0),  # All valid
    ({'nodes': [True, False], 'edges': [True]}, 2/3),  # Mixed
    ({'nodes': [False], 'edges': [False]}, 0.0),      # All invalid
    ({'nodes': [], 'edges': []}, 0.0),                # Empty
])
def test_calculate_accuracy_score(scoring, validation_results, expected):
    """Test accuracy score calculation."""
    score = scoring.calculate_accuracy_score(validation_results)
    assert pytest.approx(score, abs=1e-5) == expected

@pytest.mark.parametrize("validation_results, expected", [
    ({'is_connected': True}, 1.0),
    ({'is_connected': False}, 0.0),
])
def test_calculate_is_connected_score(scoring, validation_results, expected):
    """Test is_connected score calculation."""
    score = scoring.calculate_is_connected_score(validation_results)
    assert score == expected

@pytest.mark.parametrize("payload, expected", [
    ({'nodes': [{'id': 'n1', 'type': 'wallet', 'origin': 's1'},
                {'id': 'n2', 'type': 'wallet', 'origin': 's2'}],
      'edges': [{'type': 'transfer', 'source': 'n1', 'destination': 'n2', 'evidence': {'amount': 100, 'block_number': 123}}]},
     math.log(3 + 1) / math.log(101)),  # 2 unique nodes, 1 edge
    ({'nodes': [{'id': 'n1', 'type': 'wallet', 'origin': 's1'}] * 2, 'edges': []},
     math.log(1 + 1) / math.log(101)),  # Duplicate nodes
    ({'nodes': [], 'edges': []}, 0.0),  # Empty
    ({'nodes': [{'id': f'n{i}', 'type': 'wallet', 'origin': 's'} for i in range(100)], 'edges': []},
     1.0),  # Large volume capped
])
def test_calculate_volume_score(scoring, payload, expected):
    """Test volume score calculation."""
    score = scoring.calculate_volume_score(payload)
    assert pytest.approx(score, abs=1e-2) == expected

@pytest.mark.parametrize("response_time, expected", [
    (0.0, 1.0),           # Instant
    (5.0, 0.5),           # Half max
    (10.0, 0.0),          # Max time
    (20.0, 0.0),          # Beyond max (capped)
])
def test_calculate_responsiveness_score(scoring, response_time, expected):
    """Test responsiveness score calculation."""
    score = scoring.calculate_responsiveness_score(response_time)
    assert score == expected

def test_calculate_coverage_score(scoring, sample_payload, sample_validation_results):
    """Test total coverage score calculation."""
    response_time = 2.0  # 80% responsiveness
    score = scoring.calculate_coverage_score(sample_payload, sample_validation_results, response_time)
    
    expected_scores = {
        'novelty': 1.0,
        'accuracy': 1.0,
        'volume': math.log(3 + 1) / math.log(101),
        'responsiveness': 1.0 - (2.0 / Constants.MAX_RESPONSE_TIME),
        'is_connected': 1.0
    }
    expected = sum(expected_scores[k] * scoring.importance[k] for k in expected_scores)
    assert pytest.approx(score, abs=1e-5) == expected

    # Null payload
    score = scoring.calculate_coverage_score(None, sample_validation_results, response_time)
    assert score == 0.0

@pytest.mark.parametrize("scores, expected", [
    ([0.2, 0.5, 0.8], [0.0, 0.5, 1.0]),  # Normal range
    ([], []),                             # Empty
    ([0.5, 0.5, 0.5], [1.0, 1.0, 1.0]), # All same
])
def test_normalize_scores(scoring, scores, expected):
    """Test score normalization."""
    normalized = scoring.normalize_scores(scores)
    assert normalized == expected

def test_cache_scores(mocker, scoring):
    """Test caching scores."""
    mocker.patch('os.path.exists', return_value=False)
    mocker.patch('os.makedirs')
    mocker.patch('fcntl.flock')

    # Custom mock to aggregate writes and handle truncate
    written_data = []
    def mock_write(data):
        written_data.append(data)
        return len(data)
    def mock_truncate():
        written_data.clear()  # Simulate file truncation
        return 0

    mock_file = mocker.mock_open(read_data='{}')
    mock_file().write.side_effect = mock_write
    mock_file().truncate.side_effect = mock_truncate
    mocker.patch('builtins.open', mock_file)

    MinerScoring.cache_scores(1, 0.75)

    # Combine writes after truncation
    full_json = ''.join(written_data)
    written_data_dict = json.loads(full_json)
    assert written_data_dict['1']['score'] == 0.75
    assert written_data_dict['1']['submissions'] == 1

def test_load_cached_score(mocker, scoring):
    """Test loading cached score."""
    mock_data = {'1': {'score': 0.75, 'submissions': 1}}
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(mock_data)))
    mocker.patch('fcntl.flock')
    
    result = MinerScoring.load_cached_score(1)
    assert result == {'score': 0.75, 'submissions': 1}

    # Non-existent UID
    result = MinerScoring.load_cached_score(2)
    assert result is None

    # File error
    mocker.patch('builtins.open', side_effect=FileNotFoundError)
    result = MinerScoring.load_cached_score(1)
    assert result is None

def test_load_all_cached_scores(mocker, scoring):
    """Test loading all cached scores."""
    mock_data = {
        '1': {'score': 0.75, 'submissions': 1},
        '2': {'score': 0.5, 'submissions': 2}
    }
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(mock_data)))
    mocker.patch('fcntl.flock')
    
    result = MinerScoring.load_all_cached_scores()
    assert result == mock_data

    # Empty file
    mocker.patch('builtins.open', side_effect=FileNotFoundError)
    result = MinerScoring.load_all_cached_scores()
    assert result == {}

if __name__ == '__main__':
    pytest.main([__file__])