from ..models import Broadcast, Whisper


def inbox(member):
    return Whisper.objects.filter(member=member).only("kind", "title", "body", "is_read", "created_at")


def unread_count(member) -> int:
    return Whisper.objects.filter(member=member, is_read=False).count()


def recent_broadcasts(limit=20):
    return Broadcast.objects.select_related("sent_by")[:limit]
