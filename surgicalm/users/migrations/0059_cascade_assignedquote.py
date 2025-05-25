from django.db import migrations

FK = "users_assignedquote_patient_id_8ff02264_fk_users_customuser_id"

class Migration(migrations.Migration):
    dependencies = [("users", "0058_cascade_assignedmodules")]
    atomic = False

    operations = [
        migrations.RunSQL(f"""
            ALTER TABLE users_assignedquote
              DROP FOREIGN KEY {FK};
        """),
        migrations.RunSQL(
            sql=f"""
            ALTER TABLE users_assignedquote
              ADD CONSTRAINT {FK}
              FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
              ON DELETE CASCADE;
            """,
            reverse_sql=f"""
            ALTER TABLE users_assignedquote
              DROP FOREIGN KEY {FK};
            ALTER TABLE users_assignedquote
              ADD CONSTRAINT {FK}
              FOREIGN KEY (patient_id) REFERENCES users_customuser(id)
              ON DELETE RESTRICT;
            """,
        ),
    ]