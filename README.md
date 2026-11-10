# Learning Sites

Cours interactifs classés par matière, puis par ordre d’apprentissage : arbres rouge-noir, décisions de Markov, représentation des textes et règles d’association. Les animations et calculs s’exécutent dans le navigateur.

L’origine de production est fournie par la variable GitHub `STATIC_ORIGIN`, hors du dépôt.

## Génération automatique des cours

À la fin de chaque séance de cours, un pipeline automatisé s’appuie sur mes notes personnelles et sur les ressources en ligne fournies par mes enseignants — supports, exemples, énoncés de TD et de TP — pour générer un site interactif consacré aux notions étudiées.

La génération suit des règles pédagogiques strictes : **développer l’intuition d’abord, formaliser ensuite**. Le site ne doit pas simplement reformuler les supports : il doit permettre de comprendre les mécanismes en les manipulant.

- **Partir d’un exemple concret** et d’une question qui donne un sens à la notion avant d’introduire les définitions ou les formules.
- **Choisir des exemples pédagogiques progressifs**, assez petits pour être suivis à la main, puis montrer les cas limites et les contre-exemples qui révèlent les erreurs d’intuition.
- **Rendre les mécanismes observables** : visualisations, exécution pas à pas et paramètres modifiables, avec une explication de ce qui change et pourquoi.
- **Relier l’intuition à la théorie** : expliciter les hypothèses, les invariants et les calculs, sans sacrifier la rigueur à la simplification.
- **Vérifier la compréhension** avec des exercices et des corrections expliquées, pas seulement une réponse juste ou fausse.
- **Rester fidèle aux sources** : citer les ressources utilisées et signaler les ambiguïtés ou informations manquantes plutôt que d’inventer une explication.

Les notes personnelles servent d’entrée à la génération, pas de contenu à publier telles quelles. Les ressources des enseignants conservent leurs conditions d’accès et de réutilisation.

Ce pipeline de génération est distinct de la CI de ce dépôt : **GitHub Actions construit le portail, vérifie les fichiers produits et les déploie** ; il ne consulte pas lui-même mes notes ni les supports des enseignants.

## Ajouter ou modifier un cours

