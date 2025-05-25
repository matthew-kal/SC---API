# users/migrations/0061_cascade_datacollection.py
from django.db import migrations

FK = "users_datacollection_patient_id_9de40844_fk_users_customuser_id"

class Migration(migrations.Migration):
    dependencies = [
        ("users", "0060_cascade_assignedtask"),   # previous migration
    ]

    # MySQL autocommits each ALTER TABLE, so keep atomic off
    atomic = False

    operations = [
        # 1 – drop the old RESTRICT FK
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE users_datacollection
                  DROP FOREIGN KEY {FK};
            """
        ),
        # 2 – recreate it with ON DELETE CASCADE
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE users_datacollection
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
                  ON DELETE CASCADE;
            """,
            reverse_sql=f"""
                ALTER TABLE users_datacollection
                  DROP FOREIGN KEY {FK};
                ALTER TABLE users_datacollection
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
                  ON DELETE RESTRICT;
            """,
        ),
    ]