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

## Première connexion

Les comptes **élèves et parents** créés par l'application (inscription ou import) doivent changer leur mot de passe initial à la première connexion. Identifiant = matricule avec un point (`2026.0001`), mot de passe initial = matricule (`2026-0001`).

Les comptes déjà existants avant cette fonctionnalité ne sont pas concernés. Pour forcer tous les élèves/parents à changer :
```bash
python manage.py shell -c "from accounts.models import Profile; Profile.objects.filter(role__in=['eleve','parent']).update(must_change_password=True)"
```

## Bulletins

Deux modèles selon le niveau :

| Type | Niveaux | Contenu |
|------|---------|---------|
| **Primaire** | 1ère → 5ème année | Moyennes par matière (compositions), appréciation instituteur |
| **Secondaire / Lycée** | 6ème → 12ème | Détail Devoir / Composition / Trimestre + moyenne + conseil de classe |

Accès : Fiche élève → bouton **Bulletin** · Filtre par période · Bouton Imprimer

## Messagerie privée et rôles

Les destinataires proposés dans chaque portail sont calculés par `core/messaging.py` (`allowed_recipients`) et **vérifiés côté serveur** dans `Message.save()` : toute tentative de contacter un rôle interdit renvoie une erreur 403.

- Directeur : tous les comptes.
- Secrétaire : direction, comptable, surveillant, enseignants, parents.
- Comptable : direction, secrétariat, parents.
- Surveillant : direction, secrétariat, enseignants, élèves, parents.
- Professeur : direction, secrétariat, surveillant, **ses élèves et leurs parents**.
- Élève : ses professeurs et le surveillant (pas le comptable).
- Parent : direction, secrétariat, comptable, surveillant et **les professeurs de ses enfants**.

Les messages acceptent une pièce jointe et génèrent une notification pour le destinataire. Le rôle `surveillant` a été ajouté (droits absences/élèves, ni notes ni finances).

## Espace Comptable

Portail dédié sur `/mon-espace-comptable/` : tableau de bord financier, configuration des frais et génération de factures (avec réductions/exonérations), paiements (espèces, Mobile Money, virement, chèque) avec reçu PDF, dépenses avec pièce justificative, impayés filtrables avec rappels aux parents, reçus/factures avec annulation tracée, et rapports journaliers/hebdomadaires/mensuels/annuels exportables en Excel et PDF.

Les droits finance sont réservés au comptable et au directeur ; le secrétaire ne peut ni enregistrer de paiement ni consulter les reçus.

## Fiche classe (Gestion des classes)

La fiche d'une classe (`/classes/<id>/`) contient 10 onglets — Vue générale, Élèves, Matières, Enseignants, Emploi du temps, Présences, Notes, Discipline, Bulletins, Rapports. Les rapports (effectif, présence, enseignants, résultats) sont générés en PDF. Le modèle `Sanction` couple les retenues, avertissements, exclusions et observations à une classe et à un élève. L'historique des inscriptions est conservé lors des changements d'année (utiliser la promotion en fin d'année).

Sur mobile, les tableaux deviennent des cartes compactes ; un appui ouvre une boîte de dialogue avec toutes les colonnes de la ligne. Les cellules contenant un champ ou un lien d'action restent toujours visibles.

## Cartes & badges (élèves et personnel)

Interface unifiée sur `/eleves/cartes/` avec deux onglets **Élèves** et **Personnel**. Six modèles de badge (CR80, 85,6 × 54 mm) sont proposés avec un aperçu réel ; le modèle choisi est enregistré dans les paramètres de l'école et appliqué à tous les rendus (HTML, PNG, PDF).

Chaque badge contient un **QR code généré localement** (`core/qr.py`, dépendance `qrcode[pil]`) pour le pointage des présences :
- élève → `STU:<matricule>` ; personnel → `TCH:<matricule>`.
- Le scanner (`/absences/scan/`) reconnaît ces préfixes et détermine automatiquement le type de pointage, sans changer d'onglet.
- Aucun appel à un service QR externe.

