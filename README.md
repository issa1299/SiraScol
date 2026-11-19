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
| `/eleves/importer/` | Import en masse des élèves (CSV/Excel) — directeur/secrétaire |
| `/eleves/<id>/` | Fiche élève |
| `/mon-espace/` | Espace Élève dédié |
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

## Emploi du temps par classe

```bash
python manage.py check_edt                      # contrôle classe par classe
python manage.py generate_edt                   # classes avec élèves (idempotent)
python manage.py generate_edt --all             # toutes les classes de l'année
python manage.py generate_edt --class "1ère A"  # une seule classe
python manage.py generate_edt --overwrite       # reconstruire les grilles
```

La grille de base est aussi générable depuis l'interface `/emploi-du-temps/` (bouton « Générer la grille »), pour les admins. Les créneaux déjà occupés ne sont pas écrasés sauf avec `--overwrite`.

## Import en masse des élèves

Menu **Élèves → Importer des élèves** (`/eleves/importer/`) ou, en ligne de commande :

L'import se fait **classe par classe** : on choisit d'abord la classe (et l'année), puis on dépose le fichier des élèves de cette classe.

```bash
python manage.py import_students eleves.csv --class "1ère A"
python manage.py import_students eleves.xlsx --class "1ère A" --year 2026-2027
python manage.py import_students --sample > modele.csv
```

Le modèle CSV (séparateur `;`, UTF-8) contient les colonnes :
`Nom;Prénom;Sexe;Date de naissance;Date d'inscription;Téléphone;Lieu de naissance;Adresse;Nom du parent;Téléphone parent;Relation`

La classe et l'année ne sont **pas** dans le fichier : elles sont fournies au formulaire ou à la commande (`--class`).

- Le **matricule est généré automatiquement** (`2026-0001`).
- Un **compte élève** est créé : identifiant `2026.0001`, mot de passe `2026-0001` (à faire changer ensuite).
- Une **inscription** est créée pour la classe et l'année indiquées, avec les factures si les frais sont configurés.
- Les **parents/tuteurs** et leurs comptes sont créés si les colonnes sont remplies.
- Les lignes invalides sont ignorées et signalées dans le rapport ; aucune importation partielle d'une ligne.

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
