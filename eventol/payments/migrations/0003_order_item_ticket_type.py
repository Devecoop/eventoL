import django.db.models.deletion
from django.db import migrations, models


def copy_unit_price_to_items(apps, schema_editor):
    """The unit price moves from the order to each item (orders can mix ticket types)."""
    Order = apps.get_model('payments', 'Order')
    OrderItem = apps.get_model('payments', 'OrderItem')
    for order in Order.objects.all():
        OrderItem.objects.filter(order=order).update(unit_price=order.unit_price)


class Migration(migrations.Migration):
    dependencies = [
        ('manager', '0061_ticket_types'),
        ('payments', '0002_single_seller_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='ticket_type',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='manager.tickettype',
                verbose_name='Ticket type',
            ),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='unit_price',
            field=models.DecimalField(
                decimal_places=2, default=0, max_digits=12, verbose_name='Unit price'
            ),
            preserve_default=False,
        ),
        migrations.RunPython(copy_unit_price_to_items, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='order',
            name='unit_price',
        ),
        migrations.RemoveField(
            model_name='order',
            name='quota',
        ),
    ]
