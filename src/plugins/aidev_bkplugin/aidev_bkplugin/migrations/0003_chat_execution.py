from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("aidev_bkplugin", "0002_event_delivery")]

    operations = [
        migrations.CreateModel(
            name="ChatExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(max_length=64, unique=True)),
                ("task_id", models.CharField(max_length=32)),
                ("request_key", models.CharField(max_length=64)),
                ("status", models.CharField(default="queued", max_length=16)),
                ("run_id", models.CharField(default="", max_length=255)),
                ("result", models.JSONField(null=True)),
                ("error", models.CharField(default="", max_length=128)),
                ("cancelled", models.BooleanField(default=False)),
                ("expires_at", models.DateTimeField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
