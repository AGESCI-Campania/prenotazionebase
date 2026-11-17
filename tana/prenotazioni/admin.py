from django.contrib import admin

from .models import (
    AttivitaGiornaliera,
    BloccoTecnico,
    Contatto,
    Messaggio,
    Occupazione,
    Pagamento,
    Prenotazione,
    PresenzaArea,
    RichiestaConsenso,
    RigaImporto,
)

# Admin tecnico di consultazione: le modifiche passano dai servizi (aree di gestione, F5).
# Occupazioni sola lettura: si derivano dalle prenotazioni e dai blocchi.


class SolaLettura:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PresenzaAreaInline(admin.TabularInline):
    model = PresenzaArea
    extra = 0


class OccupazioneInline(SolaLettura, admin.TabularInline):
    model = Occupazione
    fields = ("tipo", "area", "periodo", "attiva")
    readonly_fields = fields
    extra = 0


class AttivitaGiornalieraInline(admin.TabularInline):
    model = AttivitaGiornaliera
    extra = 0


@admin.register(Prenotazione)
class PrenotazioneAdmin(admin.ModelAdmin):
    list_display = ("numero", "gruppo", "categoria", "arrivo", "partenza", "stato")
    list_filter = ("stato", "categoria")
    search_fields = ("numero", "gruppo", "contatto__nome", "contatto__email", "id_supersaas")
    date_hierarchy = "arrivo"
    readonly_fields = ("numero", "id_supersaas", "creata_il", "aggiornata_il")
    inlines = (PresenzaAreaInline, AttivitaGiornalieraInline, OccupazioneInline)


@admin.register(Occupazione)
class OccupazioneAdmin(SolaLettura, admin.ModelAdmin):
    list_display = ("area", "periodo", "tipo", "attiva", "prenotazione", "blocco")
    list_filter = ("area", "tipo", "attiva")


@admin.register(BloccoTecnico)
class BloccoTecnicoAdmin(SolaLettura, admin.ModelAdmin):
    list_display = ("area", "dal", "al", "motivo", "creato_da")


@admin.register(Contatto)
class ContattoAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "telefono", "organizzazione")
    search_fields = ("nome", "email", "organizzazione")


@admin.register(RichiestaConsenso)
class RichiestaConsensoAdmin(admin.ModelAdmin):
    list_display = ("richiesta", "prenotazione_esistente", "stato", "scadenza")
    list_filter = ("stato",)


@admin.register(RigaImporto)
class RigaImportoAdmin(admin.ModelAdmin):
    list_display = ("prenotazione", "fase", "descrizione", "quantita", "importo_centesimi")
    list_filter = ("fase", "rettifica")


@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ("prenotazione", "tipo", "importo_centesimi", "data")
    list_filter = ("tipo",)
    exclude = ("ricevuta",)  # file privato: solo dalla vista con controllo dei permessi


@admin.register(Messaggio)
class MessaggioAdmin(admin.ModelAdmin):
    list_display = ("prenotazione", "mittente", "destinatario", "inviato_il", "letto")
