from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0012_alter_travelbooking_approval_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="travelbooking",
            name="cancellation_reason",
            field=models.TextField(blank=True),
        ),
    ]
