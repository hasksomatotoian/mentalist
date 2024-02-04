from datetime import datetime, timezone


class Assistant:
    def __init__(self, name: str, description: str, instructions_filename: str, model: str,
                 needs_code_interpreter: bool, needs_retrieval: bool, assistant_id: int = None, ai_id: str = None,
                 created: datetime = None, last_update: datetime = None, checksum: str = None):

        self.id = assistant_id
        self.name = name
        self.description = description
        self.instructions_filename = instructions_filename
        self.model = model
        self.needs_code_interpreter = needs_code_interpreter
        self.needs_retrieval = needs_retrieval
        self.ai_id = ai_id
        self.created = created
        self.last_update = last_update
        self.checksum = checksum
