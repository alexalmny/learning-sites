# Learning Sites

Collection de cours interactifs : arbres rouge-noir, décisions de Markov, représentation des textes et règles d'association. Le portail relie quatre pages indépendantes, dont les animations et calculs s'exécutent dans le navigateur.

## Prérequis

- Un navigateur récent avec JavaScript activé.
- Python 3 pour l'aperçu local, ou un serveur HTTP statique pour la production.
- Node.js pour les vérifications.

## Installation et aperçu

```sh
git clone https://github.com/alexalmny/learning-sites.git
cd learning-sites
python3 -m http.server 8000 --bind 127.0.0.1
```

Ouvrir <http://localhost:8000>. Aucun paquet npm ni compilation n'est nécessaire. Le serveur Python sert uniquement à l'aperçu local.

## Déploiement sur une machine

Copier le dépôt sur la machine puis configurer un serveur HTTP pour servir ce répertoire. Par exemple, avec Caddy installé et un nom de domaine pointant vers le serveur, remplacer `cours.example.com` et le chemin dans ce fichier de configuration :

```caddyfile
cours.example.com {
    root * /srv/learning-sites
    encode zstd gzip
    file_server
}
```

Déposer les fichiers du dépôt dans `/srv/learning-sites`, appliquer la configuration Caddy et autoriser les ports 80 et 443. Caddy peut gérer automatiquement HTTPS lorsque le DNS, les ports et ses permissions sont configurés. Ne pas exposer le dossier `.git` : pour un déploiement simple, copier seulement `index.html` et les quatre dossiers de cours dans la racine web. Pour mettre à jour le site, remplacer ces fichiers par ceux de la version voulue.

Les pages sont des fichiers statiques ; aucun backend applicatif, base de données, secret ou service Node n'est nécessaire. Les liens vers Moodle et le dépôt de cours peuvent nécessiter une authentification. Les supports cités restent soumis à leurs conditions d'accès et de réutilisation ; vérifier les droits avant toute diffusion publique.

## Ajouter un cours

Créer un dossier avec un `index.html` autonome, ajouter un lien dans le portail puis lancer les vérifications. Préférer des chemins relatifs pour permettre l'hébergement sous un sous-chemin.

## Vérification et CI

```sh
python3 scripts/check.py
```

Le script vérifie la présence des pages, les liens locaux du portail et la syntaxe du JavaScript intégré avec Node. GitHub Actions lance ces contrôles sur les pushes vers `main` et les pull requests. Ces vérifications ne remplacent pas un essai manuel des animations, des calculs et de l'affichage mobile.
