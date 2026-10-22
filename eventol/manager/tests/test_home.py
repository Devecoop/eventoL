"""Home parity checks against the API used by the previous React home."""
import datetime
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone, translation
from rest_framework.test import APIClient

from manager.home import HOME_LISTS, home_sections, search_section
from manager.models import Event, EventDate, EventTag, EventUser
from manager.templatetags.home import home_trans

pytestmark = pytest.mark.django_db


@pytest.fixture
def home_events():
    today = timezone.localdate()
    events = []
    for index, days in enumerate([3, 1, -1, 7]):
        event = Event.objects.create(
            name='Home event {}'.format(index), event_slug='home-{}'.format(index),
            abstract='Open software community' if index != 1 else 'Other topic',
            limit_proposal_date=today, email='home@example.org',
            schedule_confirmed=index == 0,
            registration_closed=index == 3,
        )
        EventDate.objects.create(event=event, date=today + datetime.timedelta(days=days))
        events.append(event)
    tag = EventTag.objects.create(name='Linux community', slug='linux-community')
    events[0].tags.add(tag)
    return events


def section_slugs(section):
    return [event.event_slug for event in section['events']]


def test_lists_match_existing_api(home_events, rf):
    from django.contrib.auth.models import AnonymousUser
    request = rf.get('/')
    request.user = AnonymousUser()
    sections = {section['id']: section for section in home_sections(request)}
    assert sections['my_events']['events'] == []
    client = APIClient()
    for section_id, _, ordering, filters in HOME_LISTS:
        params = {name: str(value).lower() for name, value in filters.items()}
        params.update(ordering=ordering, fields='event_slug')
        response = client.get('/api/events/', params)
        assert response.status_code == 200
        assert section_slugs(sections[section_id]) == [
            event['event_slug'] for event in response.data['results']]
    # The current API uses dates rather than registration_closed for these lists.
    assert home_events[3].event_slug in section_slugs(sections['recent'])


@pytest.mark.parametrize('term', ['Home', 'Home 0', 'software community',
                                  'linux', 'home-1', 'absent', 'Home,0'])
def test_search_matches_existing_api(home_events, rf, term):
    request = rf.get('/', {'search': term})
    section = search_section(request)
    response = APIClient().get('/api/events/', {'search': term, 'fields': 'event_slug'})
    assert section_slugs(section) == [event['event_slug'] for event in response.data['results']]


def test_my_events_are_private(home_events, rf):
    owner = User.objects.create_user('home-owner')
    other = User.objects.create_user('home-other')
    EventUser.objects.create(event=home_events[0], user=owner)
    EventUser.objects.create(event=home_events[1], user=other)
    request = rf.get('/')
    request.user = owner
    assert section_slugs(home_sections(request)[0]) == [home_events[0].event_slug]


def test_search_fragment_escapes_content(home_events):
    event = home_events[0]
    event.name = '<script>alert(1)</script>'
    event.place = json.dumps({'name': '" onmouseover="alert(1)'})
    event.save()
    response = Client().get(reverse('home_search'), {'search': 'alert'}, HTTP_HX_REQUEST='true')
    body = response.content.decode()
    assert response.status_code == 200
    assert 'search_results' in body
    assert '&lt;script&gt;' in body
    assert '<script>' not in body
    assert '<!doctype' not in body.lower()
    assert 'data-place="{&quot;' in body


def test_search_empty_states(home_events):
    client = Client()
    response = client.get(reverse('home_search'), {'search': 'missing-unique-event'})
    assert b'Event not found' in response.content
    assert b'No Event found in your search' in response.content
    assert not client.get(reverse('home_search')).content.strip()


def test_pending_registration_redirect(home_events):
    client = Client()
    client.force_login(User.objects.create_user('pending-registration'))
    session = client.session
    session['registration_event_slug'] = home_events[0].event_slug
    session['registration_role'] = 'attendee'
    session.save()
    response = client.get(reverse('home'))
    assert response.status_code == 302
    assert response.url == reverse('attendee_registration', args=[home_events[0].event_slug])
    assert 'registration_event_slug' not in client.session
    assert 'registration_role' not in client.session


