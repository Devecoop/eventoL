"""Keep the home's existing JavaScript translations during the migration."""
from functools import lru_cache

from django import template
from django.utils.translation import get_language
from django.utils.translation.trans_real import DjangoTranslation

register = template.Library()


@lru_cache(maxsize=32)
def home_catalog(language):
    return DjangoTranslation(language, domain='djangojs')


@register.simple_tag
def home_trans(message):
    return home_catalog(get_language()).gettext(message)
