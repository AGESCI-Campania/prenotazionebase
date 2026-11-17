from django.contrib import admin

from .models import Area, Configurazione


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("nome", "codice", "capienza", "unita_capienza", "ordine")


@admin.register(Configurazione)
class ConfigurazioneAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not Configurazione.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
