# Learning Sites

Cours interactifs classés par matière, puis par ordre d’apprentissage : arbres rouge-noir, décisions de Markov, représentation des textes et règles d’association. Les animations et calculs s’exécutent dans le navigateur.

**Production : https://learning.141-145-214-196.nip.io/**

## Ajouter ou modifier un cours

1. Créer `<slug>/index.html`, lier `../styles.css` et définir la palette avec `data-course`, comme les cours existants. Ce dossier ne doit contenir que des fichiers publics : aucun secret ni lien symbolique.
2. Pour un nouveau cours, ajouter une entrée dans `courses.json` :

   ```json
   {
     "path": "nouveau-cours",
     "category": "Algorithmique",
     "index": 20,
     "title": "Nouveau cours",
     "description": "Ce que ce cours permet de comprendre."
   }
   ```

   Les matières sont regroupées et triées alphabétiquement. L’indice est un entier positif, unique **dans la matière**, trié numériquement. Les indices 10, 20, 30 permettent d’intercaler une étape 15. Réutiliser exactement le même nom de matière pour regrouper les pages.
3. Pousser sur `main` (ou fusionner une pull request). **GitHub Actions régénère le portail, teste, puis déploie automatiquement.** Il n’est pas nécessaire de modifier ou de régénérer `index.html` avant le push.

Les contrôles refusent notamment les doublons, les indices invalides et les pages absentes du catalogue. Ne pas modifier le portail à la main : le `index.html` à la racine est un aperçu généré, remplacé pendant la CI. Aucun JavaScript n’est nécessaire pour afficher le portail.

## Aperçu et tests locaux

Python 3 et un navigateur récent avec JavaScript suffisent pour consulter le site. Node.js est utilisé uniquement pour vérifier la syntaxe des scripts. Les tests de réception utilisent `tarfile.data_filter` (Python 3.12, ou la version de Python 3.10 mise à jour du serveur).

```sh
git clone https://github.com/alexalmny/learning-sites.git
cd learning-sites
python3 scripts/build.py --update-portal
python3 scripts/check.py
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m http.server 8000 --bind 127.0.0.1
```

Ouvrir <http://localhost:8000>. Le serveur Python est réservé à l’aperçu local. Pour produire uniquement les fichiers publics : `python3 scripts/build.py` (crée `dist/`, qui ne doit pas déjà exister).

## Déploiement automatique

Le workflow **`.github/workflows/ci.yml`** utilise uniquement les runners hébergés par GitHub et des actions officielles épinglées par SHA. Aucun runner, webhook, conteneur ou backend supplémentaire sur le serveur.

1. Sur push vers `main`, pull request ou lancement manuel : génération du portail, contrôles du catalogue, des liens et de la syntaxe JavaScript, tests du générateur et du récepteur SSH.
2. Après succès, pour `main` seulement : envoi de l’archive publique construite et testée vers le job `deploy`. L’artefact GitHub est conservé un jour.
3. Le job utilise l’environnement GitHub **`production`**, limité à la branche `main`. Les pull requests ne déploient jamais et n’accèdent pas à la clé.
4. Une connexion SSH envoie l’archive au récepteur installé sur le serveur. Il vérifie les chemins et types de fichiers, refuse les liens et limite une publication à 50 MiB et 10 000 entrées. Aucun script du dépôt n’est exécuté sur le serveur.
5. Le récepteur bascule le lien `current` atomiquement, puis compare le contenu servi en HTTPS aux pages et fichiers communs reçus. **En cas d’échec de cette vérification, il rétablit la version précédente.** Un échec avant la bascule laisse le site intact.
6. Un contrôle HTTPS supplémentaire depuis GitHub vérifie les pages, les en-têtes et l’inaccessibilité des fichiers privés. Un échec de ce contrôle externe signale une erreur dans Actions ; il ne déclenche pas un second retour arrière.

Les publications sont sérialisées par la concurrence GitHub et un verrou sur le serveur. Une exécution dont le commit n’est plus la tête de `main` est ignorée avant l’envoi. Les cinq dernières versions CI sont conservées, ainsi que la version précédente si nécessaire et les versions administrateur antérieures.

### Relancer manuellement

Depuis l’onglet **Actions → CI → Run workflow**, choisir `main`, ou :

```sh
gh workflow run ci.yml --ref main --repo alexalmny/learning-sites
gh run list --repo alexalmny/learning-sites
```

