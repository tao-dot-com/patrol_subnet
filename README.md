

<div align="center">
  <img src="assets/patrol-banner.png" alt="Patrol Banner" style="border-radius: 10px;">
</div>



## Great Security Starts With Great Coverage
Patrol's mission started after the Bittensor summer attacks where we saw $20M+ stolen from TAO holders, members of our Bittensor community.  

Our mission, simply put, is to secure crypto funds and provide all holders peace of mind, wherever they are.

Patrol is our first step in harnessing Bittensor to collect large volumes of live data which in later stages will be analyzed and used to prevent hacks. 


## Building a Decentralized Palantir
In Patrol, miners and validators work together to intelligently collect large volumes of data from various data sources. It lays the foundation for advanced security intelligence by creating a knowledge graph that maps relationships and behaviors, aiding in investigations, threat detection, and risk assessment.
 
The first data source we’re covering is in our own backyard: The Bittensor chain. But this is just the beginning as we plan to expand to many other chains as well as other types of data sources like social media, code repos, phishing websites, and more. Ultimately, our goal over time is to build a unified graph of relationships for every crypto wallet that shows all its relationships. 


## Who Needs Patrol?

One of the key lessons from the Bittensor summer attacks is that tracing footprints after the fact takes A LOT of time and is VERY costly. And when it comes to crypto theft investigation, time is of the essence. The longer it is from time of attack the less likely one is to recover funds.

The footprint graph that Patrol creates is a must-have for any security team, investigator and platform developing and solving crypto security.  

## Accessing Patrol's Data
Soon after Patrol launches we plan to provide a Public API for developers interested in consuming the data collected by the Patrol subnet. We expect this Public API to be available by the end of February.

## How Patrol Works

### Validator selects target wallet to cover
The flow of the subnet begins with validators selecting target wallets to submit to miners.  These targets are randomly selected from the chain and then ranked by balance. The [validator](neurons/validator.py) then sends a target to each miner(neurons/miner.py)
[See full target selection code here](src/patrol/validation/target_generation.py)

### Miner builds subgraph for target wallet
[Miners](neurons/miner.py) receive the target from the validator and begin their search for related data.  Miners construct a *subgraph* of relational data for the target, and follow the data trace to expand their subgraph to N degrees of separation from the original target. 

Example:
```python
  target = "5GWzwBegYVwZdRjQwaGAvktpGuYaeUYXnMaoaC5PPcqEBuW2"

  mining_processor = SubgraphProcessor(depth=3, max_nodes=10, max_edges=30, timeout=20)
  payload = await mining_processor.generate_subgraph(target)

  print(payload)
```
[See the full miner processing class here](src/patrol/mining/subgraph_generator.py).

The subgraph that miners submit is composed of:

- **Nodes**: Representing the entities in the subgraph (wallets, etc)
- **Edges**: Representing relationships between nodes like transactions, staking, and parent-child relationships
- **Evidence**: Supporting data to verify the nodes and edges

These subgraphs are then submitted to the validator for evaluation.


### Validator verifies miner’s subgraph

Once miners submit their subgraphs, [Validators](neurons/validator.py) will [verify](src/patrol/validation/graph_validation/bittensor_validation_mechanism.py) the data by checking the *evidence* against the *node* and *edge* data submitted by the miners.  This verification process currently supports the following node and edges types:

Nodes:
- Wallet nodes: Contains wallet addresses, balances, age, density metrics

Edges:
- Transaction edges: Direct token transfers between wallets
- Staking edges: Staking relationships between wallets
- Parent-child edges: Hierarchical relationships between wallets

See [here](src/patrol/protocol.py) for more details on the supported node and edge types.

### Validator scores subgraph

Once the data has been verified, validators will calculate a *Coverage score* for the miner based on the following criteria:
- **Accuracy** (pass/fail): Validation of node and edge data against the evidence
- **Connectedness** (pass/fail): Whether the miner's subgraph is fully connected
- **Volume** (50%): Amount of valid data submitted, with reasonable caps
- **Responsiveness** (50%): How quickly the miner can submit data

```python
   volume = len(payload.nodes) + len(payload.edges)
        volume_score = self.calculate_volume_score(payload)
        responsiveness_score = self.calculate_responsiveness_score(response_time)

        overall_score = sum([
            volume_score * self.importance["volume"],
            responsiveness_score * self.importance["responsiveness"]
        ])

```
[View th full coverage score calculation here](src/patrol/validation/miner_scoring.py).

