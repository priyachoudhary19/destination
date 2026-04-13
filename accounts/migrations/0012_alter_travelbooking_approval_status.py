from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0011_userfeedback_discovery_source_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="travelbooking",
            name="approval_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("cancelled", "Cancelled by User"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
