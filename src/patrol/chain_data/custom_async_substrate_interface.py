from async_substrate_interface import AsyncSubstrateInterface

class CustomAsyncSubstrateInterface(AsyncSubstrateInterface):
    def __init__(self, url=None, ws=None, **kwargs):
        """
        Extends AsyncSubstrateInterface to allow injecting a custom websocket connection.
        
        Args:
            url: the URI of the chain to connect to.
            ws: Optional websocket connection to use. If provided, it overrides the default one.
            **kwargs: any additional keyword arguments for the parent class.
        """
        # Initialize the parent class with all normal parameters.
        super().__init__(url, **kwargs)
        # Override the websocket connection if one is provided.
        self.ws = ws