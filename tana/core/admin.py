from django.contrib import admin

from .models import Manutenzione


@admin.register(Manutenzione)
class ManutenzioneAdmin(admin.ModelAdmin):
    list_display = ("attiva", "messaggio", "aggiornata_il")
