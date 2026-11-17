"""Backend SMTP con il nome EHLO configurabile.

Il backend SMTP di Django si presenta al server con `socket.getfqdn()`, che nel container è il suo
ID: il relay di Google Workspace (`smtp-relay.gmail.com`) può rifiutare un EHLO che non sia un nome
di dominio completo. Con l'opzione `local_hostname` (variabile `EMAIL_EHLO`) si usa quel nome.
"""

from typing import Any

from django.core.mail.backends import smtp


class EmailBackend(smtp.EmailBackend):
    def __init__(self, *args: Any, local_hostname: str = "", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.local_hostname = local_hostname

    @property
    def connection_class(self) -> Any:
        classe = super().connection_class
        if not self.local_hostname:
            return classe
        nome = self.local_hostname

        def connetti(*args: Any, **kwargs: Any) -> Any:
            return classe(*args, **{**kwargs, "local_hostname": nome})

        return connetti
