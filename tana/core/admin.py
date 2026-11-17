from django.contrib import admin

from .models import EventoStorico, Manutenzione


@admin.register(Manutenzione)
class ManutenzioneAdmin(admin.ModelAdmin):
    list_display = ("attiva", "messaggio", "aggiornata_il")


@admin.register(EventoStorico)
class EventoStoricoAdmin(admin.ModelAdmin):
    list_display = ("creato_il", "azione", "content_type", "object_id", "utente", "deciso_da")
    list_filter = ("content_type",)
    search_fields = ("azione", "deciso_da", "motivazione", "object_id")

    # Lo storico non si modifica a mano
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
