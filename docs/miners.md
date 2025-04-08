## Running a Miner

REQUIREMENTS:
  Ubuntu 22.04+
  Python 3.10+

HARDWARE REQUIREMENTS:
    8gb Ram
    2 vCPUs

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
   
3. Create a virtual environtment and install prerequisite packages:
   ```sh
   git clone https://github.com/tao_dot_com/patrol_subnet
   cd Patrol
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

4. Run the miner script to start mining data:
  - MAINNET UID: 81
  - TESTNET UID: 275
   ```sh
   pm2 start neurons/miner.py --interpreter python3 --name patrol-miner -- --netuid <UID> --wallet_path <your_wallet_path> --coldkey <your_wallet_name>  --hotkey <your_wallet_hotkey_name> --archive_node_address <your_network (test | finney | local) archive node> --external_ip <your_external_ip address> --port <your_port | 8091> --max_future_events <number of event blocks to collect into the future> --max_past_events <number of event blocks to collect into the past> --event_batch_size <number of event blocks to query at the same time>
   ```
   This script will:
   - Initialize the miner with the specified wallet name and network
   - Start the primary miner script that will process requests from the validators and submit subgraphs gathered from the archive node


### Optimising your miner

> **Note:** You will at the very least need to optimize your miner's performance by adjusting the *max_future_events*, *max_past_events* and *event_batch_size* parameters.

As the subnet gets more competitive, you will need to enhance and optimise the miner code, so that it can fetch larger subgraphs in less time. 

To aid with this experimentation, we have provided some local_dev resource, which allow you to test your miner offline (without the need for testnet). Please see (./local_dev/local_development.md)
