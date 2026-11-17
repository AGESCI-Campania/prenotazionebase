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
