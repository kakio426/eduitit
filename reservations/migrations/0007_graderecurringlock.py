from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0006_reservation_created_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="GradeRecurringLock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("day_of_week", models.IntegerField()),
                ("period", models.IntegerField()),
                ("grade", models.IntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="reservations.specialroom")),
            ],
        ),
        migrations.AddConstraint(
            model_name="graderecurringlock",
            constraint=models.UniqueConstraint(fields=("room", "day_of_week", "period"), name="unique_grade_lock_per_slot"),
        ),
    ]
