# Learning Sites

Cours interactifs classés par matière, puis par ordre d’apprentissage : arbres rouge-noir, décisions de Markov, représentation des textes et règles d’association. Les animations et calculs s’exécutent dans le navigateur.

**Production : https://learning.141-145-214-196.nip.io/**

## Aperçu local

Python 3 et un navigateur récent avec JavaScript suffisent pour consulter le site. Node.js est utilisé uniquement pour vérifier la syntaxe des scripts.

```sh
git clone https://github.com/alexalmny/learning-sites.git
cd learning-sites
python3 -m http.server 8000 --bind 127.0.0.1
```

Ouvrir <http://localhost:8000>. Le serveur Python est réservé à l’aperçu local.

## Ajouter ou classer un cours

1. Créer `<slug>/index.html`, lier `../styles.css` et définir la palette avec `data-course`, comme les cours existants. Ce dossier ne doit contenir que des fichiers publics (aucun secret ni lien symbolique).
2. Ajouter une entrée dans `courses.json` :

   ```json
   {
     "path": "nouveau-cours",
     "category": "Algorithmique",
     "index": 20,
     "title": "Nouveau cours",
     "description": "Ce que ce cours permet de comprendre."
   }
   ```

   Les matières sont regroupées et triées alphabétiquement. L’indice est un entier positif, unique **dans la matière**, trié numériquement. Les indices 10, 20, 30 permettent d’intercaler une étape 15. Réutiliser exactement le même nom de matière pour regrouper les pages. Actuellement chaque matière contient un cours, d’indice 10.
3. Régénérer le portail, puis vérifier :

   ```sh
   python3 scripts/build.py --update-portal
   python3 scripts/check.py
   python3 -m unittest discover -s scripts -p 'test_*.py'
   ```

Versionner le catalogue, les cours et le `index.html` généré ensemble. Ne pas modifier le portail à la main : les contrôles signalent un portail périmé, les doublons, les indices invalides et les pages absentes du catalogue. Aucun JavaScript n’est nécessaire pour afficher le portail.

## Déploiement sur le serveur existant

Même modèle que les autres sites du serveur : **Nginx, fichiers statiques dans `/var/www`, certificat Let’s Encrypt via Certbot**. Aucun backend, paquet npm, conteneur, base de données ni service systemd supplémentaire.

- Sources : `/home/ubuntu/develop/learning-sites`.
- Versions publiques : `/var/www/learning-sites/releases/<date>-<commit>`.
- Version active : lien symbolique `/var/www/learning-sites/current`.
- Configuration : `/etc/nginx/sites-available/learning-sites`, activée dans `sites-enabled`.
- HTTPS : certificat `learning.141-145-214-196.nip.io`, renouvelé par le timer Certbot ; le hook existant `reload-nginx` recharge Nginx.

### Mise à jour

Après récupération et revue des changements :

```sh
cd /home/ubuntu/develop/learning-sites
# Si le checkout est propre : git pull --ff-only
sh deploy/publish.sh
python3 scripts/check_live.py
```

Le script vérifie le site, teste le générateur, construit une version publique dans un répertoire temporaire, puis bascule le lien `current` atomiquement. Il ne publie ni `.git`, ni le catalogue, ni les scripts, ni la documentation. Les anciennes versions restent disponibles ; aucun rechargement Nginx n’est nécessaire pour une mise à jour de contenu. Ce n’est pas un déploiement automatique sur chaque push.

Pour produire uniquement les fichiers publics : `python3 scripts/build.py` (crée `dist/`, qui ne doit pas déjà exister).

### Première installation HTTPS

Sur ce serveur uniquement, après vérification du DNS et de l’accès aux ports 80/443 :

```sh
sh deploy/publish.sh
sudo install -m 644 deploy/nginx-http.conf /etc/nginx/sites-available/learning-sites
sudo ln -s /etc/nginx/sites-available/learning-sites /etc/nginx/sites-enabled/learning-sites
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt \
  -d learning.141-145-214-196.nip.io --non-interactive --agree-tos --register-unsafely-without-email
sudo install -m 644 deploy/nginx.conf /etc/nginx/sites-available/learning-sites
sudo nginx -t && sudo systemctl reload nginx
```

Les fichiers Nginx sont propres au nom d’hôte ci-dessus : les adapter pour un autre domaine. `noindex` et `robots.txt` limitent l’indexation, **pas l’accès public**. Les supports cités gardent leurs conditions d’accès et de réutilisation ; certains liens Moodle nécessitent une authentification.

### Retour arrière

Choisir une ancienne version dans `/var/www/learning-sites/releases`, puis :

```sh
sudo ln -s /var/www/learning-sites/releases/<version> /var/www/learning-sites/current.next
sudo mv -Tf /var/www/learning-sites/current.next /var/www/learning-sites/current
```

La bascule ne touche ni aux autres sites ni aux données persistantes. Les versions conservées sur le même disque ne constituent pas une sauvegarde externe.

## Vérification et CI

GitHub Actions exécute les contrôles sur les pushes vers `main` et les pull requests : cohérence du catalogue et du portail, liens, syntaxe JavaScript via Node, tests du tri/échappement/validation et génération des fichiers publics. `python3 scripts/check_live.py` vérifie le site publié : toutes les pages du catalogue, CSS, HTTPS, en-têtes et absence d’accès aux sources internes. Ces tests ne remplacent pas une vérification des animations et de l’affichage mobile dans un navigateur.
