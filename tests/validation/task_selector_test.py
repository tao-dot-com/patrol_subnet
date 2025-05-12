import pytest

from patrol.constants import TaskType
from patrol.validation.validator import TaskSelector


def test_select_task_according_to_weightings():
    weightings = {
        TaskType.COLDKEY_SEARCH: 20,
        TaskType.HOTKEY_OWNERSHIP: 60,
    }

    task_selector = TaskSelector(weightings)

    counts = {
        TaskType.COLDKEY_SEARCH: 0,
        TaskType.HOTKEY_OWNERSHIP: 0,
    }

    for i in range(1000):
        task = task_selector.select_task()
        counts[task] += 1

    assert counts[TaskType.COLDKEY_SEARCH] == pytest.approx(250, 0.1)
    assert counts[TaskType.HOTKEY_OWNERSHIP] == pytest.approx(750, 0.1)



