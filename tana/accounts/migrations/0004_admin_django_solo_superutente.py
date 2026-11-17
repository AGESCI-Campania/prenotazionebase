from django.db import migrations


def togli_staff(apps, schema_editor):
    """Nell'admin Django resta solo il superutente: i ruoli lavorano in gestione ed editor."""
    User = apps.get_model("accounts", "User")
    User.objects.filter(is_staff=True, is_superuser=False).update(is_staff=False)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_avatar_sestante")]

    operations = [migrations.RunPython(togli_staff, migrations.RunPython.noop)]
