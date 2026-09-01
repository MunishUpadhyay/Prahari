from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('signals', '0005_signal_signals_sig_user_id_c6184e_idx'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='signal',
            name='contact_number',
        ),
    ]
