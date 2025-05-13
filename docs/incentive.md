## Incentive Mechanism Scoring Overview

## Task 1:

This task implements a modular incentive mechanism designed to reward nodes based on the quality, quantity, and efficiency of their payload submissions. The scoring system currently includes two active components — Volume and Responsiveness.

Scoring contributions: 
- Volume - 90%
- Responsiveness - 10%

Along with the scoring mechanism there are a number of pass/fail validation checks, which if failed, result in a score of zero. The code for these checks are [here](src/patrol/validation/graph_validation/bittensor_validation_mechanism.py).

⸻

### Volume Score

The volume score measures how much data a node contributes in each payload. It uses a sigmoid function to smoothly reward higher-volume submissions, without hard thresholds.

```python
    def calculate_volume_score(self, total_items: int) -> float:
        score = 1 / (1 + math.exp(-Constants.STEEPNESS * (total_items - Constants.INFLECTION_POINT)))
        return score
```

- total_items = len(nodes) + len(edges)
- INFLECTION_POINT is currently set to 1000
- STEEPNESS controls the steepness of the sigmoid curve (e.g., 0.005)

**Intuition**
- Small payloads get a low score
- Payloads near 1000 items (nodes + edges) receive a baseline score of ~0.5
- Larger payloads approach a perfect score of 1.0 asymptotically

This ensures smooth scaling and avoids harsh penalties for slightly smaller submissions, while still rewarding contributors who go above and beyond.

### Responsiveness Score

The responsiveness score incentivizes fast responses from nodes. It is computed using an inverse-scaling function that prioritizes lower latency:

```python
def calculate_responsiveness_score(self, response_time: float) -> float:
    return Constants.RESPONSE_TIME_HALF_SCORE / (response_time + Constants.RESPONSE_TIME_HALF_SCORE)
```

Where RESPONSE_TIME_HALF_SCORE is the response time that yields a score of exactly 0.5 (e.g., 10 seconds).

**Intuition**
- Instant responses get the maximum score (1.0)
- Responses around the target time get a moderate score (~0.5)
- Slower responses are still scored, but with diminishing value

This rewards both speed and reliability while allowing some flexibility for slower nodes.

⸻

### Overall Scoring Design

Each component (Volume, Responsiveness) is normalized between 0.0 and 1.0, and can be combined via weighted averaging or other aggregation logic to produce a final incentive score per payload.

[View the full score calculation here](../src/patrol/validation/miner_scoring.py).

⸻

## Task 2:

This task implements a simple incentive mechanism designed to reward nodes based on the accuracy and efficiency of their payload submissions.

Below shows the pass/fail impact of response validation and the contribution of the responsiveness score incentivizing fast responses from nodes. It is computed using an inverse-scaling function that prioritizes lower latency:

```python
def score(self, is_valid: bool, response_time_seconds: float):
        if not is_valid:
            return HotkeyOwnershipScore(0, 0, 0)

        validity_score = 1

        response_time_score = self._response_time_half_score/(response_time_seconds + self._response_time_half_score)

        overall_score = sum([
            validity_score * self._validity_weight,
            response_time_score * self._validity_weight
        ]) / sum([self._validity_weight, self._validity_weight])

        return HotkeyOwnershipScore(validity_score, response_time_score, overall_score)
```

Where response_time_half_score is the response time that yields a score of exactly 0.5 (for this challenge it is set to 2 seconds).

**Intuition**
- Invalid responses score 0.
- Instant responses get the maximum score (1.0)
- Responses around the target time get a moderate score (~0.5)
- Slower responses are still scored, but with diminishing value

This rewards both speed and reliability while allowing some flexibility for slower nodes.