Le serveur n’a pas besoin d’un `git pull` : seuls les fichiers publics de l’artefact sont transférés. Le checkout de développement sur le serveur n’est donc pas mis à jour automatiquement.

### Accès et chemins du serveur

- Sources de développement : `/home/ubuntu/develop/learning-sites`.
- Versions : `/var/www/learning-sites/releases/<commit>-<run>-<attempt>`.
- Version active : `/var/www/learning-sites/current`.
- Compte dédié : `learning-deploy`, **sans sudo**, avec accès en écriture limité aux répertoires de publication du site.
- Clé autorisée : `/var/lib/learning-sites-deploy/.ssh/authorized_keys`, fichier et répertoires SSH appartenant à root. Option `restrict` et commande forcée `/usr/local/libexec/learning-sites-deploy` : aucun shell, transfert arbitraire, tunnel ou terminal.
- Récepteur : copie de `deploy/receive.py`, installée par root et non modifiable par `learning-deploy`.
- Nginx : `/etc/nginx/sites-available/learning-sites`, activé dans `sites-enabled` ; copie de `deploy/nginx.conf`.
- TLS : certificat Let's Encrypt `learning.141-145-214-196.nip.io`, renouvellement Certbot existant et hook `reload-nginx`.

Un changement du récepteur ou de Nginx demande une installation administrative explicite ; la CI ne peut modifier ni ces fichiers, ni les autres services :

```sh
sudo install -D -o root -g root -m 755 deploy/receive.py /usr/local/libexec/learning-sites-deploy
# Seulement si la configuration Nginx change :
sudo install -m 644 deploy/nginx.conf /etc/nginx/sites-available/learning-sites
sudo nginx -t && sudo systemctl reload nginx
```

Aucun rechargement Nginx n’est nécessaire pour les publications de contenu.

### Clé SSH et restauration de la configuration

L’environnement GitHub `production` contient :

- Secret **`LEARNING_DEPLOY_KEY`** : clé privée Ed25519 dédiée ; aucune copie n’est conservée dans le dépôt ou sur le serveur.
- Variable **`LEARNING_DEPLOY_KNOWN_HOSTS`** : clé publique d’hôte SSH, obtenue directement depuis `/etc/ssh/ssh_host_ed25519_key.pub`, pas par un `ssh-keyscan` non vérifié pendant la CI. La vérification d’hôte est obligatoire.

Pour une rotation, générer une nouvelle clé dédiée, installer sa clé publique avec les mêmes restrictions dans `authorized_keys`, puis envoyer la clé privée à GitHub via l’entrée standard, sans l’afficher :

```sh
gh secret set LEARNING_DEPLOY_KEY --env production --repo alexalmny/learning-sites < /chemin/prive/cle
```

Supprimer la copie locale après la rotation. Pour révoquer immédiatement l’accès, retirer la clé publique de `authorized_keys` et supprimer le secret GitHub. Pour reconstruire un serveur, recréer le compte système `learning-deploy` (home root-owned `/var/lib/learning-sites-deploy`, shell `/bin/sh` nécessaire à SSH), les répertoires de publication, la commande forcée et le certificat/configuration Nginx avant de relancer le workflow.

### Retour arrière administratif

Ne pas effectuer une bascule manuelle en parallèle d’une publication Actions. Choisir une version dans `/var/www/learning-sites/releases`, puis :

```sh
sudo ln -s /var/www/learning-sites/releases/<version> /var/www/learning-sites/current.next
sudo mv -Tf /var/www/learning-sites/current.next /var/www/learning-sites/current
```

Le push suivant sur `main` republiera normalement. Les versions du même disque ne constituent pas une sauvegarde externe.

## Vérifier le site publié

```sh
python3 scripts/check_live.py
```

Ce contrôle compare toutes les pages du catalogue et le CSS au contenu attendu, vérifie HTTPS, les en-têtes et l’absence d’accès aux sources internes. Ces tests ne remplacent pas une vérification exhaustive des animations et calculs pédagogiques.

Le site est **public** : `noindex` et `robots.txt` ne sont pas un contrôle d’accès. Les supports cités gardent leurs conditions d’accès et de réutilisation ; certains liens Moodle nécessitent une authentification. Une fuite de la clé de déploiement permettrait de remplacer le contenu public de ce site ; elle ne donne pas de shell ni de droits sur les autres services.
