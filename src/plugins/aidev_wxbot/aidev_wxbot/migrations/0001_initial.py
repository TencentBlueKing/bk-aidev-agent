# Generated migration file

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AgentSession',
            fields=[
                ('group_id', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='群组ID')),
                ('thread_id', models.CharField(max_length=255, verbose_name='线程ID')),
                ('last_session_time', models.DateTimeField(verbose_name='最后会话时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': 'Agent会话',
                'verbose_name_plural': 'Agent会话',
                'db_table': 'wxaibot_agent_session',
            },
        ),
    ]
