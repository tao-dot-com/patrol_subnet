
class WeightWatcher: #lol
    def __init__(self, config: bt.config, my_uid: int, wallet: bt.wallet):
        self.subtensor = bt.subtensor(config=config)
        self.scoring = MinerScoring()
        self.moving_avg_scores = [0] * 256 #256 is the max number of uids
        self.alpha = 0.1 #used for moving average scores
        self.wallet = wallet
        self.my_uid = my_uid
        self.config = config
        self.moving_avg_scores_path = os.path.join(os.getcwd(), 'moving_avg_scores.json')
        if not os.path.exists(self.moving_avg_scores_path):
            self.save_moving_avg_scores()

    def save_moving_avg_scores(self):
        with open(self.moving_avg_scores_path, 'w') as f:
            json.dump(self.moving_avg_scores, f)

    def load_moving_avg_scores(self):
        try:
            with open(self.moving_avg_scores_path, 'r') as f:
                try:
                    self.moving_avg_scores = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    self.moving_avg_scores = [0] * 256
        except FileNotFoundError:
            self.moving_avg_scores = [0] * 256

    def get_tempo(self):
        return self.subtensor.query_subtensor('Tempo', params=[self.config.netuid])

    def should_set_weights(self):
        last_update = self.subtensor.blocks_since_last_update(self.config.netuid, self.my_uid)
        if last_update > self.get_tempo():
            return True
        return False
    
    def update_moving_avg_scores(self):

        scores = self.scoring.load_all_cached_scores()
        scores = self.scoring.normalize_scores(scores)

        if type(scores) != dict:
            logger.error(f"scores is not a dictionary: {scores}")
            return

        for i in scores.keys():
            self.moving_avg_scores[i] = self.alpha * scores[i] + (1 - self.alpha) * self.moving_avg_scores[i]

        self.save_moving_avg_scores()

    def set_weights(self):
        self.load_moving_avg_scores()
        self.update_moving_avg_scores()

        total = sum(self.moving_avg_scores)
        if total < 1:
            weights = self.moving_avg_scores
        else:
            weights = [score / total for score in self.moving_avg_scores]

        if sum(weights) == 0:
            bt.logging.warning(f"All weights are 0 for validator {self.my_uid}.  Skipping weight update.")
            return
        
        self.subtensor.set_weights(netuid=self.config.netuid, 
                                   wallet=self.wallet, 
                                   uids=[i for i in range(256)],
                                   weights=weights,
                                   wait_for_inclusion=True)
        
        bt.logging.debug(f"Weights set for validator {self.my_uid}")