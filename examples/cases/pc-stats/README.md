# pc-stats

Boîte à outils autonome, à part de shss lui-même : shss reste un outil
de console (`#@ ... @#` → un script, exécuté une fois). Rien ici ne
s'installe ou ne tourne tout seul — chaque pièce se lance à la main,
volontairement, y compris le logging en arrière-plan.

## État actuel

- **`bin/pc-power`** — mesure la consommation électrique du moment
  (CPU/RAM/GPU/disques/écrans/USB + estimation carte mère/pertes
  alimentation). C'est le script du cas curaté `energie` de shss.
  `--csv` : une ligne compacte au lieu du tableau, même code de
  mesure.
- **`bin/pc-power-log`** — ajoute une ligne à `data/power.csv`. Rien ne
  l'appelle automatiquement ; lance-le à la main, ou installe le
  minuteur (voir plus bas) si tu veux un historique régulier.
- **`bin/pc-uptime`** — statistiques d'allumage/extinction pour un
  mois donné, à partir de `journalctl --list-boots` (fonctionne déjà
  rétroactivement, aucune donnée à collecter).
- **`lib/pc-stats-common.sh`** — logique partagée entre les outils
  ci-dessus.
- **`systemd/pc-power-log.{service,timer}`** — fichiers d'unité
  fournis en référence, **pas installés par défaut**. Testés une fois
  en mode utilisateur sur cette machine (4 septembre 2026), puis
  désinstallés délibérément — voir plus bas.
- **`data/power.csv`** — jamais versionné (`.gitignore`), contient
  quelques lignes de test.

## Pas encore fait

`pc-week`/`pc-month`/`pc-year`/`pc-report` (combinent `pc-uptime` et
une lecture de `data/power.csv`) et `pc-top-power`/`pc-gpu-stats`/
`pc-disk-stats`/`pc-cost`/`pc-export-csv` (format de sortie pas encore
précisé). Les kWh réels par mois ne sont possibles qu'à partir du
moment où `data/power.csv` accumule des données — pas rétroactivement,
contrairement à `pc-uptime`.

## Si tu veux le logging automatique

Volontairement **pas** activé par défaut. Pour l'installer toi-même :

```bash
mkdir -p ~/.config/systemd/user
cp systemd/pc-power-log.{service,timer} ~/.config/systemd/user/
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
