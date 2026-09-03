from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("aidev_bkplugin", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="EventSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("scope_key", models.CharField(max_length=64, db_index=True)),
                ("subscriber", models.CharField(max_length=255)),
                ("event_name", models.CharField(max_length=128)),
                ("app_code", models.CharField(max_length=255)),
                ("session_code", models.CharField(max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("property", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="EventDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.CharField(max_length=64)),
                ("envelope", models.JSONField(default=dict)),
                ("route", models.JSONField(default=dict)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("available_at", models.DateTimeField()),
                ("lease_token", models.CharField(default="", max_length=32)),
                ("lease_until", models.DateTimeField(null=True)),
                ("progress", models.PositiveIntegerField(default=0)),
                ("error_type", models.CharField(default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscription", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="aidev_bkplugin.eventsubscription")),
            ],
            options={
                "indexes": [models.Index(fields=["status", "available_at"], name="event_delivery_ready")],
                "constraints": [models.UniqueConstraint(fields=("subscription", "event_id"), name="unique_event_delivery")],
            },
        ),
    ]
