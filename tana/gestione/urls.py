from django.urls import path

from . import views

app_name = "gestione"

urlpatterns = [
    path("", views.cruscotto, name="cruscotto"),
    path("prenotazioni/", views.elenco, name="elenco"),
    path("prenotazioni/nuova/", views.nuova, name="nuova"),
    path("prenotazioni/<str:numero>/", views.scheda, name="scheda"),
    path("prenotazioni/<str:numero>/consuntivo/", views.consuntivo, name="consuntivo"),
    path("prenotazioni/<str:numero>/chiudi/", views.chiudi, name="chiudi"),
    path("prenotazioni/<str:numero>/<str:nome>/", views.azione, name="azione"),
    path("calendario/", views.calendario, name="calendario"),
    path("arrivi/", views.arrivi, name="arrivi"),
    path("blocchi/", views.blocchi, name="blocchi"),
    path("listini/", views.listini, name="listini"),
    path("listini/versioni/<int:pk>/", views.versione, name="versione"),
    path("configurazione/", views.configurazione, name="configurazione"),
    path("utenti/", views.utenti, name="utenti"),
    path("statistiche/", views.statistiche_anno, name="statistiche"),
    path("export/", views.esporta, name="export"),
]
