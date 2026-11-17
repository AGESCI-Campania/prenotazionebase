#!/usr/bin/env bash
# Prima installazione di Tana sul server (modello: scripts/installa.sh di Plancia 3.0).
# Prerequisito: agesci-campania-web-frontend già installato (rete agesci-proxy esistente).
# Guida completa: docs/installazione.md.
#
# Uso:  scripts/installa.sh
#       TANA_ADMIN_EMAIL=x@y scripts/installa.sh   (senza domande)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_comune.sh
source scripts/_tana.sh

richiedi_comandi docker git openssl
docker network inspect "$RETE_PROXY" >/dev/null 2>&1 \
	|| errore "Rete $RETE_PROXY mancante: installare prima agesci-campania-web-frontend."
(( EUID != 0 )) || errore "Non eseguire come root: entrare come agesci (sudo -iu agesci)."

# --- .env ---
# Si può preparare .env prima (cp .env.template .env, indirizzo corretto): i segreti vuoti li
# genera lo script; quelli già presenti non si toccano mai.
if [[ -f .env ]]; then
	info ".env già presente: completo solo i segreti vuoti."
else
	info "Creo .env da .env.template."
	cp .env.template .env
fi
chmod 600 .env
if [[ -z "$(leggi_var DJANGO_SECRET_KEY)" ]]; then
	imposta_var DJANGO_SECRET_KEY "$(openssl rand -base64 60 | tr -d '\n')"
	info "Generata DJANGO_SECRET_KEY."
fi
if [[ -z "$(leggi_var POSTGRES_PASSWORD)" ]]; then
	# Finisce dentro DATABASE_URL: niente / + = che andrebbero codificati
	imposta_var POSTGRES_PASSWORD "$(openssl rand -base64 36 | tr -d '\n/+=')"
	info "Generata POSTGRES_PASSWORD."
fi
for v in DJANGO_SECRET_KEY POSTGRES_PASSWORD ALLOWED_HOSTS CSRF_TRUSTED_ORIGINS BASE_URL; do
	[[ -n "$(leggi_var "$v")" ]] || errore "$v vuota in .env."
done
controlla_var_nuove

# --- Versione: si installa una release (tag vX.Y.Z), poi si aggiorna con scripts/aggiorna.sh ---
git fetch --tags --quiet || avviso "Non riesco a scaricare i tag da GitHub."
if ! git describe --tags --exact-match --match 'v[0-9]*' >/dev/null 2>&1; then
	ultima="$(git tag -l 'v[0-9]*' --sort=-v:refname | head -1)"
	avviso "Il repo non è su una release (tag vX.Y.Z)."
	[[ -z "$ultima" ]] || avviso "Ultima release: $ultima (git checkout $ultima e rilanciare)."
fi

# --- Cartelle (create dall'utente del repo: i container girano con lo stesso uid) ---
mkdir -p logs backups aggiornamenti

# --- Avvio (le migrazioni le applica l'entrypoint del container web) ---
info "Costruisco le immagini di Tana e scarico le altre."
costruisci_immagini --pull
docker compose pull --ignore-buildable
docker compose up -d
attendi_salute 600 "${SERVIZI_SALUTE[@]}"

# --- Dominio del Site Django (link nelle email di allauth) e dati iniziali ---
dominio="$(leggi_var ALLOWED_HOSTS | cut -d, -f1)"
manage shell -c "from django.contrib.sites.models import Site; Site.objects.update_or_create(pk=1, defaults={'domain': '$dominio', 'name': 'Tana'})"
info "Site Django impostato su $dominio."
manage dati_iniziali

# --- Superutente tecnico di emergenza (P-13): solo se non ne esiste nessuno ---
password_admin=""
email_admin=""
if [[ "$(manage shell -c 'from tana.accounts.models import User; print(User.objects.filter(is_superuser=True).exists())' | tail -n 1)" != "True" ]]; then
	email_admin="${TANA_ADMIN_EMAIL:-}"
	[[ -n "$email_admin" ]] || read -rp "Email del superutente di emergenza di Tana: " email_admin
	[[ -n "$email_admin" ]] || errore "Email del superutente obbligatoria."
	password_admin="$(openssl rand -base64 18 | tr -d '\n')"
	# -e senza valore: la password passa dall'ambiente, non dalla riga di comando
	DJANGO_SUPERUSER_PASSWORD="$password_admin" docker compose exec -T -e DJANGO_SUPERUSER_PASSWORD web \
		uv run python manage.py createsuperuser --noinput --email "$email_admin"
	info "Creato il superutente di emergenza $email_admin."
else
	info "Esiste già un superutente, non ne creo altri."
fi

# --- Avvio automatico al boot (dopo il reverse proxy) e backup notturno ---
# Sestante non è una dipendenza d'avvio: serve solo al login.
installa_servizio_systemd prenotazionebase "$UNIT_PROXY"
installa_backup_systemd
installa_aggiornamenti_systemd

cat <<EOF

Tana è attiva (rete $RETE_PROXY, alias tana-nginx:80).
EOF
if [[ -n "$password_admin" ]]; then
	cat <<EOF

  Superutente di emergenza:  $email_admin  /  $password_admin
  (mostrata solo ora: annotarla in un luogo sicuro; al primo accesso va configurata la MFA)
EOF
fi
mancanti="$(credenziali_mancanti | tr '\n' ' ')"
if [[ -n "$mancanti" ]]; then
	avviso "Variabili ancora vuote in .env: $mancanti"
fi
cat <<EOF

Passi successivi (dettagli in docs/installazione.md):
  0. Avvio al boot e backup: systemctl status prenotazionebase prenotazionebase-backup.timer
     (se sopra sono indicati comandi per l'amministratore, vanno eseguiti da un utente sudoer)
  1. DNS: ${dominio} → IP di questo server
  2. In agesci-campania-web-frontend aggiungere caddy/sites/tana.caddy:

       # Tana — Prenotazioni e sito della Base Scout «Gianni Sabatino»
       # Repo: https://github.com/AGESCI-Campania/prenotazionebase
       ${dominio} {
       	import comune
       	reverse_proxy tana-nginx:80
       }

     più la riga del registro progetti in docs/INTEGRAZIONE.md, commit, push, poi
     /opt/agesci-campania-web-frontend/scripts/aggiorna.sh
  3. SSO Sestante: blueprint provider-tana.yaml applicato nel repo sestante, poi client ID e
     secret da https://auth.agescicampania.net/if/admin/#/core/providers → Tana → modifica
     in .env come SOCIAL_SESTANTE_CLIENT_ID e SOCIAL_SESTANTE_CLIENT_SECRET, poi docker compose up -d
     (callback: https://${dominio}/accounts/oidc/sestante/login/callback/)
  4. Email (EMAIL_HOST_USER, EMAIL_HOST_PASSWORD) e ADMIN_EMAILS in .env, poi docker compose up -d
  5. https://${dominio}/django-admin/ — accesso come superutente, MFA
  6. Configurazione iniziale nel backend e import da SuperSaaS (docs/installazione.md)
EOF
