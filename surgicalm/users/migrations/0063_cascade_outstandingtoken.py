# users/migrations/0063_cascade_outstandingtoken.py
from django.db import migrations

FK = "token_blacklist_outs_user_id_83bc629a_fk_users_cus"

class Migration(migrations.Migration):
    dependencies = [
        ("users", "0062_cascade_watcheddata"),   # previous migration
    ]

    # MySQL autocommits each ALTER TABLE
    atomic = False

    operations = [
        # 1 – drop the current RESTRICT FK
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE token_blacklist_outstandingtoken
                  DROP FOREIGN KEY {FK};
            """
        ),
        # 2 – recreate with ON DELETE CASCADE
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE token_blacklist_outstandingtoken
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (user_id) REFERENCES users_customuser(id)
                  ON DELETE CASCADE;
            """,
            reverse_sql=f"""
                ALTER TABLE token_blacklist_outstandingtoken
                  DROP FOREIGN KEY {FK};
                ALTER TABLE token_blacklist_outstandingtoken
                  ADD CONSTRAINT {FK}
                  FOREIGN KEY (user_id) REFERENCES users_customuser(id)
                  ON DELETE RESTRICT;
            """,
        ),
    ]