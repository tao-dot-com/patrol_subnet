import time
import asyncio
import argparse
import traceback

import bittensor as bt
from bittensor.utils.networking import get_external_ip
from typing import Tuple
import logging
import argparse

from patrol.protocol import PatrolSynapse, MinerPingSynapse
from patrol.chain_data.event_fetcher import EventFetcher
from patrol.chain_data.coldkey_finder import ColdkeyFinder
from patrol.mining.subgraph_generator import SubgraphGenerator
from patrol.constants import Constants

class Miner:
    def __init__(self, dev_flag: bool, wallet_path: str, coldkey: str, hotkey: str, port: int, external_ip: str, netuid: int, subtensor_network: str, subgraph_generator: SubgraphGenerator):
        self.dev_flag = dev_flag
        self.wallet_path = wallet_path
        self.coldkey = coldkey
        self.hotkey = hotkey
        self.port = port
        self.external_ip = external_ip
        self.netuid = netuid
        self.network = subtensor_network
        self.subgraph_generator = subgraph_generator
        self.setup_logging()
        self.setup_bittensor_objects()

    def setup_logging(self):
        # Activate Bittensor's logging with the set configurations.
        bt.logging(
            debug=False,
            trace=False,
            info=True,
            record_log=False,
            logging_dir="~/.bittensor/miners"
        )
        bt.logging.info(f"Running miner for subnet: {self.netuid} on network: {self.network}.")

        # Disable all other loggers
        bt.logging.disable_third_party_loggers()
        
        # Set uvicorn access log format to empty
        logging.getLogger("uvicorn.access").handlers = []
        
        # Disable specific loggers completely
        for logger_name in [
            'uvicorn',
            'uvicorn.error',
            'uvicorn.access',
            'uvicorn.asgi',
            'uvicorn.protocols',
            'uvicorn.protocols.http',
            'uvicorn.protocols.websockets',
            'uvicorn.protocols.http.auto',
            'uvicorn.protocols.http.h11',
            'uvicorn.protocols.http.httptools',
            'uvicorn.lifespan',
            'uvicorn.lifespan.on',
            'uvicorn.lifespan.off',
            'asgi',
            'fastapi',
            'fastapi.error',
            'starlette',
            'starlette.access',
            'starlette.error',
            'multipart',
            'charset_normalizer',
            'httpx',
            'httpcore',
            'httptools',
            'websockets'
        ]:
            logger = logging.getLogger(logger_name)
            logger.disabled = True
            logger.handlers = []  # Remove any existing handlers
            logger.propagate = False
        
        class DebugHandler(logging.Handler):
            def emit(self, record):
                if 'HTTP/1.1" 200 OK' in record.getMessage():
                    print(f"\nLogger producing HTTP logs: {record.name}\n")
                
        logging.getLogger().addHandler(DebugHandler())
                    
    def setup_bittensor_objects(self):
        # Initialize Bittensor miner objects
        bt.logging.info("Setting up Bittensor objects.")

        if self.external_ip is None:
            if self.dev_flag:
                self.external_ip = "0.0.0.0"    
            else:
                self.external_ip = get_external_ip()


        self.wallet = bt.wallet(self.coldkey, self.hotkey, path=self.wallet_path)
        self.wallet.create_if_non_existent(False, False)
        bt.logging.info(f"Wallet: {self.wallet}")

        if not self.dev_flag:

            # Initialize subtensor.
            self.subtensor = bt.subtensor(network=self.network)
            bt.logging.info(f"Subtensor: {self.subtensor}")

            # Initialize metagraph.
            self.metagraph = self.subtensor.metagraph(self.netuid)
            bt.logging.info(f"Metagraph: {self.metagraph}")

            if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
                bt.logging.error(f"\nYour miner: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again.")
                exit()
            else:
                # Each miner gets a unique identity (UID) in the network.
                self.my_subnet_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
                bt.logging.info(f"Running miner on uid: {self.my_subnet_uid}")

    def blacklist_fn(self, synapse: PatrolSynapse) -> Tuple[bool, str]:
        # Ignore requests from unrecognized entities.
        if not self.dev_flag and synapse.dendrite.hotkey not in self.metagraph.hotkeys:
            bt.logging.warning(f'Blacklisting unrecognized hotkey {synapse.dendrite.hotkey}')
            return True, "Unrecognized hotkey"

        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)

        if not self.metagraph.validator_permit[uid] or self.metagraph.S[uid] < 30000:
            bt.logging.warning(
                f"Blacklisting a request from non-validator hotkey {synapse.dendrite.hotkey}"
            )
            return True, "Non-validator hotkey"
        
        bt.logging.trace(f'Not blacklisting recognized hotkey {synapse.dendrite.hotkey}')
        return False, None

    async def forward(self, synapse: PatrolSynapse) -> PatrolSynapse:
        """
        This function is called when a validator requests a subgraph from the miner.
        It generates a subgraph for the given target and returns it.
        """
        bt.logging.info(f"Received request: {synapse.target}")
        start_time = time.time()
        synapse.subgraph_output = await self.subgraph_generator.run(synapse.target, synapse.target_block_number)

        volume = len(synapse.subgraph_output.nodes) + len(synapse.subgraph_output.edges)

        bt.logging.info(f"Finished: {time.time() - start_time} with volume: {volume}")
        return synapse

    def forward_ping(self, synapse: MinerPingSynapse) -> MinerPingSynapse:
        """
        This function is called when a validator pings the miner to check if it is available.
        It returns a MinerPingSynapse object with is_available set to True.
        """
        bt.logging.info("Received ping from validator. Telling validator that I am available.")
        return MinerPingSynapse(is_available=True)

    def setup_axon(self):
        # Build and link miner functions to the axon.
        self.axon = bt.axon(
            wallet=self.wallet, 
            port=self.port, 
            external_ip=self.external_ip
            )

        # Attach functions to the axon.
        bt.logging.info("Attaching forward functions to axon.")
        self.axon.attach(
            forward_fn=self.forward,
            blacklist_fn=self.blacklist_fn,
        ).attach(
            forward_fn=self.forward_ping
        )

        if not self.dev_flag:
            # Serve the axon.
            bt.logging.info(f"Serving axon on network: {self.network} with netuid: {self.netuid}")
            self.axon.serve(netuid=self.netuid, subtensor=self.subtensor)
            bt.logging.info(f"Axon: {self.axon}")

        # Start the axon server.
        bt.logging.info(f"Starting axon server on port: {self.port}")
        self.axon.start()

    def run(self):
        self.setup_axon()

        # Keep the miner alive.
        bt.logging.info("Starting main loop")
        step = 0
        while True:
            try:
                # Periodically update our knowledge of the network graph.
                if step % 60 == 0:
                    if not self.dev_flag:
                        self.metagraph.sync()
                        log = (
                            f'Block: {self.metagraph.block.item()} | '
                            f'Incentive: {self.metagraph.I[self.my_subnet_uid]} | '
                        )
                        bt.logging.info(log)
                step += 1
                time.sleep(1)

            except KeyboardInterrupt:
                self.axon.stop()
                bt.logging.success('Miner killed by keyboard interrupt.')
                break
            except Exception as e:
                bt.logging.error(traceback.format_exc())
                continue

