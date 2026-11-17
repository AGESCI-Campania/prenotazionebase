from django.urls import path

from . import views

app_name = "prenotazioni"

urlpatterns = [
    path("", views.elenco, name="elenco"),
    path("nuova/", views.nuova, name="nuova"),
    path("nuova/<int:passo>/", views.nuova, name="nuova_passo"),
    path("nuova/anteprima/", views.anteprima, name="anteprima"),
    path("consensi/<int:pk>/", views.rispondi_consenso, name="rispondi_consenso"),
    path("telefono/<int:pk>/", views.rispondi_telefono, name="rispondi_telefono"),
    path("<str:numero>/", views.dettaglio, name="dettaglio"),
    path("<str:numero>/ricevuta/", views.carica_ricevuta, name="carica_ricevuta"),
    path("<str:numero>/ricevute/<int:pk>/", views.ricevuta, name="ricevuta"),
    path("<str:numero>/documenti/<str:tipo>/", views.documento, name="documento"),
    path("<str:numero>/annulla/", views.annulla, name="annulla"),
    path("<str:numero>/messaggi/", views.scrivi, name="scrivi"),
    path("<str:numero>/telefono/<str:altro>/", views.chiedi_telefono, name="chiedi_telefono"),
]
