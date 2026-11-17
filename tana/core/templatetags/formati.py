"""Formati italiani per i template: importi in centesimi → euro."""

from django import template

from tana.core.formati import euro

register = template.Library()
register.filter("euro", euro)