async def setup_subgraph_generator(max_future_events: int = 500, max_past_events: int = 500) -> SubgraphGenerator:

    event_fetcher = EventFetcher()
    await event_fetcher.initialize_substrate_connections()

    coldkey_finder = ColdkeyFinder()
    await coldkey_finder.initialize_substrate_connection()

    return SubgraphGenerator(event_fetcher=event_fetcher, coldkey_finder=coldkey_finder, max_future_events=max_future_events, max_past_events=max_past_events)

# Run the miner

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run the miner with command-line arguments.")
    parser.add_argument('--netuid', type=int, default=1, help="The chain subnet uid.")
    parser.add_argument('--wallet_path', type=str, default="~/.bittensor/wallets/", help="The path to the wallets.")
    parser.add_argument('--coldkey', type=str, default="miners", help="The cold key for the miner.")
    parser.add_argument('--hotkey', type=str, default="miner_1", help="The hot key for the miner.")
    parser.add_argument('--port', type=int, default=8000, help="Port number for the miner.")
    parser.add_argument('--external_ip', type=str, default=None, help="External IP for miner to serve on the metagraph.")
    parser.add_argument('--dev_flag', type=bool, default=False, help="Enable developer mode. This will run the miner without needing a blockchain endpoint.")
    parser.add_argument('--archive_node_address', type=str, default="ws://5.9.118.137:9944", help="Address of bittensor archive node.")
    parser.add_argument('--max_future_events', type=int, default=500, help="Number of blocks to querying into the future from the target block recieved.")
    parser.add_argument('--max_past_events', type=int, default=500, help="Number of blocks to querying into the past from the target block recieved.")
    
    args = parser.parse_args()

    Constants.ARCHIVE_NODE_ADDRESS = args.archive_node_address

    subgraph_generator = asyncio.run(setup_subgraph_generator())
    
    miner = Miner(
        dev_flag=args.dev_flag,
        wallet_path=args.wallet_path,
        coldkey=args.coldkey,
        hotkey=args.hotkey,
        port=args.port,
        external_ip=args.external_ip,
        netuid=args.netuid,
        subtensor_network=args.archive_node_address,
        subgraph_generator=subgraph_generator
    )
    miner.run()