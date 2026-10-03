from django.db import migrations


INDEX_NAME = 'aquawatch_unique_account_email'


def enforce_unique_email(apps, schema_editor):
    # auth.User is owned by Django, so keep our index in an explicit migration.
    User = apps.get_model('auth', 'User')
    users = User.objects.using(schema_editor.connection.alias)
    seen = {}
    changes = []
    duplicate_ids = set()
    for user_id, email in users.values_list('pk', 'email').iterator():
        normalized = email.strip().lower()
        if normalized:
            if normalized in seen:
                duplicate_ids.update((seen[normalized], user_id))
            else:
                seen[normalized] = user_id
        if email != normalized:
            changes.append((user_id, normalized))
    if duplicate_ids:
        identifiers = ', '.join(str(pk) for pk in sorted(duplicate_ids))
        raise RuntimeError(
            'Cannot enforce unique email: existing accounts share an email '
            f'(user IDs: {identifiers}). Assign distinct verified emails to these '
            'accounts, then rerun migrate. No accounts were deleted or merged.'
        )
    for user_id, normalized in changes:
        users.filter(pk=user_id).update(email=normalized)
    quote = schema_editor.quote_name
    table = quote(User._meta.db_table)
    email_column = quote(User._meta.get_field('email').column)
    # Blank emails remain available for legacy accounts without an address.
    schema_editor.execute(
        f'CREATE UNIQUE INDEX {quote(INDEX_NAME)} ON {table} '
        f'(LOWER(TRIM({email_column}))) WHERE TRIM({email_column}) <> \'\''
    )


def remove_unique_email(apps, schema_editor):
    schema_editor.execute(f'DROP INDEX {schema_editor.quote_name(INDEX_NAME)}')


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('aquawatch_app', '0004_devicereading_mobileauthwindow_mobiletoken_and_more'),
    ]

    operations = [migrations.RunPython(enforce_unique_email, remove_unique_email)]
