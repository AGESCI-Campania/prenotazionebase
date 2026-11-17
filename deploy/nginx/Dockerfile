# Immagine dell'nginx interno di Tana: configurazione dentro l'immagine (come Plancia), così una
# release che la cambia ricostruisce e ricrea il container con scripts/aggiorna.sh.
FROM nginx:1.30.6-alpine
COPY default.conf.template proxy-django.inc /etc/nginx/templates/
COPY manutenzione.html /usr/share/nginx/tana/
