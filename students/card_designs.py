# -*- coding: utf-8 -*-
"""Modèles de carte scolaire."""

CARD_DESIGNS = {
    'mali': {
        'label': 'Carte d\'identité scolaire (Mali)',
        'top': (30, 64, 175),
        'bottom': (255, 255, 255),
        'accent': (30, 64, 175),
        'status': (30, 64, 175),
        'band': (30, 64, 175),
        'style': 'mali',
    },
    'official': {
        'label': 'Officiel (fond blanc)',
        'top': (30, 64, 175),
        'bottom': (255, 255, 255),
        'accent': (220, 38, 38),
        'status': (30, 64, 175),
        'band': (185, 28, 28),
        'style': 'mali',  # utilise le même rendu Mali
    },
    'modern': {
        'label': 'Moderne (bleu nuit)',
        'top': (30, 64, 175),
        'bottom': (15, 23, 42),
        'accent': (251, 191, 36),
        'status': (16, 185, 129),
        'band': (251, 191, 36),
        'style': 'mali',
    },
}


def get_design(key):
    return CARD_DESIGNS.get(key) or CARD_DESIGNS['mali']
