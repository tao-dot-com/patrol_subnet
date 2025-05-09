from collections import namedtuple

HotkeyOwnershipScore = namedtuple(
    typename="HotkeyOwnershipScore",
    field_names=["validity", "response_time", "overall"]
)

class HotkeyOwnershipScoring:

    def __init__(self,
                 response_time_half_score: float = 2.0,
                 response_time_weight = 50,
                 validity_weight = 50,
    ):
        self._response_time_half_score = response_time_half_score
        self._response_weight = response_time_weight
        self._validity_weight = validity_weight

    def score(self, is_valid: bool, response_time_seconds: float):
        if not is_valid:
            return HotkeyOwnershipScore(0, 0, 0)

        validity_score = 1

        response_time_score = self._response_time_half_score/(response_time_seconds + self._response_time_half_score)

        overall_score = sum([
            validity_score * self._validity_weight,
            response_time_score * self._validity_weight
        ]) / sum([self._validity_weight, self._validity_weight])

        return HotkeyOwnershipScore(validity_score, response_time_score, overall_score)

