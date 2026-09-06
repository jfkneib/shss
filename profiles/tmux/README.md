# tmux

Troisième profil de cas curatés pour shss (voir `docs/shss-cases.md` à
la racine du dépôt pour le mécanisme général, et `profiles/README.md`
pour la convention de structure). Domaine : sessions persistantes /
multiplexage via `tmux` — lister, créer, reprendre, fermer une session.

`screen` volontairement laissé de côté pour l'instant : `tmux` domine
largement l'usage aujourd'hui, doubler chaque cas pour un second outil
avant d'en avoir besoin réellement n'aurait fait que doubler le travail
sans bénéfice mesuré. Un `screen-*` pourrait s'ajouter à côté plus
tard, sur le même modèle, sans rien changer à ce qui existe déjà.

Comme les profils précédents, rien ne s'installe ou ne s'active tout
seul : voir « Récupérer la base opérationnelle » ci-dessous.

## Le point qui a guidé toute la conception : la contrainte de terminal

`tmux new -s X` / `tmux attach -t X` prennent le contrôle plein écran
du terminal — contrairement à `pc-power` ou `gs-grep` (voir
`profiles/pc-stats/`, `profiles/grep-search/`) qui impriment juste du
texte et rendent la main. Or shss exécute une ligne résolue de deux
façons différentes :

- **Intégration bashrc/`Ctrl-G`** : la ligne résolue est collée dans le
  vrai prompt bash de l'utilisateur, qui appuie ensuite sur Entrée —
  ça tourne dans un vrai terminal.
- **REPL shss / mode `-c`** : la ligne tourne dans `PersistentShell`
  (`src/shss/shell.py`) — un `subprocess.Popen` avec de simples tubes
  (`stdin=PIPE`, `stdout=PIPE`), **sans pseudo-terminal**.

**Vérifié en pratique** (pas supposé) avant d'écrire le moindre script,
avec `tmux` réellement installé sur cette machine :

- via un shell sans TTY (reproduisant exactement `PersistentShell`) :
  `tmux new -s X` échoue immédiatement avec `open terminal failed: not
  a terminal`, code de sortie 1, aucune session créée.
- via un vrai pseudo-terminal (reproduisant `Ctrl-G`/bashrc, testé avec
  Python `pty.openpty()` + `TERM=xterm-256color`) : `tmux new -s X`
  fonctionne normalement (prend le terminal, affiche l'interface tmux),
  se détache proprement sur `Ctrl-b d`, la session reste active en
  arrière-plan.
- `tmux ls`, `tmux new -d -s X` (détaché), `tmux new-window`,
  `tmux rename-session`, `tmux kill-session`, `tmux kill-server` :
  tous fonctionnent sans le moindre souci sans TTY — aucune contrainte
  pour ceux-là.

**Conséquence directe sur les scripts** : `tm-new-session` et
`tm-attach` (les deux seuls cas interactifs) commencent par
`[ ! -t 0 ] || [ ! -t 1 ]` et refusent avec un message clair plutôt que
de laisser filer l'erreur brute de tmux si le terminal n'est pas réel —
testé dans les deux configurations (avec et sans TTY réel, voir
ci-dessus).

## Cas curatés

| Cas | Script | Interactif ? | Ce qu'il montre |
|---|---|---|---|
| `tmux-liste` | `tm-list` | non | Cas de base, sûr partout — gère proprement le cas "aucun serveur tmux" (tmux renvoie 1, ce n'est pas une vraie erreur) |
| `tmux-tuer-session` | `tm-kill-session` | non | Cas gabarit (nom de session variable) ; vérifie l'existence avant d'agir (`tmux has-session`) plutôt que de laisser tmux échouer avec un message brut |
| `tmux-tuer-tout` | `tm-kill-all` | non | `tmux kill-server` — destructif mais non interactif, aucune confirmation propre au script (même convention que les autres cas : la confirmation "utiliser ce résultat ?" a déjà eu lieu côté shss) |
| `tmux-nouvelle-session` | `tm-new-session` | **oui** | Garde TTY ; si la session existe déjà, s'y rattache plutôt que d'échouer sur "session déjà existante" |
| `tmux-reprendre-session` | `tm-attach` | **oui** | Garde TTY ; nom donné → erreur claire si absente (liste les sessions existantes) |
| `tmux-reprendre-defaut` | `tm-attach` (sans argument) | **oui** | Pas de nom précisé → sonde `tmux list-sessions` au runtime (jamais deviné) : une seule session → s'y attache, plusieurs → les liste et demande de préciser, aucune → le dit clairement |

## Limite connue : marges de similarité serrées entre cas voisins

Les six cas parlent tous de « session tmux » — `shss-cases test` montre
le bon cas en tête à chaque fois, mais parfois avec un écart modeste
avec le second (`tmux-nouvelle-session` vs `tmux-tuer-session` : 100 %
contre 96.3 % sur `'tue la session tmux "travail"'` normalisé). Comme
pour `grep-motif`/`grep-motif-home` dans `profiles/grep-search/`,
fonctionne aujourd'hui sur les formulations testées mais à surveiller
en ajoutant des demandes réelles, pas à considérer comme acquis.

## Récupérer la base opérationnelle

Même mécanisme que les profils précédents — depuis un clone git :

```bash
mkdir -p ~/.shss/profiles/tmux/scripts
cp profiles/tmux/cases.seed.json ~/.shss/profiles/tmux/cases.json
cp -r profiles/tmux/linux ~/.shss/profiles/tmux/scripts/linux
./bin/shss-cases --profile tmux reindex
```

Depuis le paquet `.deb` (`/opt/shss/profiles/tmux/`), mêmes commandes
avec ce chemin, `shss-cases` sans le `./bin/`.

Ensuite, dans une ligne bash :

```bash
export SHSS_CASES_PROFILE=tmux   # ou #@tmux@ ... @# en ligne
#@ liste mes sessions tmux @#
```

Pour les cas interactifs (`tmux-nouvelle-session`, `tmux-reprendre-*`),
utilise l'intégration bashrc/`Ctrl-G` (`shell-integration/shss.bash`)
plutôt que le REPL ou `-c` — voir plus haut pourquoi.
