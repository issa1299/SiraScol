# SiraScol - Django + SQLite

## Structure

| Cycle | Années |
|-------|--------|
| Primaire | 1ère → 6ème année |
| Secondaire | 7ème → 9ème année |
| Lycée | 10ème → 12ème année (séries) |

## Évaluations

| Niveaux | Types |
|---------|-------|
| 1ère → 5ème | Composition mensuelle |
| 6ème → 12ème | Devoir + Composition + Trimestre |

## Installation

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py init_school_data
python manage.py runserver
```

## Pages

| URL | Description |
|-----|-------------|
| `/` | Tableau de bord |
| `/accounts/login/` | Connexion |
| `/eleves/` | Liste élèves |
| `/eleves/<id>/` | Fiche élève |
| `/enseignants/` | Liste enseignants |
| `/enseignants/<id>/` | Fiche enseignant |
| `/classes/` | Liste classes |
| `/classes/<id>/` | Détail classe |
| `/notes/` | Liste évaluations |
| `/notes/<id>/saisie/` | **Saisie des notes** |
| `/notes/bulletins/` | **Gestion des bulletins** (par classe) |
| `/notes/bulletin/<id>/` | Bulletin individuel (Primaire ou Secondaire/Lycée) |
| `/absences/` | Liste absences |
| `/absences/ajouter/` | Saisir absence |
| `/finances/` | **Dashboard finances** |
| `/finances/factures/` | Liste factures |
| `/finances/paiement/` | Enregistrer paiement |
| `/admin/` | Administration |

## Matricule
Généré automatiquement : `2026-0001`, `2026-0002`...


## Bulletins

Deux modèles selon le niveau :

| Type | Niveaux | Contenu |
|------|---------|---------|
| **Primaire** | 1ère → 5ème année | Moyennes par matière (compositions), appréciation instituteur |
| **Secondaire / Lycée** | 6ème → 12ème | Détail Devoir / Composition / Trimestre + moyenne + conseil de classe |

Accès : Fiche élève → bouton **Bulletin** · Filtre par période · Bouton Imprimer

## Production

Voir **[PRODUCTION.md](PRODUCTION.md)** pour la checklist complète (HTTPS, DEBUG, sauvegardes).

```bash
# Sauvegarde
python manage.py backup_data

# Variables (exemple)
# SIRASCOL_DEBUG=0
# SIRASCOL_SECRET_KEY=...
# SIRASCOL_ALLOWED_HOSTS=ecole.example.com
```
