# Helper scripts for local development and testing

## Testing your miner code

The easiest way to test your miner code, is to run your miner.py in dev mode with the following command

"python miner.py --dev_flag True --port 8000"

This will turn off the blacklisting and verify functionality, allowing you to ping your miner endpoint as a normal api. 

Next, you can run 

"python query_miner_endpoint.py" 

Which will send a request to your locally running miner. You can change the number of requests by updating the number of REQUESTS at the bottom of the script.

NOTE: You may see some cases of partial validation, saying that some edges were unverifiable. For example:

`Validation finished - Validation passed with some edges unverifiable: Original Volume:2000, Validated Volume: 1998`

This is due to certain block numbers not being fetched, when the in memory event store is pre-populated with the events required during validation e.g. from the subtrate client timing out when querying for many blocks at a time.

## Testing the validator code

While it is not strickly necessary, as the validator code will run itself, it can be useful to test it for debugging purposes. 

With this in mind, we have created a very simple miner endpoint that returns a static response. For more sophisticated testing, it could be useful to set a miner up with the dev flag turned on (see instructions above).

You can run the static miner endpoint using

"uvicorn static_miner_endpoint:app --host 0.0.0.0 --port 8000"