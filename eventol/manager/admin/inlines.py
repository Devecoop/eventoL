from django.contrib.admin.options import TabularInline

from manager.models import Event, EventDate, TicketType


class EventDateAdminInline(TabularInline):
    model = EventDate


class TicketTypeAdminInline(TabularInline):
    model = TicketType
    extra = 0


class EventTagInline(TabularInline):
    model = Event.tags.through
