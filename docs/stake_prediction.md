# Stake Prediction

This task incentivizes miners to accurately predict staking movements for wallets in a subnet.
Predictions for **StakeAdded** and **StakeRemoved** will be scored against the chain data for each wallet on a subnet.
Miners will receive a batch of tasks indicating the subnet, a set of wallets currently active in that subnet, and a block prediction interval.

Miners have 16 seconds to respond to each task. Missing responses or time-outs will score zero.

Miners' responses should include predictions in RAO for the total amount of stake removed during the prediction interval for each wallet given.
Wallet predictions absent from the response will be assumed to be predictions of zero stake movement.

THere is no incentive to respond quicker than time-out. All responses received within the timeout interval will be scored equally.

## Scoring

The predictions for each subnet are compared against the actual **StakeRemoved** and **StakeAdded** events recorded on the chain during

The task scoring is on per-wallet basis. There are 2 factors for each score:
1. The logarithmic magnitude of the actual stake movement
2. The accuracy of the prediction - an inverted parabolic formula

The scores for each wallet are summed to give a total score. Hence subnets with more wallets can yield higher scores;
wallets with stake movements can yield higher scores.

$`score = \sum_{n=0}^{N-1} \Bigg[\big(1 + log_{10}(actual_n + 1)\big) \times max\Bigg(0, 1 - \left(\frac{2.0 \times error_n}{1 + actual_n}\right) ^ 2\Bigg)\Bigg]`$

The scores for **StakeRemoved** events and **StakeAdded** predictions are added to give an overall total accuracy score.

where:
- ***error*** is the difference between the predicted amount and actual amount of stake added or removed during the interval;  
- ***actual*** is the actual stake removed during the interval.
- ***n*** is the subnet index

Both these values are TAO, converted from the RAO amounts in the predictions and actual data.

Overall accuracy score for a task is the sum of accuracies over all wallets predicted.

## Weights

Overall accuracy is normalized and used to set weights once per epoch.
This task contributes 100% of the weights.

### Sample Synapse request
```json
{
  "batch_id": "a1877105-bd97-46af-b749-416b2f4d7cf3",
  "task_id": "130dea16-9843-4b3a-97c8-0ab845178165",
  "prediction_interval": {
    "start_block": 5500000,
    "end_block": 5507200
  },
  "subnet_uid": 42,
  "wallets": [
    { "hotkey": "5GYnKhRwkRN78ZREMhohMvCRQBoc6sFwkTskYVjrQWWDVnZp", "coldkey": "5DLr6vrZqmCQBxH9H9UNJbErTtoDBrSkMJZu1xZwWsKCz1ig"},
    { "hotkey": "5GxqhbNg9gTfZUdcKji4pMDQdhqcVCTNWon9VyuqKdoWCsuH", "coldkey": "5FEo31ujEdvDjKPwS5p54ek5HksjJgcwk3FrEfxtikLcm2U1"},
    ...
  ]
}
```

### Sample Synapse response
```json
{
  "batch_id": "a1877105-bd97-46af-b749-416b2f4d7cf3",
  "task_id": "130dea16-9843-4b3a-97c8-0ab845178165",
  "subnet_uid": 42,
  "predictions": [
    { "amount": 12000000000, "transaction_type": "StakeRemoved", "wallet_hotkey_ss58": "5GYnKhRwkRN78ZREMhohMvCRQBoc6sFwkTskYVjrQWWDVnZp", "wallet_coldkey_ss58": "5DLr6vrZqmCQBxH9H9UNJbErTtoDBrSkMJZu1xZwWsKCz1ig"},
    { "amount": 0, "transaction_type": "StakeRemoved", "wallet_hotkey_ss58": "5GxqhbNg9gTfZUdcKji4pMDQdhqcVCTNWon9VyuqKdoWCsuH", "wallet_coldkey_ss58": "5FEo31ujEdvDjKPwS5p54ek5HksjJgcwk3FrEfxtikLcm2U1"},
    { "amount": 50000000000, "transaction_type": "StakeAdded", "wallet_hotkey_ss58": "5GYnKhRwkRN78ZREMhohMvCRQBoc6sFwkTskYVjrQWWDVnZp", "wallet_coldkey_ss58": "5DLr6vrZqmCQBxH9H9UNJbErTtoDBrSkMJZu1xZwWsKCz1ig"},
    { "amount": 0, "transaction_type": "StakeAdded", "wallet_hotkey_ss58": "5GxqhbNg9gTfZUdcKji4pMDQdhqcVCTNWon9VyuqKdoWCsuH", "wallet_coldkey_ss58": "5FEo31ujEdvDjKPwS5p54ek5HksjJgcwk3FrEfxtikLcm2U1"},
    ...
  ]
}
```
- All predicted amounts will be in RAO.
- Predictions for wallets not present in the request will be ignored.
- Duplicate wallet predictions (same hotkey) will be rejected, and the entire task will score 0.0)
