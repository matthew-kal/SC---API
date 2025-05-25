# users/migrations/0058_cascade_assignedmodules.py
from django.db import migrations

FK = "users_assignedmodules_patient_id_e420ea62_fk_users_customuser_id"

class Migration(migrations.Migration):
    dependencies = [("users", "0057_pushnotificationtoken")]

    atomic = False          # MySQL autocommits ALTER TABLE

    operations = [
        migrations.RunSQL(f"""
            ALTER TABLE users_assignedmodules
            DROP FOREIGN KEY {FK};
        """),
        migrations.RunSQL(f"""
            ALTER TABLE users_assignedmodules
            ADD CONSTRAINT {FK}
            FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
            ON DELETE CASCADE;
        """,
        reverse_sql=f"""
            ALTER TABLE users_assignedmodules
            DROP FOREIGN KEY {FK};
            ALTER TABLE users_assignedmodules
            ADD CONSTRAINT {FK}
            FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
            ON DELETE RESTRICT;
        """),
    ]
