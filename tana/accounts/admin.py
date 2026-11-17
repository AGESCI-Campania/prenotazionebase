from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Nomina, User
from .services import allinea_gruppi


class NominaInline(admin.TabularInline):
    model = Nomina
    fk_name = "utente"
    extra = 0
    fields = ("ruolo", "da_sso", "attiva", "assegnata_da", "assegnata_il")
    readonly_fields = ("da_sso", "assegnata_da", "assegnata_il")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dati personali", {"fields": ("first_name", "last_name")}),
        (
            "Permessi",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Date", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    inlines = (NominaInline,)

    def save_formset(self, request, form, formset, change):
        for istanza in formset.save(commit=False):
            if isinstance(istanza, Nomina) and not istanza.pk:
                istanza.assegnata_da = request.user
            istanza.save()
        for eliminata in formset.deleted_objects:
            eliminata.delete()
        formset.save_m2m()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # I gruppi dei ruoli seguono le nomine (anche se modificati a mano nel form)
        allinea_gruppi(form.instance)
