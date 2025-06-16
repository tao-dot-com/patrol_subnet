# Helper scripts for local development and testing

## Testing your miner code

The easiest way to test your miner code, is to run your miner.py in dev mode with the following command (read the [mining readme](../../docs/mining.md) doc first)

"python miner.py --dev_flag True --port 8000"

This will turn off the blacklisting and verify functionality, allowing you to ping your miner endpoint as a normal api. 

Then you will need to move into the validator directory and run

"pip install -e ." 

Next, return to this local_dev directory and you can run 

"python query_miner_endpoint_hotkey_ownership.py

Which will send a request to your locally running miner for either task you want to test. You can change the number of requests by updating the number of REQUESTS on line 79. 

## Testing the validator code

While it is not strictly necessary, as the validator code will run itself, it can be useful to test it for debugging purposes. 

With this in mind, we have created a very simple miner endpoint that returns a static response for the coldkey search task. For more sophisticated testing, it could be useful to set a miner up with the dev flag turned on (see instructions above).

You can run the static miner endpoint using

"uvicorn static_miner_endpoint:app --host 0.0.0.0 --port 8000"
