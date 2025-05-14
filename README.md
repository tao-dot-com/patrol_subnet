<div align="center">
  <img src="assets/patrol-banner.png" alt="Patrol Banner" style="border-radius: 10px;">
</div>


## 🧠 A decentralized behavioral analysis and prediction engine.

Built to help $TAO investors take decisive action by connecting behavioral signals across the Bittensor network to likely future outcomes. Patrol aims to become the trust and predictive engine for decentralized networks — combining deep historical analysis with forward-looking insight to power smarter decisions across the ecosystem.

---

## 🔍 From Behavior to Insight

Patrol turns raw on-chain activity into forward-looking insight through a structured process we call the **Predictive Intelligence Loop** — a reusable pattern found across the Bittensor network.

1. **Observe Behavior**  
   Track wallet actions: emissions, transfers, staking, swaps, etc.

2. **Model Actors & Environments**  
   Identify patterns and personas (e.g. dumpers, holders, flip traders) and map how they shape subnet dynamics.

3. **Generate Predictions**  
   Forecast likely outcomes: outflows, instability, accumulation, or price impact.

Each layer sharpens the next. By connecting actions to intent and intent to environment, Patrol helps users understand not just what happened — but what's likely next.

---

## 🧪 Task Types

Patrol supports three categories of mining tasks — each offering a distinct lens on behavior and contributing to a fuller understanding of the network:

1. **Historical Pattern Analysis**  
   **Status:** Live  
   Miners identify and label behaviors that have already occurred — such as emission dumping, alpha hoarding, validator churn, or cold key swaps. These signatures help define the behavioral history of wallets and subnets.

2. **Predictive Forecasting**  
   **Status:** Launching Soon  
   Miners will analyze recent activity to forecast what might happen next — projecting sell pressure, anticipating post-ownership actions, or detecting early signs of rising risk.

3. **LLM-Based Chain Reasoning**  
   **Status:** Not Yet Available  
   Future tasks will leverage large language models to interpret patterns, answer open-ended questions, and generate human-readable explanations of complex behaviors.

Each task type builds on the last — from raw observation to interpretation to predictive insight.

## Accessing Patrol's Data
In the near future we plan to provide a Public API for developers interested in consuming the data collected by the Patrol subnet.

## How Patrol Works

### Validator selects target wallet to cover
The flow of the subnet begins with validators selecting target wallets to submit to miners.  These targets are randomly selected from the chain. The [validator](src/patrol/validation/validator.py) then sends a target to each [miner](src/patrol/mining/miner.py). 
[See full target selection code here](src/patrol/validation/target_generation.py)

### Miner builds subgraph for target wallet
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


### Validator verifies miner’s subgraph

Once miners submit their subgraphs, [Validators](src/patrol/validation/validator.py) will [verify](src/patrol/validation/graph_validation/bittensor_validation_mechanism.py) the data by checking the *evidence* against the *node* and *edge* data submitted by the miners. This validation is pass/fail, failing will result in a score of 0 for that submission. This verification process currently supports the following node and edges types:

Nodes:
- Wallet nodes: Contains wallet addresses and types.

Edges:
- Transaction edges: Direct token transfers between wallets
- Staking edges: Staking relationships between wallets

See [here](src/patrol/protocol.py) for more details on the supported node and edge types.

### Validator scores subgraph

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
[View detailed overview of incentive mechanism here](docs/incentive.md).

Ultimately, the mission for each miner is to achieve the highest coverage score by delivering data that is high quality, high quantity, and novel. By doing so, miners ensure that only top-tier data is presented to validators, fortifying a comprehensive and dynamic knowledge graph. This invaluable resource is pivotal for a wide array of security applications, driving the future of digital asset protection and intelligence.

 ## Documentation and Resources

<table style="border: none !important; width: 100% !important; border-collapse: collapse !important; margin: 0 auto !important;">
  <tbody>
    <tr>
      <td><b>Docs</b></td>
      <td><b>Resources</b></td>
    </tr>
    <tr style="vertical-align: top !important">
      <td>
        ⛏️ <a href="docs/mining.md">Mining Guide</a><br>
        🔧 <a href="docs/validating.md">Validator Guide</a><br>
        📈 <a href="docs/incentive.md">Incentive Mechanism</a><br>
      <td>
        <a href="https://docs.bittensor.com/learn/bittensor-building-blocks">🧠 Bittensor Introduction</a><br> 
      </td>
    </tr>
  </tbody>
</table>

   ## Coming Soon

   - Addition of parent-child relationships to supported edge types
   - Support for additional data sources
     - Ethereum chain
     - Solana chain
     - X (Twitter)
     - Reddit
     - Github repositories

   - Public API for querying the knowledge graph
   - Dashboard for tracking miner performance and metrics

## License
This repository is licensed under the MIT License.
```text
# The MIT License (MIT)
# Copyright © 2023 Tensora Holdings Limited

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
```
