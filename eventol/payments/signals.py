"""Signals for the apps that consume payments (e.g. manager issues the tickets).

Both are sent after the database transaction commits, with ``order`` as argument.
"""

from django.dispatch import Signal

# The order was approved and fits the quota: issue the tickets
order_paid = Signal()

# A paid order was refunded or charged back: invalidate the tickets
order_refunded = Signal()
