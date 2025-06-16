# Coldkey search task

#### Validator selects target wallet to cover
The flow of the subnet begins with validators selecting target wallets to submit to miners.  These targets are randomly selected from the chain. The [validator](validator/src/patrol/validation/validator.py) then sends a target to each [miner](src/patrol/mining/miner.py).
[See full target selection code here](validator/src/patrol/validation/target_generation.py)

#### Miner builds subgraph for target wallet
[Miners](src/patrol/mining/miner.py) receive the target from the validator and begin their search for related data.  Miners construct a *subgraph* of relational data for the target, and follow the data trace to expand their subgraph to N degrees of separation from the original target.

Example:
```python
  target = "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2"
  target_block = 5100341

  subgraph_generator = SubgraphGenerator(event_fetcher=fetcher, event_processor=event_processor, max_future_events=50, max_past_events=50, batch_size=50)
  subgraph = await subgraph_generator.run(target, target_block)

  print(subgraph)
```
[See the full miner processing class here](src/patrol/mining/subgraph_generator.py).

The subgraph that miners submit is composed of:

- **Nodes**: Representing the entities in the subgraph (wallets, etc)
- **Edges**: Representing relationships between nodes like transactions and staking (exapnding to include parent-child relationships as part of the roadmap).
- **Evidence**: Supporting data to verify the nodes and edges

These subgraphs are then submitted to the validator for evaluation.


#### Validator verifies miner’s subgraph

Once miners submit their subgraphs, [Validators](validator/src/patrol/validation/validator.py) will [verify](validator/src/patrol/validation/graph_validation/bittensor_validation_mechanism.py) the data by checking the *evidence* against the *node* and *edge* data submitted by the miners. This validation is pass/fail, failing will result in a score of 0 for that submission. This verification process currently supports the following node and edges types:

Nodes:
- Wallet nodes: Contains wallet addresses and types.

Edges:
- Transaction edges: Direct token transfers between wallets
- Staking edges: Staking relationships between wallets

See [here](src/patrol/protocol.py) for more details on the supported node and edge types.

#### Validator scores subgraph

Once the data has been verified, validators will calculate a *score* for the miner based on the following criteria:
- **Volume** (90%): Amount of valid data submitted, with reasonable caps
- **Responsiveness** (10%): How quickly the miner can submit data
- **Novelty** (will be implemented soon) : How unique the data returned by the miner is.

```python
   volume = len(payload.nodes) + len(payload.edges)
        volume_score = self.calculate_volume_score(payload)
        responsiveness_score = self.calculate_responsiveness_score(response_time)

        overall_score = sum([
            volume_score * self.importance["volume"],
            responsiveness_score * self.importance["responsiveness"]
        ])

```

Ultimately, the mission for each miner is to achieve the highest coverage score by delivering data that is high quality, high quantity, and novel. By doing so, miners ensure that only top-tier data is presented to validators, fortifying a comprehensive and dynamic knowledge graph. This invaluable resource is pivotal for a wide array of security applications, driving the future of digital asset protection and intelligence.

## Incentive mechanism

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

[View the full score calculation here](../validator/src/patrol/validation/miner_scoring.py).

⸻