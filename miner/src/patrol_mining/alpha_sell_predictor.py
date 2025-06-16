from patrol_common import TransactionType, AlphaSellPrediction, WalletIdentifier

class AlphaSellPredictor:

    async def predict_constant_value(self, wallets: list[WalletIdentifier]) -> list[AlphaSellPrediction]:
        predictions = []

        for wallet in wallets:
            predictions.append(
                AlphaSellPrediction(
                    wallet_hotkey_ss58=wallet.hotkey,
                    wallet_coldkey_ss58=wallet.coldkey,
                    transaction_type=TransactionType.STAKE_REMOVED,
                    amount=0
                )
            )
        return predictions