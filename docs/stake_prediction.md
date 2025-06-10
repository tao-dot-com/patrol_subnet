# Stake Prediction

This task incentivizes miners to accurately predict staking movements for wallets in a subnet.
Miners will receive a batch of tasks indicating the subnet, a set of wallets currently active in that subnet, and a block prediction interval.

Miners have 16 seconds to respond to each task. Missing responses or time-outs will score zero.

Miners' responses should include predictions in RAO for the total amount of stake removed during the prediction interval for each wallet given.
Wallet predictions absent from the response will be assumed to be predictions of zero stake movement.

THere is no incentive to respond quicker than time-out. All responses received within the timeout interval will be scored equally.

## Scoring

The predictions for each subnet are compared against the actual **StakeRemoved** events recorded on the chain during

The task scoring is on per-wallet basis. There are 2 factors for each score:
1. The logarithmic magnitude of the actual stake movement
2. The accuracy of the prediction - an inverted parabolic formula

The scores for each wallet are summed to give a total score. Hence subnets with more wallets can yield higher scores;
wallets with stake movements can yield higher scores.

$$`score = \sum_{n=0}^{N-1} \Bigg[\big(1 + log_{10}(actual_n + 1)\big) \times max\Bigg(0, 1 - \left(\frac{2.0 \times error_n}{1 + actual_n}\right) ^ 2\Bigg)\Bigg]`$$

where:
- ***error*** is the difference between the predicted amount and actual amount of stake removed during the interval;  
- ***actual*** is the actual stake removed during the interval.
- ***n*** is the subnet index

Both these values are TAO, converted from the RAO amounts in the predictions and actual data.

Overall accuracy score for a task is the sum of accuracies over all wallets predicted.

## Weights

Overall accuracy is normalized and used to set weights once per epoch.
This task contributes 40% of the weights.

