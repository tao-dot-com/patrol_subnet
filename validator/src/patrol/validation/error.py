from uuid import UUID


class MinerTaskException(Exception):
    def __init__(self, message: str, task_id: UUID = None, batch_id: UUID = None):
        super().__init__(message)
        self.message = message
        self.task_id = task_id
        self.batch_id = batch_id

    def __str__(self):
        return f"{self.__class__.__name__}({self.message}: task_id={self.task_id}; batch_id={self.batch_id})"