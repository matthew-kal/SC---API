# users/migrations/0062_cascade_watcheddata.py
from django.db import migrations

FK = "users_watcheddata_user_id_021b741f_fk_users_customuser_id"

class Migration(migrations.Migration):
    dependencies = [
        ("users", "0061_cascade_datacollection"),   # previous migration
    ]

    # MySQL autocommits ALTER TABLE statements
    atomic = False

    operations = [
        # 1 – drop the existing RESTRICT FK
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE users_watcheddata
                  DROP FOREIGN KEY {FK};
            """
        ),
        # 2 – add the FK back with ON DELETE CASCADE
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE users_watcheddata
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (user_id) REFERENCES users_customuser(id)
                  ON DELETE CASCADE;
            """,
            reverse_sql=f"""
                ALTER TABLE users_watcheddata
                  DROP FOREIGN KEY {FK};
                ALTER TABLE users_watcheddata
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (user_id) REFERENCES users_customuser(id)
                  ON DELETE RESTRICT;
            """,
        ),
    ]
