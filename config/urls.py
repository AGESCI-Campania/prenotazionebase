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

urlpatterns = [
    path("healthz/", core_views.healthz, name="healthz"),
    path("django-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("cms/", include(wagtailadmin_urls)),
    path("documenti/", include(wagtaildocs_urls)),
    # Qui, in F1–F5: prenotazioni/, disponibilita/, listino/, gestione/
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Sempre per ultima: tutto il resto è il sito della base in Wagtail
urlpatterns += [path("", include(wagtail_urls))]
