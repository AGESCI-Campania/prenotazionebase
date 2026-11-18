"""Il messaggio della modalità demo nelle pagine senza contesto proprio (es. allauth)."""

from django import template

from tana.prenotazioni import demo

register = template.Library()
register.simple_tag(demo.messaggio, name="messaggio_demo")
