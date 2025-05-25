# users/migrations/0060_cascade_assignedtask.py
from django.db import migrations

FK = "users_assignedtask_patient_id_6edc28fd_fk_users_customuser_id"

class Migration(migrations.Migration):
    dependencies = [
        ("users", "0059_cascade_assignedquote"),   # previous migration
    ]

    # MySQL autocom-mits each ALTER TABLE, so leave atomic off
    atomic = False

    operations = [
        # 1 – drop the old FK (RESTRICT)
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE users_assignedtask
                  DROP FOREIGN KEY {FK};
            """
        ),
        # 2 – add the same-named FK with ON DELETE CASCADE
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE users_assignedtask
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
                  ON DELETE CASCADE;
            """,
            reverse_sql=f"""
                ALTER TABLE users_assignedtask
                  DROP FOREIGN KEY {FK};
                ALTER TABLE users_assignedtask
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
                  ON DELETE RESTRICT;
            """,
        ),
    ]