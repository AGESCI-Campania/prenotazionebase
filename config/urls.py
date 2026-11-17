"""URL di Tana.

Le pagine applicative hanno prefissi propri e vanno registrate PRIMA della rotta generica di
Wagtail, che serve la radice del sito della base (D-30). Prefissi riservati: /prenotazioni/,
/disponibilita/, /listino/, /gestione/, /accounts/ (allauth), /cms/ (editor), /django-admin/.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from tana.core import views as core_views
from tana.listini.views import listino
from tana.prenotazioni.views_pubbliche import disponibilita

urlpatterns = [
    path("healthz/", core_views.healthz, name="healthz"),
    path("manifest.webmanifest", core_views.manifest, name="manifest"),
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("senza-rete/", core_views.senza_rete, name="senza_rete"),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("cms/", include(wagtailadmin_urls)),
    path("documenti/", include(wagtaildocs_urls)),
    path("prenotazioni/", include("tana.prenotazioni.urls")),
    path("disponibilita/", disponibilita, name="disponibilita"),
    path("listino/", listino, name="listino"),
    path("gestione/", include("tana.gestione.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Sempre per ultima: tutto il resto è il sito della base in Wagtail
urlpatterns += [path("", include(wagtail_urls))]
