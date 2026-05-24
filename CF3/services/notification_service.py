from __future__ import annotations

from datetime import datetime


class NotificationService:

    @staticmethod
    def create_notification(title: str, message: str) -> dict:

        return {
            'title': title,
            'message': message,
            'created_at': datetime.now().isoformat(),
            'status': 'active',
        }
