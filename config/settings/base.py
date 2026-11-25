"""Impostazioni comuni di Tana. Valori da variabili d'ambiente (.env / .env.dev)."""

import os
from pathlib import Path

import environ
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# In sviluppo e nei test le variabili stanno in .env.dev; in produzione arrivano solo da
# docker compose (.env), mai da .env.dev
if not os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith(".prod"):
    environ.Env.read_env(BASE_DIR / ".env.dev", overwrite=False)

SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
BASE_URL = env.str("BASE_URL", default="http://localhost:8000")

INSTALLED_APPS = [
    # Tana
    "tana.core",
    "tana.accounts",
    "tana.base",
    "tana.listini",
    "tana.prenotazioni",
    "tana.gestione",
    "tana.sito",
    "tana.aggiornamenti",
    # Tema regionale (prima di allauth e dell'admin: sovrascrive i loro template)
    "agesci_theme",
    # Wagtail (sito della base, D-30)
    "wagtail.contrib.forms",
    "wagtail.contrib.settings",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.postgres",
    # Autenticazione (D-15, D-28)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.openid_connect",
    "allauth.mfa",
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "tana.accounts.middleware.MFAObbligatoriaMiddleware",
    "tana.core.middleware.ManutenzioneMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "axes.middleware.AxesMiddleware",
]

# CSP uguale in sviluppo, test e produzione (le violazioni si vedono subito in locale).
# Il tema 3.0.0a5 carica Bootstrap 6 da jsDelivr e i font da Google Fonts (base.html del tema)
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.UNSAFE_INLINE, "https://cdn.jsdelivr.net"],
    "style-src": [
        CSP.SELF,
        CSP.UNSAFE_INLINE,
        "https://cdn.jsdelivr.net",
        "https://fonts.googleapis.com",
    ],
    "img-src": [CSP.SELF, "data:", "https:"],
    "font-src": [CSP.SELF, "data:", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net"],
    "connect-src": [CSP.SELF],
    "frame-src": [CSP.SELF, "https://www.google.com", "https://www.openstreetmap.org"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF, "https://auth.agescicampania.net"],
    "frame-ancestors": [CSP.SELF],
}

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "agesci_theme.context_processors.agesci_theme",
                "tana.core.context_processors.manuale",
                "tana.gestione.context_processors.menu",
                "tana.sito.context_processors.menu",
                "wagtail.contrib.settings.context_processors.settings",
            ],
        },
    }
]
FORM_RENDERER = "agesci_theme.forms.AgesciFormRenderer"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # per primo: blocco dei tentativi ripetuti
    # Con password: mai gli account di gestione, che entrano solo con Sestante (P-13)
    "tana.accounts.backends.TanaModelBackend",
    "tana.accounts.backends.TanaAllauthBackend",
]

