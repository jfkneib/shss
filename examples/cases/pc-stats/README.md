# pc-stats

Boîte à outils autonome, à part de shss lui-même : shss reste un outil
de console (`#@ ... @#` → un script, exécuté une fois). Rien ici ne
s'installe ou ne tourne tout seul — chaque pièce se lance à la main,
volontairement, y compris le logging en arrière-plan.

C'est aussi l'exemple concret du mécanisme de cas curatés de shss :
chaque script ci-dessous est câblé comme un cas dans le profil
`pc-stats` (voir `docs/shss-cases.md` à la racine du dépôt pour le
mécanisme général — profils, cas gabarit, variables d'environnement).

## Récupérer la base opérationnelle après un `git pull`

**Important à savoir** : `git pull` seul ne suffit pas. Les scripts
(`linux/bin/pc-*`, `linux/lib/`) sont versionnés, mais la base de cas
qui les rend réellement utilisables (`~/.shss/profiles/pc-stats/`) vit
**hors du dépôt**, dans ton `$HOME` — jamais écrasée par un pull, pour
ne pas effacer des cas que tu aurais ajoutés toi-même.

`cases.seed.json`, à côté de ce README, est un instantané de la base
curatée (les demandes-exemples + de petits scripts d'appel, texte pur,
rien de propre à une machine — voir plus bas). Pour l'installer (ou la
mettre à jour après un pull) :

```bash
mkdir -p ~/.shss/profiles/pc-stats/scripts
cp examples/cases/pc-stats/cases.seed.json ~/.shss/profiles/pc-stats/cases.json
cp -r examples/cases/pc-stats/linux ~/.shss/profiles/pc-stats/scripts/linux
./bin/shss-cases --profile pc-stats reindex
```

Le `reindex` est indispensable et prend quelques secondes : c'est lui
qui calcule `cases.embeddings.json`, le cache de vecteurs de
similarité. Ce fichier-là ne se copie et ne se partage **jamais**
(dérivé, propre au modèle d'embeddings de la machine qui l'a
généré) — toujours régénéré localement.

Si tu as déjà des cas à toi dans ce profil, les `cp` ci-dessus les
écraseraient : fusionne à la main (`shss-cases list` sur les deux
fichiers, et compare les deux `scripts/linux/`) plutôt que de copier
aveuglément.

Ensuite, pour t'en servir tel quel dans une ligne bash :

```bash
export SHSS_CASES_PROFILE=pc-stats     # ou #@pc-stats@ ... @# en ligne
#@ bilan de sante du pc @#
```

## État actuel

11 cas curatés dans le profil `pc-stats`, chacun avec son script sous
`linux/bin/` : la colonne « Script » ci-dessous, c'est où *lire et
modifier* chaque outil.

**Répertoire par OS** : `bin/`, `lib/` et `systemd/` sont rangés sous
`linux/` — pas juste pour ranger, ces outils dépendent tous de Linux
(`/sys`, `systemctl`, `journalctl`, `apt`, `virsh`...), rien de portable
vers un autre OS. Le jour où un `pc-power` Windows/macOS aurait un
sens, il vivrait dans un `windows/`/`macos/` à côté, avec sa propre
implémentation — sans rien bouger dans `linux/` ni dans la logique des
cas eux-mêmes. `data/` (juste des lignes CSV, pas du code) reste au
niveau du profil : le format de `power.csv` n'a pas de raison de
dépendre de l'OS qui l'a produit.

**Architecture des cas** : chaque cas est un petit script d'appel
(quelques lignes) qui exécute le vrai outil via
`$SHSS_PROFILE_DIR/scripts/linux/bin/<nom>` — une variable
d'environnement que shss fournit à tout cas qui matche (voir
`docs/shss-cases.md`), pointant vers le répertoire du profil actif sur
la machine courante (`~/.shss/profiles/pc-stats/` ici). Jamais un
chemin codé en dur vers ce dépôt : `SHSS_PROFILE_DIR` reste valide
partout où le profil a été installé, contrairement à un chemin vers un
clone git précis. `uptime` illustre bien la logique : son cas extrait
juste le mois demandé (`SHSS_REQUEST` ou stdin), puis appelle
`$SHSS_PROFILE_DIR/scripts/linux/bin/pc-uptime` qui, lui, source
`lib/pc-stats-common.sh` à côté de lui — d'où l'étape `cp -r
examples/cases/pc-stats/linux` ci-dessus, qui embarque `bin/` et
`lib/` ensemble.

