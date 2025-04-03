
class Constants:
    MAX_RESPONSE_TIME: int = 160  # timeout response time in seconds
    OPENTENSOR_ARCHIVE_NODE: str = "wss://archive.chain.opentensor.ai:443/" #URL for the Opentensor Foundation Archive Node
    LOCAL_INDEXER_ADDRESS: str = "localhost"
    ARCHIVE_NODE_ADDRESS: str = OPENTENSOR_ARCHIVE_NODE #MODIFY THIS IF YOU WANT TO CHANGE WHICH ADDRESS YOU WANT TO USE FOR THE ARCHIVE NODE
    SUBNET_NETUID: int = 81
    U64_MAX = 2**64 - 1
    LOWER_BLOCK_LIMIT: int = 3014341