LANGUAGE_CODE = "it"
LANGUAGES = [("it", "Italiano")]
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Media pubblici (immagini e documenti di Wagtail). Gli allegati privati (ricevute) stanno in
# PRIVATE_MEDIA_ROOT e si servono solo con X-Accel-Redirect dopo il controllo dei permessi (P-14).
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env.str("MEDIA_ROOT", default=str(BASE_DIR / "media")))
PRIVATE_MEDIA_ROOT = Path(env.str("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "privati")))
# In produzione i file privati li serve nginx (X-Accel-Redirect verso la location internal
# /protetti/); in sviluppo e nei test li serve Django dopo lo stesso controllo dei permessi.
PRIVATI_X_ACCEL = False
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "privato": {
        "BACKEND": "tana.core.storage.StoragePrivato",
        "OPTIONS": {"location": PRIVATE_MEDIA_ROOT},
    },
    # Nomi con hash anche per le icone della PWA (cache delle icone su iOS, D-22)
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- Tema regionale (D-21, P-08) --------------------------------------------------------
AGESCI_THEME_BRANCA = "eg"  # base verde, ricolorata con la palette della base in tana.css
AGESCI_THEME_NOME = "Base Scout «Gianni Sabatino»"
AGESCI_THEME_LOGO_NAVBAR = "tana/img/logo/lupo-base-aiello.svg"

# --- Wagtail (D-30) ---------------------------------------------------------------------
WAGTAIL_SITE_NAME = "Base Scout «Gianni Sabatino»"
WAGTAILADMIN_BASE_URL = BASE_URL
WAGTAIL_I18N_ENABLED = False
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}
WAGTAILDOCS_EXTENSIONS = ["pdf"]
# Gravatar sempre in https (il default «//» in http locale viola la CSP, img-src https:)
WAGTAIL_GRAVATAR_PROVIDER_URL = "https://www.gravatar.com/avatar"
# Editor (P-15) con il login di Tana (Sestante o superutente); password gestite da allauth
WAGTAILADMIN_LOGIN_URL = "account_login"
# Chi è già collegato ma non può entrare nell'editor vede la pagina di accesso (per cambiare
# utente) invece di essere rimandato all'editor: niente ciclo di reindirizzamenti
ACCOUNT_AUTHENTICATED_LOGIN_REDIRECTS = False
WAGTAIL_PASSWORD_MANAGEMENT_ENABLED = False
WAGTAIL_PASSWORD_RESET_ENABLED = False

# --- allauth (D-15, D-28) ---------------------------------------------------------------
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
LOGIN_REDIRECT_URL = "/"
SOCIALACCOUNT_AUTO_SIGNUP = False  # auto-signup solo per Sestante, nell'adapter
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
ACCOUNT_ADAPTER = "tana.accounts.adapters.TanaAccountAdapter"
SOCIALACCOUNT_ADAPTER = "tana.accounts.adapters.TanaSocialAccountAdapter"
MFA_ADAPTER = "tana.accounts.adapters.TanaMFAAdapter"
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Tana – Base Scout Aiello"

# Sestante (SSO AGESCI Campania): senza client id il provider non si configura e il pulsante
# non compare, ma l'app parte comunque (contratto INTEGRAZIONE-SSO.md di Sestante).
SOCIAL_SESTANTE_CLIENT_ID = env.str("SOCIAL_SESTANTE_CLIENT_ID", default="")
SOCIAL_SESTANTE_CLIENT_SECRET = env.str("SOCIAL_SESTANTE_CLIENT_SECRET", default="")
# Senza "/" finale: allauth aggiunge "/.well-known/openid-configuration" e con la doppia barra
# Sestante (authentik) risponde 404, cioè errore 500 al clic su «Accedi con SSO» (come Plancia).
SOCIAL_SESTANTE_SERVER_URL = env.str(
    "SOCIAL_SESTANTE_SERVER_URL",
    default="https://auth.agescicampania.net/application/o/tana",
).rstrip("/")
# Token dell'account di servizio svc-tana per gli inviti su Sestante (contratto SSO § 10):
# vuoto = nessun invito, chi riceve un ruolo si fa creare l'account dalla segreteria regionale
SESTANTE_INVITI_TOKEN = env.str("SESTANTE_INVITI_TOKEN", default="")
SOCIALACCOUNT_PROVIDERS: dict = {}
if SOCIAL_SESTANTE_CLIENT_ID:
    SOCIALACCOUNT_PROVIDERS["openid_connect"] = {
        "APPS": [
            {
                "provider_id": "sestante",
                "name": "SSO AGESCI Campania",
                "client_id": SOCIAL_SESTANTE_CLIENT_ID,
                "secret": SOCIAL_SESTANTE_CLIENT_SECRET,
                "settings": {
                    "server_url": SOCIAL_SESTANTE_SERVER_URL,
                    # avatar: immagine del profilo (claim `picture`, tana.accounts.avatar)
                    "scope": ["openid", "profile", "email", "avatar"],
                },
            }
        ]
    }

# --- django-axes ------------------------------------------------------------------------
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = 1  # ore
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]

# --- Email (D-29) -----------------------------------------------------------------------
# Mailer di Django 6.1: "default" lo usano allauth, Wagtail, mail_admins e chi non indica
# `using`. Le impostazioni EMAIL_HOST & co. sono deprecate (con MAILERS sono un errore); le
# variabili d'ambiente omonime restano e finiscono qui.
MAILERS = {
    "default": {
        # SMTP di Django con il nome EHLO configurabile (relay di Google Workspace)
        "BACKEND": "tana.core.mail.EmailBackend",
        "OPTIONS": {
            "host": env.str("EMAIL_HOST", default="localhost"),
            "port": env.int("EMAIL_PORT", default=587),
            "username": env.str("EMAIL_HOST_USER", default=""),
            "password": env.str("EMAIL_HOST_PASSWORD", default=""),
            "use_tls": env.bool("EMAIL_USE_TLS", default=True),
            "local_hostname": env.str("EMAIL_EHLO", default=""),
        },
    }
}
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="Tana <prenotazioni@agescicampania.net>")
SERVER_EMAIL = env.str("SERVER_EMAIL", default="prenotazioni@agescicampania.net")
EMAIL_REPLY_TO = env.str("EMAIL_REPLY_TO", default="baseaiellodelsabato@campania.agesci.it")
ADMINS = env.list("ADMIN_EMAILS", default=[])  # indirizzi, non più coppie (nome, email)

# --- Aggiornamento dal web (P-20) -------------------------------------------------------
# Bind mount di /opt/prenotazionebase/aggiornamenti: Django scrive solo richiesta.json
# Manuale d'uso su Read the Docs: la versione dell'ultima release, link nel footer e nella gestione
MANUALE_URL = "https://baseaiello.readthedocs.io/it/stable/"

AGGIORNAMENTI_DIR = BASE_DIR / "aggiornamenti"
AGGIORNAMENTI_CONTROLLO_RELEASE = True  # controllo giornaliero dell'ultima release su GitHub

# --- Scheduler (P-07, P-11) -------------------------------------------------------------
SCHEDULER_INTERVALLO = env.int("SCHEDULER_INTERVALLO", default=300)  # secondi
SCHEDULER_BATTITO = Path(env.str("SCHEDULER_BATTITO", default="/tmp/tana-scheduler-battito"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"semplice": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "semplice"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