Deux cas (`disques`, `uptime`) avaient d'abord été ajoutés avec un
chemin codé en dur vers ce dépôt (`/home/jfk/git/dev/shss/...`) —
fonctionnait par hasard tant que tout était lancé depuis cette
machine avec ce clone à cet endroit, cassait sinon. `SHSS_PROFILE_DIR`
corrige ça pour de bon : après modification d'un script sous
`linux/bin/` ou `linux/lib/`, une simple recopie (`cp -r` comme
ci-dessus, ou juste le fichier modifié) suffit à répercuter le
changement — aucun cas n'a besoin d'être réédité pour ça, contrairement
à l'ancien schéma où chaque cas embarquait sa propre copie du script.

| Cas              | Script             | Ce qu'il montre |
|------------------|--------------------|--------|
| `energie`        | `pc-power`         | Consommation électrique estimée (CPU/RAM/GPU/disques/écrans/USB), `--csv` pour une ligne compacte |
| `uptime`         | `pc-uptime`        | **Cas gabarit** : allumage/extinction pour un mois donné (`journalctl --list-boots`), mois en paramètre libre dans la demande, courant par défaut |
| `disques`        | `pc-disk-info`     | Détail par disque (modèle, santé, partitions) |
| `temperatures`   | `pc-temp-info`     | Sondes hwmon + température GPU |
| `gpu`            | `pc-gpu-info`      | Détail carte graphique + processus qui l'utilisent |
| `reseau`         | `pc-net-info`      | Interfaces physiques en détail, virtuelles en liste compacte |
| `services`       | `pc-service-info`  | Services systemd : chargés/actifs/en échec, top 10 mémoire |
| `paquets`        | `pc-pkg-info`      | Mises à jour dispo, paquets cassés, orphelins |
| `docker`         | `pc-docker-info`   | Conteneurs/images/volumes/réseaux Docker |
| `virtualisation` | `pc-vm-info`       | VM KVM/libvirt : résumé + détail des VM en cours |
| `sante`          | `pc-report`        | Agrégateur : croise tout ce qui précède et signale ce qui mérite un œil (disque plein, service en échec, charge, RAM, conteneur planté) |

Plus, autonomes (pas de cas dédié — support pour `energie`) :

- **`linux/bin/pc-power-log`** — ajoute une ligne à `data/power.csv`.
  Rien ne l'appelle automatiquement ; lance-le à la main, ou installe
  le minuteur (voir plus bas) si tu veux un historique régulier.
- **`linux/lib/pc-stats-common.sh`** — logique partagée entre les
  outils.
- **`linux/systemd/pc-power-log.{service,timer}`** — fichiers d'unité
  fournis en référence, **pas installés par défaut**. Testés une fois
  en mode utilisateur sur cette machine (4 septembre 2026), puis
  désinstallés délibérément — voir plus bas.
- **`data/power.csv`** — jamais versionné (`.gitignore`).

## Pas encore fait

Historique/tendances à partir de `data/power.csv` (rien ne l'exploite
encore, seul `pc-power-log` l'alimente) ; identité machine synthétique
(déjà en partie couverte par l'en-tête de `pc-power` — hostname/
kernel/CPU/RAM) ; USB/PCI, utilisateurs/sessions, sécurité/ports,
DNS/routes, logs/erreurs récents.

## Si tu veux le logging automatique

Volontairement **pas** activé par défaut. Pour l'installer toi-même :

```bash
mkdir -p ~/.config/systemd/user
cp linux/systemd/pc-power-log.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pc-power-log.timer
```

**Compromis root/utilisateur**, à choisir en connaissance de cause :

- **Utilisateur** (`systemctl --user`, ci-dessus) : aucun sudo pour
  installer, `data/power.csv` reste possédé par toi. Le CPU (RAPL)
  reste à 0 W dans le log (`cpu_mesure=0`) — `sudo` ne peut pas
  demander de mot de passe depuis un minuteur sans terminal. Le reste
  (GPU/RAM/disques/écrans) continue d'être mesuré/estimé normalement.
- **Root** (service système, `/etc/systemd/system/`, `sudo systemctl
  enable --now`) : le CPU se mesure réellement (root a l'accès RAPL
  direct), mais `data/power.csv` devient root:root (lecture libre,
  édition/suppression nécessitent `sudo`).

Si le minuteur en mode utilisateur est installé et que tu veux qu'il
continue même déconnecté (pas seulement pendant une session ouverte) :

```bash
sudo loginctl enable-linger jfk
```
