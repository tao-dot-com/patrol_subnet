from typing import Dict, Any, List, Tuple
import bittensor as bt
import math

from patrol.constants import Constants

class MinerScoring:
    def __init__(self):
        self.importance = {
            # 'novelty': X, This will be implemented soon
            'volume': 0.5,
            'responsiveness': 0.5,
        }
        
    def calculate_novelty_score(self, payload: Dict[str, Any]) -> float:
        """
        Calculate how novel/unique the submitted data is compared to historical data.
        Returns score between 0-1.
        """
        # TODO: Implement comparison with historical submissions
        # For now return placeholder score
        pass
          
    def calculate_volume_score(self, payload: Dict[str, Any]) -> float:
        """
        Calculate volume score based on amount of valid data submitted.
        Returns score between 0-1.
        """
        def dict_to_hashable(d: Dict[str, Any]) -> Tuple:
            """Convert a dictionary to a hashable tuple, handling nested dicts."""
            return tuple(sorted((k, dict_to_hashable(v) if isinstance(v, dict) else v) for k, v in d.items()))

        def get_unique_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            seen = set()
            return [
                d for d in items 
                if not (dict_to_hashable({k: v for k, v in d.items() if k not in ['block_number', 'timestamp']}) in seen or seen.add(dict_to_hashable({k: v for k, v in d.items() if k not in ['block_number', 'timestamp']})))
            ]

        unique_nodes = get_unique_items(payload['nodes'])
        unique_edges = get_unique_items(payload['edges'])

        # Count unique items
        total_unique_items = len(unique_nodes) + len(unique_edges)

        base_score = math.log(total_unique_items + 1) / math.log(101)  # +1 to avoid log(0), 101 for reference point
        return min(1.0, base_score)  # Cap at 100 unique items for max score
    
    def calculate_responsiveness_score(self, response_time: float) -> float:
        """
        Calculate responsiveness score based on response time.
        Returns score between 0-1.
        """

        response_time = min(response_time, Constants.MAX_RESPONSE_TIME)

        return 1.0 - (response_time / Constants.MAX_RESPONSE_TIME)

    def calculate_overall_scores(self, payload: Dict[str, Any], response_time: float) -> float:
        """
        Calculate total weighted Coverage score for the miner submission.
        Returns normalized Coverage score between 0-1.
        """

        # Just need to check this is how we respond? 
        if payload is None:
            return 0.0
    
        scores = {
            'volume': self.calculate_volume_score(payload),
            'responsiveness': self.calculate_responsiveness_score(response_time)
        }

        
        coverage_score = sum(scores[k] * self.importance[k] for k in scores)

        bt.logging.info(f"Total Coverage Score: {coverage_score}")
        return coverage_score
    
    def normalize_scores(self, scores: Dict[int, float]) -> List[float]:
        """
            Normalize a dictionary of miner Coverage scores to ensure fair comparison.
            Returns list of Coverage scores normalized between 0-1.
        """
        if not scores:
            return []
        
        min_score = min(scores.values())
        max_score = max(scores.values())
        
        if min_score == max_score:
            return [1.0] * len(scores)
        
        return {uid: round((score - min_score) / (max_score - min_score), 6) for uid, score in scores.items()}
