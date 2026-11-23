from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("aidev_bkplugin", "0002_event_delivery")]

    operations = [
        migrations.CreateModel(
            name="SessionPollTurn",
            fields=[
                ("session_key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("turn_id", models.CharField(max_length=255)),
                ("expires_at", models.DateTimeField()),
                ("ticket", models.UUIDField(unique=True)),
                ("started", models.BooleanField(default=False)),
            ],
        ),
    ]
