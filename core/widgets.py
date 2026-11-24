# -*- coding: utf-8 -*-
"""Widget de date utilisable au clavier comme avec le sélecteur natif (mobile inclus)."""
from django import forms
from django.forms.utils import flatatt
from django.utils.safestring import mark_safe


class SmartDateInput(forms.DateInput):
    """Champ texte « JJ/MM/AAAA » + bouton calendrier (input date natif).

    - la saisie manuelle fonctionne partout, y compris sur mobile ;
    - le calendrier natif reste disponible d'un simple clic ;
    - plusieurs formats sont acceptés : JJ/MM/AAAA, JJ-MM-AAAA, AAAA-MM-JJ.
    """

    input_type = 'text'

    def format_value(self, value):
        value = super().format_value(value)
        if not value:
            return ''
        text = str(value)
        if len(text) == 10 and text[4] == '-':
            return f'{text[8:10]}/{text[5:7]}/{text[:4]}'
        return text

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        final_attrs = self.build_attrs(attrs, {
            'type': 'text',
            'name': name,
            'value': self.format_value(value),
            'placeholder': 'JJ/MM/AAAA',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'class': 'form-input smart-date-text',
        })
        picker_attrs = self.build_attrs({
            'type': 'date',
            'class': 'smart-date-picker',
            'tabindex': '-1',
            'aria-hidden': 'true',
        })
        html = (
            '<span class="smart-date-wrap" style="display:flex;gap:.35rem;align-items:center">'
            f'<input{flatatt(final_attrs)}>'
            f'<input{flatatt(picker_attrs)}>'
            '<button type="button" class="smart-date-btn" title="Choisir une date" '
            'aria-label="Choisir une date"><i class="fas fa-calendar"></i></button>'
            '</span>'
        )
        script = ''
        if not getattr(self, '_smart_date_script_done', False):
            script = (
                '<script>\n'
                '(function(){\n'
                ' if(window.__siraSmartDate) return; window.__siraSmartDate=true;\n'
                ' document.addEventListener("click",function(e){\n'
                '  var btn=e.target.closest(".smart-date-btn"); if(!btn)return;\n'
                '  var wrap=btn.parentElement; var txt=wrap.querySelector(".smart-date-text");\n'
                '  var pk=wrap.querySelector(".smart-date-picker"); if(!pk)return;\n'
                '  var m=(txt.value||"").match(/^(\\d{2})\\/(\\d{2})\\/(\\d{4})$/);\n'
                '  if(m) pk.value=m[3]+"-"+m[2]+"-"+m[1];\n'
                '  if(pk.showPicker){try{pk.showPicker();return;}catch(err){}}\n'
                '  pk.focus(); pk.click();\n'
                ' });\n'
                ' document.addEventListener("change",function(e){\n'
                '  var pk=e.target; if(!pk.classList||!pk.classList.contains("smart-date-picker"))return;\n'
                '  var txt=pk.parentElement.querySelector(".smart-date-text");\n'
                '  if(txt && pk.value){var p=pk.value.split("-");txt.value=p[2]+"/"+p[1]+"/"+p[0];}\n'
                ' });\n'
                '})();\n'
                '</script>'
            )
            type(self)._smart_date_script_done = True
        return mark_safe(html + script)