def test_home_is_server_rendered(home_events, settings):
    # Rendering this page must not require a Home/React bundle in the manifest.
    settings.WEBPACK_LOADER = {'DEFAULT': {
        'STATS_FILE': str(__file__), 'BUNDLE_DIR_NAME': '',
    }}
    from unittest.mock import patch
    with patch('webpack_loader.templatetags.webpack_loader.utils.get_files', return_value=[]):
        response = Client().get(reverse('home'))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'Home event 0' in body
    assert 'data-home-slider' in body
    assert 'hx-get="/home/search/"' in body
    assert 'render_components' not in body
    assert 'react' not in body.lower()


def test_home_translations_use_existing_catalog():
    with translation.override('es'):
        assert home_trans('Search your event') == 'Busca tu evento'


def test_home_list_limit_does_not_truncate_my_events(home_events, rf, settings):
    settings.REST_FRAMEWORK = dict(settings.REST_FRAMEWORK, PAGE_SIZE=1)
    owner = User.objects.create_user('many-events-owner')
    for event in home_events:
        EventUser.objects.create(event=event, user=owner)
    request = rf.get('/')
    request.user = owner
    sections = {section['id']: section for section in home_sections(request)}
    assert len(sections['my_events']['events']) == 4
    assert len(sections['recent']['events']) == 1
    assert len(search_section(rf.get('/', {'search': 'Home'}))['events']) == 1


def test_card_images_and_locations(home_events, rf):
    event = home_events[0]
    Event.objects.filter(pk=event.pk).update(image='images_thumbnails/example.png')
    section = search_section(rf.get('/', {'search': 'home-0'}))
    assert section['events'][0].home_image.endswith('/images_thumbnails/example.png')
    event.image = ''
    event.place = json.dumps({'geometry': {'location': {'lat': -34.6, 'lng': -58.4}}})
    event.save()
    response = Client().get(reverse('home_search'), {'search': 'home-0'})
    assert b'data-home-map' in response.content
    assert b'&quot;lat&quot;: -34.6' in response.content


def test_home_branding_and_authenticated_links(home_events):
    from types import SimpleNamespace
    from unittest.mock import patch
    settings = SimpleNamespace(
        message='A "custom" message <script>unsafe</script>',
        background=SimpleNamespace(url='/media/background.png'),
        logo_header=SimpleNamespace(url='/media/header.png'),
        logo_landing=SimpleNamespace(url='/media/landing.png'),
    )
    client = Client()
    with patch('manager.context_processors.EventolSetting.load', return_value=settings), \
            patch('webpack_loader.templatetags.webpack_loader.utils.get_files', return_value=[]):
        anonymous = client.get(reverse('home')).content.decode()
        assert '/media/background.png' not in anonymous
        assert 'class="home-page"' in anonymous
        assert '/media/header.png' in anonymous
        assert '/media/landing.png' in anonymous
        assert 'A &quot;custom&quot; message &lt;script&gt;unsafe&lt;/script&gt;' in anonymous
        assert 'href="/accounts/login/"' in anonymous
        assert 'href="/create-event/"' not in anonymous
        client.force_login(User.objects.create_user('home-links', first_name='Aye'))
        authenticated = client.get(reverse('home')).content.decode()
        assert 'href="/create-event/"' in authenticated
        assert 'href="/accounts/profile/"' in authenticated
        assert 'href="/accounts/login/"' not in authenticated


def test_anonymous_pending_registration_is_preserved():
    client = Client()
    session = client.session
    session['registration_event_slug'] = 'pending'
    session['registration_role'] = 'attendee'
    session.save()
    from unittest.mock import patch
    with patch('webpack_loader.templatetags.webpack_loader.utils.get_files', return_value=[]):
        assert client.get(reverse('home')).status_code == 200
    assert client.session['registration_event_slug'] == 'pending'
