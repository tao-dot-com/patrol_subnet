### Hotkey ownership task

This task challenges miners to discover changes in the ownership of a hotkey.

1. The validator selects a set of random hotkeys, and sends one to each miner as a **target_hotkey**
2. The miner finds the coldkeys that have owned the target_hotkey and responds with a graph where the nodes are coldkeys and the edges contain the block number where the hotkey ownership change became effective.

Example Request:
```json
{
     "target_hotkey_ss58": "5E4JBpbx3p3BchvJF2RQ4CLqAF5ECZNYuPbCg8u9T8Y5jtgi"
}
```
Example Response:

```json
{
     "subgraph_output": {
          "nodes": [
               { "id": "5CMEwRYLefRmtJg8zzRyJtcXrQqmspr9B1r1nKySDReA37Z1", "type": "wallet", "origin": "bittensor" },
               { "id": "5G694c15wAu1LKb9rpSQqJjpBfg4K1oiBxEm5QSVdVZAfp9f", "type": "wallet", "origin": "bittensor" }
          ],
          "edges": [
               { 
                    "category": "coldkey_swap",
                    "type": "hotkey_ownership",
                    "coldkey_source": "5CMEwRYLefRmtJg8zzRyJtcXrQqmspr9B1r1nKySDReA37Z1",
                    "coldkey_destination": "5G694c15wAu1LKb9rpSQqJjpBfg4K1oiBxEm5QSVdVZAfp9f",
                    "evidence": {
                         "effective_block_number": 5070010 
                    }
               }
          ]
     }
}
```
3. The validator ensures that the response is syntactically correct, and that the asserted changes of ownership(s) 
4. are genuine.
4. The validator scores the response according to the incentive mechanism.

## Incentive mechanism

This task implements a simple incentive mechanism designed to reward nodes based on the accuracy and efficiency 
of their payload submissions.

Below shows the pass/fail impact of response validation and the contribution of the responsiveness score 
incentivizing fast responses from nodes. It is computed using an inverse-scaling function that prioritizes lower 
latency:

$$`s_{response} = \frac{t_{half}}{t + t_{half}}`$$
where $`t`$ is the recorded response time, $`t_{half}`$ is a constant specifying the time at which the score will 
be 0.5. It is set to 2.0.

Overall score is calculated as follows:
$$`s_{overall} = \frac{1 + s_{response} w_{response}}{w_{validity} + w_{response}}`$$

where $`s_{response}`$ is the response time score,
$`w_{response}`$ (50) and $`w_{validity}`$ (50) are the relative weightings given 
to responsive score and validity score respectively.  

```python
def score(self, is_valid: bool, response_time_seconds: float):
        if not is_valid:
            return HotkeyOwnershipScore(0, 0, 0)

        validity_score = 1

        response_time_score = self._response_time_half_score/(response_time_seconds + self._response_time_half_score)

        overall_score = sum([
            validity_score * self._validity_weight,
            response_time_score * self._response_weight
        ]) / sum([self._validity_weight, self._response_weight])

        return HotkeyOwnershipScore(validity_score, response_time_score, overall_score)
```

Where response_time_half_score is the response time that yields a score of exactly 0.5 (for this challenge 
it is set to 2 seconds).

**Intuition**
- Invalid responses score 0.
- Instant responses get the maximum score (1.0)
- Responses around the target time get a moderate score (~0.5)
- Slower responses are still scored, but with diminishing value

This rewards both speed and reliability while allowing some flexibility for slower miners.

This task contributes 60% of the weights.
