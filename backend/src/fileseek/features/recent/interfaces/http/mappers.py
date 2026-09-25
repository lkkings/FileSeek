from fileseek.features.recent.application.commands import RecordAccessCommand
from fileseek.features.recent.application.queries import ListRecentAccessQuery


def list_recent_query(limit: int) -> ListRecentAccessQuery:
    return ListRecentAccessQuery(limit)

def record_access_command(file_id: str) -> RecordAccessCommand:
    return RecordAccessCommand(file_id)
