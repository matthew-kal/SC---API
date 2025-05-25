#users/migrations/0064_cascade_blacklistedtoken.py
from django.db import migrations

FK = "token_blacklist_blacklistedtoken_token_id_3cc7fe56_fk"

class Migration(migrations.Migration):
    dependencies = [
        ("users", "0063_cascade_outstandingtoken"),   # latest applied migration
    ]
    atomic = False        # MySQL autocommits ALTER TABLE

    operations = [
        # drop the old RESTRICT FK
        migrations.RunSQL(f"""
            ALTER TABLE token_blacklist_blacklistedtoken
              DROP FOREIGN KEY {FK};
        """),
        # add it back with ON DELETE CASCADE
        migrations.RunSQL(
            sql=f"""
            ALTER TABLE token_blacklist_blacklistedtoken
              ADD CONSTRAINT {FK}
              FOREIGN KEY (token_id) REFERENCES token_blacklist_outstandingtoken(id)
              ON DELETE CASCADE;
            """,
            reverse_sql=f"""
            ALTER TABLE token_blacklist_blacklistedtoken
              DROP FOREIGN KEY {FK};
            ALTER TABLE token_blacklist_blacklistedtoken
              ADD CONSTRAINT {FK}
              FOREIGN KEY (token_id) REFERENCES token_blacklist_outstandingtoken(id)
              ON DELETE RESTRICT;
            """,
        ),
    ]