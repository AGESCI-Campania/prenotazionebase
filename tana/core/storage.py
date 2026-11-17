"""Storage dei file privati (ricevute dei bonifici, P-14).

I file stanno in PRIVATE_MEDIA_ROOT (`STORAGES["privato"]`), fuori da MEDIA_ROOT e senza URL
pubblico: si servono solo da una vista che controlla i permessi e risponde con X-Accel-Redirect.
"""

from django.core.files.storage import FileSystemStorage, Storage, storages


class StoragePrivato(FileSystemStorage):
    def url(self, name: str | None) -> str:
        # Senza base_url FileSystemStorage userebbe MEDIA_URL: un file privato non ha URL
        raise NotImplementedError("I file privati non hanno un URL pubblico.")


def storage_privato() -> Storage:
    # Callable: le migrazioni non dipendono dalle impostazioni dell'ambiente
    return storages["privato"]
