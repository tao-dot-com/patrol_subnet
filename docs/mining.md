## Running a Miner

REQUIREMENTS:
- Ubuntu 22.04+
- Python 3.12+

HARDWARE REQUIREMENTS:
- 8gb Ram
- 2 vCPUs

### Getting Started

1. Register your miner using the command:
   - MAINNET UID: 81
   - TESTNET UID: 275
   ```sh
   btcli subnet register --netuid <UID> --wallet.name <YOUR_COLDKEY> --wallet.hotkey <YOUR_HOTKEY> --network <your_network (testnet or finney)>
   ```
   This will register your miner with the Patrol subnet.

2. Set up the PM2 process manager:
   ```sh
   apt install nodejs npm
   npm i -g pm2
   ```
   
3. Create a virtual environment and install prerequisite packages:
   ```sh
   git clone https://github.com/tao_dot_com/patrol_subnet
   cd patrol_subnet
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   pip install -e common/
   ```

4. Run the miner script to start mining data:
  - MAINNET UID: 81
  - TESTNET UID: 275
   
   ```sh
   pm2 start miner/src/patrol_mining/miner.py --interpreter python3 --name patrol-miner -- \
  --netuid <UID> \
  --wallet_path <your_wallet_path> \
  --coldkey <your_wallet_name> \
  --hotkey <your_wallet_hotkey_name> \
  --subtensor_address <network address for (test | finney | local)> \
  --archive_node_address <your archive node for data collection (always has to be mainnet)> \
  --external_ip <your_external_ip address> \
  --port <your_port | 8000> \
  --max_future_events <number of event blocks to collect into the future> \
  --max_past_events <number of event blocks to collect into the past> \
  --event_batch_size <number of event blocks to query at the same time>
   ```
   This script will:
   - Initialize the miner with the specified wallet name and network
   - Start the primary miner script that will process requests from the validators and submit responses for the tasks outlined below

> [!NOTE]
> If you are attempting to run a miner on testnet, you will need to change '--subtensor_address' to the testnet network, but '--archive_node_address' always needs to point toward an archive node synced for mainnet, as regardless of testnet/mainnet, the data collected is always live.

### Tasks

Miners should implement both of the following tasks:

- [Hotkey Ownership Task](hotkey_ownership.md)  
There are no standard hyperparamters for changing the performance of your miner on this task. You will likely find benefits from pursuing caching in some form.


- [Stake Prediction Task](stake_prediction.md)  
The reference miner will predict zero stake movement by default. It is completely up to miners to
optimize the prediction mechanism to improve accuracy.

### Optimising your miner

For both tasks, we strongly suggest setting up your own archive node, which will allow you to avoid any rate limits and/or competing for resources when querying the opentensor archive node. A guide to help you set up your own archive node can be found [here](https://docs.bittensor.com/subtensor-nodes/).

To aid with optimizing for both tasks, we have provided some local_dev resource, which allow you to test your miner offline (without the need for testnet). Please see [here](../src/miner/local_dev/local_development.md).

