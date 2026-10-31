from database.models import AuditLog


def log_action(session, user_id, action, receipt_id=None, details=None):
    session.add(
        AuditLog(
            user_id=user_id,
            receipt_id=receipt_id,
            action=action,
            details=details,
        )
    )