Actions disponibles : aperçu en boîte de dialogue, PDF individuel ou groupé (une carte par page), image PNG haute définition et impression navigateur. Les badges du personnel sont aussi accessibles depuis `/enseignants/qr-codes/`.

## Espace Secrétaire

Portail dédié sur `/mon-espace-secretaire/` : tableau de bord administratif, élèves (recherche, archive, transfert), inscriptions/réinscriptions, classes et effectifs, enseignants, documents PDF (certificat de scolarité, attestation, fiche d'inscription, liste de classe), annonces et messages à transmettre à la direction, notifications, profil.

Le rôle `comptable` est désormais distinct de `secretaire` : le secrétaire gère les dossiers scolaires, le comptable les seules opérations financières.

## Espace Parent

Portail dédié sur `/mon-espace-parent/` (dashboard multi-enfants, notes, bulletins PDF, absences, paiements/reçus, emploi du temps, devoirs, messagerie, demandes de rendez-vous, notifications, profil). Un sélecteur d'enfant permet de suivre chaque enfant avec un seul compte. Le parent ne peut consulter que ses propres enfants ; les reçus de paiement sont également filtrés par élève.

## Espace Professeur

Portail dédié sur `/mon-espace-prof/` (dashboard, classes, notes, présences, emploi du temps, devoirs, supports de cours, bulletins/appréciations, notifications, rendez-vous, messages, profil). Les nouveaux messages et demandes de rendez-vous créent une notification pour leur destinataire (professeur ou direction). Les enseignants y voient uniquement leurs classes et matières affectées. La validation finale des notes par la direction se fait sur `/mon-espace-prof/validation/`. Les notes validées ne sont plus modifiables par les enseignants.

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

### Par l'interface (directeur / secrétaire)
1. Télécharger le **modèle Excel** (`.xlsx`, onglets « Élèves » et « Consignes ») ou le modèle CSV.
2. Remplir **une ligne par élève** de la classe choisie.
3. Déposer le fichier : SiraScol **vérifie les données et détecte doublons/erreurs**, puis affiche un **aperçu** — *aucune écriture en base à cette étape*.
4. **Confirmer** l'import : les élèves valides sont créés dans une transaction globale, avec leurs comptes et inscriptions.
5. Un **rapport d'erreurs Excel** est téléchargeable si des lignes ont été ignorées.

### En ligne de commande
```bash
python manage.py import_students eleves.csv --class "1ère A"
python manage.py import_students eleves.xlsx --class "1ère A" --year 2026-2027
python manage.py import_students --sample > modele.csv
```

Le modèle (séparateur `;` pour le CSV, UTF-8) contient les colonnes :
`Nom;Prénom;Sexe;Date de naissance;Date d'inscription;Téléphone;Lieu de naissance;Adresse;Nom du parent;Téléphone parent;Relation`

La classe et l'année ne sont **pas** dans le fichier : elles sont fournies au formulaire ou à la commande (`--class`).

- Le **matricule est généré automatiquement** (`2026-0001`).
- Un **compte élève** est créé : identifiant `2026.0001`, mot de passe `2026-0001` (à faire changer ensuite).
- Une **inscription** est créée pour la classe et l'année indiquées, avec les factures si les frais sont configurés.
- Les **parents/tuteurs** et leurs comptes sont créés si les colonnes sont remplies ; un même parent peut être associé à plusieurs enfants.
- Les **doublons** (même nom + prénom + date de naissance, dans le fichier ou en base) et les **lignes invalides** sont signalés avant confirmation et jamais importés ; aucune importation partielle d'une ligne.

## Inscription manuelle

Menu **Élèves → Ajouter un élève** (`/eleves/ajouter/`). Le secrétaire renseigne l'identité, la scolarité (classe + année, obligatoires) et les informations du parent/tuteur — existant (plusieurs enfants possibles sur un même compte) ou nouveau. Le **matricule est généré automatiquement**, les comptes élève/parent sont créés et leurs identifiants affichés, et les frais de la classe sont facturés.

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
