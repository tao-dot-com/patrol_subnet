import bittensor as bt

sub = bt.subtensor(network="finney")

print(sub.get_current_block())