1. Créer `<slug>/index.html`, lier `../styles.css` et définir la palette avec `data-course`, comme les cours existants. Ce dossier ne doit contenir que des fichiers publics : aucun secret ni lien symbolique.
2. Pour un nouveau cours, ajouter une entrée dans `courses.json` :

   ```json
   {
     "path": "nouveau-cours",
     "category": "Algorithmique avancée 2 (AA2)",
     "index": 20,
     "title": "Nouveau cours",
     "description": "Ce que ce cours permet de comprendre."
   }
   ```

   Les matières sont regroupées et triées alphabétiquement. L’indice est un entier positif, unique **dans la matière**, trié numériquement. Les indices 10, 20, 30 permettent d’intercaler un cours à l’indice 15 ; ils servent uniquement au tri et ne sont pas affichés. Réutiliser exactement le même nom de matière pour regrouper les pages. Les intitulés suivent la [liste des matières du master IA sur le FIL](https://www.fil.univ-lille.fr/portail/index.php?dipl=MInfo&sem=IA&ue=ACCUEIL). Le portail affiche uniquement le nom du site, les matières et les liens des cours, sans descriptions.
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

Le workflow **`.github/workflows/ci.yml`** appelle **`.github/workflows/deploy-static.yml`**, réutilisable par les autres sites statiques. Il utilise uniquement les runners hébergés par GitHub et des actions officielles épinglées par SHA. Aucun runner, webhook, conteneur ou backend supplémentaire sur le serveur.

1. Sur push vers `main`, pull request ou lancement manuel : génération du portail, contrôles du catalogue, des liens et de la syntaxe JavaScript, tests du générateur et du récepteur SSH.
2. Après succès, pour `main` seulement : envoi de l’archive publique construite et testée vers le job `deploy`. L’artefact GitHub est conservé un jour.
3. Le job utilise l’environnement GitHub **`production`**, limité à la branche `main`. Les pull requests ne déploient jamais et n’accèdent pas à la clé.
4. Une connexion SSH envoie l’archive au récepteur installé sur le serveur. Il vérifie les chemins et types de fichiers, refuse les liens et limite une publication à 50 MiB et 10 000 entrées. Aucun script du dépôt n’est exécuté sur le serveur.
5. Le récepteur enregistre la version précédente et une échéance de cinq minutes avant de basculer `current` atomiquement. Il compare ensuite tous les fichiers publics servis en HTTPS aux fichiers reçus. **Une erreur locale rétablit immédiatement la version précédente.** Un échec avant la bascule laisse le site intact.
6. Depuis GitHub, le workflow vérifie le SHA-256 de chaque fichier public puis exécute `scripts/check_live.py` (pages, en-têtes et inaccessibilité des fichiers privés). Il confirme la publication uniquement après succès. **Un échec ou une annulation déclenche un retour arrière par SSH.**
7. Le timer serveur `static-release@learning-deploy.timer` vérifie les publications toutes les 30 secondes. **Sans confirmation dans les cinq minutes, il rétablit la version précédente**, même si le runner disparaît ou ne peut plus se connecter. Le délai peut être prolongé par la durée d’une vérification serveur en cours, qui détient le verrou de publication. Une ancienne exécution ne peut pas annuler une publication plus récente.

Les publications sont sérialisées par la concurrence GitHub et un verrou sur le serveur. Une exécution dont le commit n’est plus la tête de `main` est ignorée avant l’envoi. Les cinq dernières versions CI sont conservées, ainsi que la version précédente si nécessaire et les versions administrateur antérieures.

### Relancer manuellement

Depuis l’onglet **Actions → CI → Run workflow**, choisir `main`, ou :

```sh
gh workflow run ci.yml --ref main --repo alexalmny/learning-sites
gh run list --repo alexalmny/learning-sites
```

Le serveur n’a pas besoin d’un `git pull` : seuls les fichiers publics de l’artefact sont transférés. Le checkout de développement sur le serveur n’est donc pas mis à jour automatiquement.

### Accès et chemins du serveur

- Sources de développement : le checkout local, à placer librement.
- Versions : `/var/www/learning-sites/releases/<commit>-<run>-<attempt>`.
- Version active : `/var/www/learning-sites/current`.
- Compte dédié : `learning-deploy`, **sans sudo**, avec accès en écriture limité aux répertoires de publication du site.
- Clé autorisée : `/var/lib/learning-sites-deploy/.ssh/authorized_keys`, fichier et répertoires SSH appartenant à root. Option `restrict` et commande forcée `/usr/local/libexec/static-release-receive --config /etc/static-release/learning-deploy.json` : aucun shell, transfert arbitraire, tunnel ou terminal.
- Récepteur partagé : `deploy/receive.py`, installé par root dans `/usr/local/libexec/static-release-receive` et non modifiable par les comptes de déploiement.
- Configuration du site : `/etc/static-release/learning-deploy.json`, root-owned ; fixe la racine publique, l’origine HTTPS et les fichiers obligatoires.
- Watchdog : `deploy/static-release@.service` et `.timer`, installés sous `/etc/systemd/system/` et activés pour chaque compte de déploiement.
- Nginx : `/etc/nginx/sites-available/learning-sites`, activé dans `sites-enabled` ; copie de `deploy/nginx.conf`.
- TLS : certificat Let's Encrypt pour `LEARNING_HOST`, renouvellement Certbot et hook de rechargement Nginx à provisionner.

Un changement du récepteur ou de Nginx demande une installation administrative explicite ; la CI ne peut modifier ni ces fichiers, ni les autres services :

```sh
sudo install -D -o root -g root -m 755 deploy/receive.py /usr/local/libexec/static-release-receive
sudo install -o root -g root -m 644 deploy/static-release@.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now static-release@learning-deploy.timer
# Seulement si la configuration Nginx change :
export LEARNING_HOST=learning.example.com
envsubst '${LEARNING_HOST}' < deploy/nginx.conf > /tmp/learning-sites-nginx.conf
sudo install -m 644 /tmp/learning-sites-nginx.conf /etc/nginx/sites-available/learning-sites
sudo nginx -t && sudo systemctl reload nginx
```

Aucun rechargement Nginx n’est nécessaire pour les publications de contenu.

### Clé SSH et restauration de la configuration

Définir les variables GitHub de dépôt `STATIC_ORIGIN` (origine HTTPS) et
`STATIC_DEPLOY_USER` (compte SSH restreint). Les passer comme entrées au workflow
partagé. Les URL de service sont publiques une fois déployées, mais ne sont pas
codées en dur dans les sources. L’environnement GitHub `production` contient :

- Secret **`STATIC_DEPLOY_KEY`** : clé privée Ed25519 dédiée au site ; aucune copie n’est conservée dans le dépôt ou sur le serveur.
- Secret **`STATIC_DEPLOY_KNOWN_HOSTS`** : clé publique d’hôte SSH, obtenue directement depuis `/etc/ssh/ssh_host_ed25519_key.pub`, pas par un `ssh-keyscan` non vérifié pendant la CI. La vérification d’hôte est obligatoire.

La clé autorisée utilise `restrict,command="/usr/local/libexec/static-release-receive --config /etc/static-release/learning-deploy.json"`. Seules les commandes `deploy`, `confirm` et `rollback`, suivies d’un identifiant `<commit>-<run>-<attempt>`, sont acceptées ; aucun shell ni sudo.

Pour une rotation, générer une nouvelle clé dédiée, installer sa clé publique avec les mêmes restrictions dans `authorized_keys`, puis envoyer la clé privée à GitHub via l’entrée standard, sans l’afficher :

```sh
gh secret set STATIC_DEPLOY_KEY --env production --repo alexalmny/learning-sites < /chemin/prive/cle
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
ORIGIN=https://learning.example.com python3 scripts/check_live.py
```

Ce contrôle compare toutes les pages du catalogue et le CSS au contenu attendu, vérifie HTTPS, les en-têtes et l’absence d’accès aux sources internes. Ces tests ne remplacent pas une vérification exhaustive des animations et calculs pédagogiques.

Le site est **public** : `noindex` et `robots.txt` ne sont pas un contrôle d’accès. Les supports cités gardent leurs conditions d’accès et de réutilisation ; certains liens Moodle nécessitent une authentification. Une fuite de la clé de déploiement permettrait de remplacer le contenu public de ce site ; elle ne donne pas de shell ni de droits sur les autres services.
