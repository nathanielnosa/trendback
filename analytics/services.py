
from .models import AnalyticsEvent

def record_event(*,event_type,actor=None,post=None,visitor_id="",source="",metadata=None,):
    
    valid_event_types = {
        choice for choice, _label in AnalyticsEvent.EventType.choices
    }

    if event_type not in valid_event_types:
        raise ValueError(
            f"Unsupported analytics event type: {event_type}"
        )

    return AnalyticsEvent.objects.create(event_type=event_type,actor=actor,post=post,visitor_id=visitor_id,source=source,metadata=metadata or {})