# Stake Prediction

This task incentivizes miners to accurately predict staking movements for wallets in a subnet.
Miners will receive a batch of tasks indicating the subnet, a set of wallets currently active in that subnet, and a block prediction interval.

Miners have 16 seconds to respond to each task. Missing responses or time-outs will score zero.

Miners' responses should include predictions in RAO for the total amount of stake removed during the prediction interval for each wallet given.
Wallet predictions absent from the response will be assumed to be predictions of zero stake movement.

THere is no incentive to respond quicker than time-out. All responses received within the timeout interval will be scored equally.

## Scoring

The predictions for each wallet are compared against the actual **StakeRemoved** events recorded on the chain during
the prediction interval according to the formula:

$$`accuracy = 1 - \left(\frac{2.0 \times error}{1 + actual}\right) ^ 2`$$

where:
- ***error*** is the difference between the predicted amount and actual amount of stake removed during the interval;  
- ***actual*** is the actual stake removed during the interval.

Both these values are TAO, converted from the RAO amounts in the predictions and actual data.

Overall accuracy is calculated as the mean accuracy of all the tasks in a batch.

## Weights

Overall accuracy is normalized and used to set weights once per epoch.
This task contributes 50% of the weights.

