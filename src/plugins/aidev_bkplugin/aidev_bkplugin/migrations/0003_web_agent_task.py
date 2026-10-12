from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("aidev_bkplugin", "0002_event_delivery")]

    operations = [
        migrations.CreateModel(
            name="WebAgentTask",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("task_id", models.CharField(max_length=32)),
                ("request_key", models.CharField(max_length=64)),
                ("status", models.CharField(default="queued", max_length=16)),
                ("result", models.JSONField(null=True)),
                ("error", models.CharField(default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
