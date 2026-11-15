# Déployer SiraScol sur PythonAnywhere (gratuit)

## 1. Créer un compte
1. Va sur https://www.pythonanywhere.com
2. **Create a Beginner account** (gratuit)
3. Choisis un username (ex: `sirascol`)  
   → ton site sera : `https://sirascol.pythonanywhere.com`

---

## 2. Uploader le projet

### Option A — Upload ZIP (simple)
1. Menu **Files**
2. Va dans `/home/TON_USERNAME/`
3. Upload `SiraScol.zip`
4. Ouvre une **Bash console** :
```bash
cd ~
unzip SiraScol.zip -d SiraScol
cd SiraScol
```

### Option B — Git (si le projet est sur GitHub)
```bash
cd ~
git clone https://github.com/TON_COMPTE/SiraScol.git
cd SiraScol
```

---

## 3. Environnement virtuel + paquets
Dans la **Bash console** :
```bash
cd ~/SiraScol
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> Si `python3.12` n’existe pas, essaie `python3.10` ou `python3.11` (voir la version dispo sur ton compte).

---

## 4. Fichier `.env` (important)
```bash
cd ~/SiraScol
nano .env
```

Contenu (adapte le username) :
```
SIRASCOL_DEBUG=0
SIRASCOL_SECRET_KEY=remplace-par-une-longue-cle-aleatoire
SIRASCOL_ALLOWED_HOSTS=TON_USERNAME.pythonanywhere.com
SIRASCOL_SSL_REDIRECT=0
SIRASCOL_BEHIND_PROXY=1
SIRASCOL_TIMEZONE=Africa/Bamako
```

Générer une clé secrète :
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Colle le résultat dans `SIRASCOL_SECRET_KEY=...`

Enregistre : `Ctrl+O`, Entrée, `Ctrl+X`.

---

## 5. Base de données + fichiers statiques
```bash
cd ~/SiraScol
source venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```
(Crée ton compte admin : username + mot de passe)

Optionnel — données de démo :
```bash
python manage.py init_school_data
```

---

## 6. Configurer l’appli Web

1. Menu **Web**
2. **Add a new web app**
3. **Manual configuration** (pas Django wizard)
4. Choisis la **même version Python** que le venv (3.12 / 3.11 / 3.10)

### 6.1 Source code & Working directory
- **Source code** : `/home/TON_USERNAME/SiraScol`
- **Working directory** : `/home/TON_USERNAME/SiraScol`

### 6.2 Virtualenv
```
/home/TON_USERNAME/SiraScol/venv
```

### 6.3 Fichier WSGI
Clique sur le lien du fichier WSGI (ex: `/var/www/TON_USERNAME_pythonanywhere_com_wsgi.py`)

**Efface tout** et mets :
```python
import os
import sys

path = '/home/TON_USERNAME/SiraScol'
if path not in sys.path:
    sys.path.insert(0, path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
Remplace `TON_USERNAME` par ton vrai username.  
Enregistre.

### 6.4 Static files
Dans la section **Static files** :

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/TON_USERNAME/SiraScol/staticfiles` |
| `/media/` | `/home/TON_USERNAME/SiraScol/media` |

### 6.5 Reload
Bouton vert **Reload** en haut de la page Web.

---

## 7. Tester
Ouvre : **https://TON_USERNAME.pythonanywhere.com**

Login avec le superuser créé à l’étape 5.

---

## Problèmes fréquents

| Erreur | Solution |
|--------|----------|
| DisallowedHost | Vérifie `SIRASCOL_ALLOWED_HOSTS=tonusername.pythonanywhere.com` dans `.env` |
| Page blanche / 500 | Onglet **Web** → **Log files** → Error log |
| CSS / images absents | `collectstatic` + mapping `/static/` et `/media/` |
| Module not found | `source venv/bin/activate` puis `pip install -r requirements.txt` + Reload |
| Wrong Python version | Venv et Web app doivent avoir la **même** version |

---

## Mettre à jour le code plus tard
```bash
cd ~/SiraScol
source venv/bin/activate
# (upload nouveaux fichiers ou git pull)
python manage.py migrate
python manage.py collectstatic --noinput
```
Puis **Reload** sur la page Web.

---

## Sauvegarde
```bash
cd ~/SiraScol
source venv/bin/activate
python manage.py backup_data
```
Les archives sont dans `~/SiraScol/backups/`.

---

## Rappel compte gratuit
- 1 site web
- Suffisant pour démo / petite école
- Ne pas laisser `SIRASCOL_DEBUG=1` en ligne