Ultimately, the mission for each miner is to achieve the highest coverage score by delivering data that is high quality, high quantity, and novel. By doing so, miners ensure that only top-tier data is presented to validators, fortifying a comprehensive and dynamic knowledge graph. This invaluable resource is pivotal for a wide array of security applications, driving the future of digital asset protection and intelligence.

## Running a Miner
REQUIREMENTS:
  Ubuntu 22.04+
  Python 3.10+
  
To run a Patrol subnet miner, follow these steps:

1. Set up the required indexer infrastructure by running the command:
   ```sh
   python setup_miner.py
   ```
   This [script](setup_miner.py) will:
   - Install Docker if it is not already installed
   - Start the Docker daemon
   - Clone the indexer repository
   - Pull the necessary Python base image
   - Build and launch the indexer within a Docker container

> **Note:** You will need to run the indexer for a period of 26 HOURS to allow it to catch up to the current state PRIOR to starting your miner.

2. Register your miner using the command:
   - MAINNET UID: 81
   - TESTNET UID: 275
   ```sh
   btcli subnet register --netuid <UID> --wallet.name <YOUR_COLDKEY> --wallet.hotkey <YOUR_HOTKEY> --network <your_network (testnet or finney)>
   ```
   This will register your miner with the Patrol subnet.

4. Set up the PM2 process manager:
   ```sh
   apt install nodejs npm
   npm i -g pm2
   ```
   
5. Create a virtual environtment and install prerequisite packages:
   ```sh
   git clone https://github.com/tao_dot_com/patrol_subnet
   cd Patrol
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

3. Run the miner script to start mining data:
  - MAINNET UID: 81
  - TESTNET UID: 275
   ```sh
   pm2 start neurons/miner.py --interpreter python3 --name patrol-miner -- --netuid <UID> --wallet.path <your_wallet_path> --wallet.name <your_wallet_name>  --wallet.hotkey <your_wallet_hotkey_name> --subtensor.network <your_network (test | finney | local)> --axon.port <your_port | 8091>
   ```
   This script will:
   - Initialize the miner with the specified wallet name and network
   - Start the primary miner script that will process requests from the validators and submit subgraphs gathered from the indexer

> **Note:** You may need to optimize your miner's performance by adjusting the *depth* and *max_nodes* parameters in the MiningProcessor class initialization in the miner.py script. 

## Running a Validator
REQUIREMENTS:
  Ubuntu 22.04+
  Python 3.10+
  
To run a Patrol subnet validator, follow these steps:

Be sure to create wallet in advance, following instructions from https://docs.bittensor.com.

1. Register your validator with the Patrol subnet using the command:
   - MAINNET UID: 81
   - TESTNET UID: 275
   ```sh
   btcli subnet register --netuid <UID> --wallet.name <YOUR_COLDKEY> --wallet.hotkey <YOUR_HOTKEY> --network <your_network (testnet or finney)>
   ```

2. Set up the PM2 process manager:
   ```sh
   apt install nodejs npm
   npm i -g pm2
   ```
   
3. Create a virtual environtment and install prerequisite packages:
   ```sh
   git clone https://github.com/tao_dot_com/patrol_subnet
   cd Patrol
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

4. Run the validator script from the patrol directory:
   MAINNET UID: 81
   TESTNET UID: 275
   ```sh
   pm2 start neurons/validator.py --interpreter python3 --name patrol-validator -- --netuid <UID> --wallet.path <your_wallet_path> --wallet.name <your_wallet_name> --wallet.hotkey <your_wallet_hotkey_name> --subtensor.network <your_network (test | finney | local)>
   ```

   This script will:
   - Initialize the validator with the specified wallet name and network
   - Start the validator script that will process requests from the miners and submit subgraphs gathered from the indexer

   ## Coming Soon

   - Support for additional data sources
     - Ethereum chain
     - Solana chain
     - X (Twitter)
     - Reddit
     - Github repositories

   - Public API for querying the knowledge graph
   - Dashboard for tracking miner performance and metrics



## [Miners](./docs/miners.md)

## [Validators](./docs/validators.md)