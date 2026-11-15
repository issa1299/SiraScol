# Checklist production — SiraScol

## 1. Préparer l’environnement

```powershell
cd C:\Users\USER\Downloads\SiraScol
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Générer une clé secrète :
```powershell
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Créer un fichier `.env` (ou variables système Windows) :
```
SIRASCOL_SECRET_KEY=<votre_cle>
SIRASCOL_DEBUG=0
SIRASCOL_ALLOWED_HOSTS=votre-domaine.com
SIRASCOL_TIMEZONE=Africa/Bamako
```

Sous PowerShell (session courante) :
```powershell
$env:SIRASCOL_SECRET_KEY="votre_cle"
$env:SIRASCOL_DEBUG="0"
$env:SIRASCOL_ALLOWED_HOSTS="votre-domaine.com"
```

## 2. Base de données & fichiers

```powershell
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py init_school_data
```

## 3. Sauvegardes (très important)

```powershell
python manage.py backup_data
```

Planifier chaque jour (Planificateur de tâches Windows) ou cron Linux :
```bash
0 2 * * * cd /chemin/SiraScol && ./venv/bin/python manage.py backup_data
```

Les archives sont dans le dossier `backups/`.

## 4. Serveur web (recommandé)

Ne pas utiliser `runserver` en production.

Exemple minimal avec waitress (Windows) :
```powershell
pip install waitress
waitress-serve --listen=0.0.0.0:8000 config.wsgi:application
```

Derrière **nginx** ou **Caddy** avec certificat HTTPS (Let's Encrypt).

## 5. HTTPS

- Obligatoire pour l’empreinte digitale hors localhost
- Obligatoire pour les cookies sécurisés (`SESSION_COOKIE_SECURE`)

## 6. Comptes

| À faire | Détail |
|---------|--------|
| Mot de passe admin fort | Min. 12 caractères |
| Un compte par personne | Pas de compte partagé |
| Désactiver les comptes partis | Personnel → statut |
| Limiter les superusers | 1 ou 2 max |

## 7. Contrôles avant ouverture

- [ ] `SIRASCOL_DEBUG=0`
- [ ] `SIRASCOL_SECRET_KEY` unique (pas la clé de dev)
- [ ] `SIRASCOL_ALLOWED_HOSTS` = ton domaine uniquement
- [ ] HTTPS actif
- [ ] `collectstatic` fait
- [ ] Sauvegarde testée (`backup_data`)
- [ ] Connexion admin OK
- [ ] Empreinte testée en HTTPS
- [ ] Rôles vérifiés (prof / parent ne voient pas tout)

## 8. En cas de panne

1. Mode maintenance : Paramètres → **Activer**
2. Restaurer une archive `backups/sirascol_backup_*.zip` (db.sqlite3 + media)
3. Relancer le service

## Rappel

| Contexte | OK ? |
|----------|------|
| Réseau local école + comptes contrôlés | Oui |
| Internet public sans HTTPS / DEBUG=1 | Non |
