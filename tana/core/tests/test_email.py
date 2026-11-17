import logging

from django.conf import DEPRECATED_EMAIL_SETTINGS, settings
from django.core import mail
from django.core.mail import EmailMessage
from django.utils.log import AdminEmailHandler


def test_nessuna_impostazione_email_deprecata():
    assert "default" in settings.MAILERS
    assert not [nome for nome in DEPRECATED_EMAIL_SETTINGS if settings.is_overridden(nome)]


def test_invio_con_il_mailer_di_default():
    EmailMessage("Prova", "Testo", to=["referente@example.org"]).send()
    mail.send_mail("Seconda", "Testo", None, ["referente@example.org"])
    assert [m.subject for m in mail.outbox] == ["Prova", "Seconda"]
    assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL


def test_errori_agli_amministratori(settings):
    settings.ADMINS = ["admin@example.org"]
    record = logging.makeLogRecord({"msg": "Errore di prova", "levelno": logging.ERROR})
    AdminEmailHandler().emit(record)
    assert mail.outbox[-1].to == ["admin@example.org"]


class _SMTPFinto:
    """Registra i parametri di connessione al posto di smtplib.SMTP."""

    connessioni: list[dict] = []

    def __init__(self, host, port, **kwargs):
        _SMTPFinto.connessioni.append({"host": host, "port": port, **kwargs})

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def quit(self):
        pass


def _apri(monkeypatch, **opzioni):
    from django.core.mail.backends import smtp

    from tana.core.mail import EmailBackend

    _SMTPFinto.connessioni = []
    monkeypatch.setattr(smtp.smtplib, "SMTP", _SMTPFinto)
    backend = EmailBackend(
        alias="prova", host="smtp-relay.gmail.com", port=587, use_tls=True, **opzioni
    )
    backend.open()
    backend.close()
    return _SMTPFinto.connessioni[0]


def test_ehlo_configurabile(monkeypatch):
    connessione = _apri(monkeypatch, local_hostname="srv2.agescicampania.net")
    assert connessione["local_hostname"] == "srv2.agescicampania.net"
    assert (connessione["host"], connessione["port"]) == ("smtp-relay.gmail.com", 587)


def test_ehlo_di_default(monkeypatch):
    from django.core.mail.utils import DNS_NAME

    assert _apri(monkeypatch)["local_hostname"] == DNS_NAME.get_fqdn()


def test_mailer_di_produzione_usa_il_backend_di_tana():
    import importlib

    import config.settings.base as base

    importlib.reload(base)
    assert base.MAILERS["default"]["BACKEND"] == "tana.core.mail.EmailBackend"
    assert "local_hostname" in base.MAILERS["default"]["OPTIONS"]
