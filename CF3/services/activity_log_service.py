from __future__ import annotations

from datetime import datetime


class ActivityLogService:

    logs = []

    @classmethod
    def add_log(cls, user: str, action: str):

        cls.logs.append(
            {
                'user': user,
                'action': action,
                'timestamp': datetime.now().isoformat(),
            }
        )

    @classmethod
    def get_logs(cls):

        return cls.logs
