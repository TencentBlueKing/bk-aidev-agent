from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("aidev_wxbot", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="agentsession",
            name="active_session_code",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="当前执行会话ID"),
        )
    ]
