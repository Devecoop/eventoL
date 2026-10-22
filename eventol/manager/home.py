"""Server-rendered home lists, with the same queries as the React home."""
import json
from urllib.parse import urlsplit

from django.conf import settings
from rest_framework.filters import SearchFilter
from rest_framework.request import Request

from eventol.api import EventViewSet
from manager.models import Event


HOME_LISTS = (
    ('recent', 'Recent Events', '-created_at', {'registration_is_open': True}),
    ('featured', 'Featured Events', '-attendees_count', {'registration_is_open': True}),
    ('next', 'Upcoming Events', 'last_date', {'registration_is_open': True}),
    ('schedule_confirmed', 'Events with Confirmed Schedule', '-attendees_count',
     {'registration_is_open': True, 'schedule_confirmed': True}),
    ('finished', 'Finished Events', '-attendees_count', {'registration_is_open': False}),
)


def home_section(section_id, title, queryset, show_empty=False):
    events = list(queryset.prefetch_related('tags'))
    for event in events:
        # React uses URL(image).pathname rather than the absolute API URL.
        event.home_image = urlsplit(event.image.url).path if event.image else ''
        try:
            place = json.loads(event.place or '{}')
        except (TypeError, ValueError):
            place = {}
        event.home_place = place.get('name', '') if isinstance(place, dict) else ''
    return {'id': section_id, 'title': title, 'events': events, 'show_empty': show_empty}


def search_section(request):
    # Reuse the API's tokenization, multi-word matching and tag searches.
    queryset = SearchFilter().filter_queryset(
        Request(request), Event.objects.all(), EventViewSet())
    limit = settings.REST_FRAMEWORK.get('PAGE_SIZE', 20)
    return home_section('search_results', 'Search results', queryset[:limit], True)


def home_sections(request):
    sections = [home_section('my_events', 'My Events',
                             Event.objects.get_event_by_user(request.user))]
    limit = settings.REST_FRAMEWORK.get('PAGE_SIZE', 20)
    for section_id, title, ordering, filters in HOME_LISTS:
        queryset = Event.objects.filter(**filters).order_by(ordering)[:limit]
        sections.append(home_section(section_id, title, queryset))
    return sections
