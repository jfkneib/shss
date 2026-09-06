# grep-search

Deuxième profil de cas curatés pour shss (voir `docs/shss-cases.md` à
la racine du dépôt pour le mécanisme général, et `profiles/README.md`
pour la convention de structure). Domaine : recherche de fichiers par
**contenu** (logs, configs, code, docs) — `rg`/`grep`, avec repli sur
`grep` seul quand `rg` (ripgrep) n'est pas installé.

Comme `pc-stats/`, rien ne s'installe ou ne s'active tout seul : les
scripts sont fournis par ce dossier, mais la base de cas qui les rend
utilisables vit dans `~/.shss/profiles/grep-search/`, hors de ce dépôt
(voir « Récupérer la base opérationnelle » ci-dessous).

## Différence avec `pc-stats`

Dans `pc-stats`, presque chaque cas répond toujours la même chose
(`bilan de sante du pc` exécute toujours le même script). Ici, **le
motif recherché change à chaque demande** — chaque cas est donc un cas
« gabarit » (`--stdin`, voir `docs/shss-cases.md` section 4) : le
texte entre guillemets dans la demande est capturé, transmis au script
sur son entrée standard, jamais collé dans le code généré — aucun
risque d'injection même si le motif contient des guillemets, des
`$(...)`, etc.

## Cas curatés

| Cas | Script | Portée | Ce qu'il montre |
|---|---|---|---|
| `grep-motif` | `gs-grep` | répertoire **courant** de la console (`.`) | cas gabarit de base ; `rg` si présent (respecte `.gitignore`, ignore les binaires), repli `grep` sinon |
| `grep-motif-home` | `gs-grep` | `$HOME` de l'utilisateur | même script, portée différente — voir limite ci-dessous |

Les deux appellent le même outil, `linux/bin/gs-grep <repertoire>
<motif>` : la portée (cwd ou home) est fixée par le cas, pas décidée à
l'intérieur du script — plus simple que d'ajouter une détection de
portée en plus de la similarité sémantique, qui fait déjà ce tri entre
formulations (« ici »/« ce dossier » vs « mes fichiers »/« chez moi »/
« repertoire personnel »).

## Portée retenue (décision)

Deux portées seulement pour l'instant, volontairement : le répertoire
courant de la console (`.`, celui d'où la ligne shss est résolue — le
process shell de shss est persistant, donc `.` correspond bien au vrai
répertoire courant de la session, pas un chemin figé), et le répertoire
personnel (`$HOME`). Rien d'autre (chemin explicite dans la demande,
`/etc`, `/var/log`...) tant que ces deux-là n'ont pas fait leurs
preuves.

## Limites connues

- **Discrimination cwd/home pas toujours nette** : testé avec
  `shss-cases test`, le bon cas arrive toujours en tête mais parfois
  avec un écart de moins d'un point de similarité (`grep "TODO" ici` →
  71.5 % vs 70.8 %). Fonctionne aujourd'hui sur les formulations
  testées, mais fragile — à surveiller en ajoutant des demandes réelles
  au fil de l'usage plutôt que de faire confiance à l'écart actuel.
- **`$HOME` n'est pas un dossier "propre"** : au-delà de
  `.git`/`node_modules`/`.venv`/`.cache`/`__pycache__` (exclus dans
  `gs-grep`), un vrai `$HOME` contient des caches et journaux d'outils
  installés (ex. `~/.claude`, `~/.vscode-server`, profils de
  navigateur) impossibles à tous connaître à l'avance — constaté en
  testant ce script depuis `/tmp` : un motif de test s'est retrouvé
  matché dans le propre journal de session de l'outil en train
  d'écrire ce fichier. Pas de solution générale, juste le dire
  honnêtement plutôt que promettre un `$HOME` filtré à 100 %.
- **Pas de gestion de la casse/mots entiers/regex** dans les deux cas
  actuels — recherche littérale telle que tapée entre guillemets
  (`rg`/`grep` sans `-i`/`-w`/`-E`). Volontaire pour rester simple en
  V1 ; à revoir si le besoin se confirme.
- Seul Linux couvert (comme `pc-stats`) — `grep`/`rg` existent aussi
  sous Windows/macOS, donc ce profil serait un bon candidat pour
  tester tôt le routage `windows/`/`macos/` mentionné dans
  `profiles/README.md`, le jour où ça vaut le coup.

## Idées non retenues pour l'instant

Recherche dans les logs (`/var/log`, `.gz` via `zgrep`) et dans les
fichiers de config (`/etc`, `~/.config`) — permissions à gérer
proprement (souvent root-only) ; recherche restreinte par type de
fichier (`.md`, `.py`...) — capture d'un second paramètre limitée par
le mécanisme de cas gabarit (une seule chaîne entre guillemets
capturée par demande, voir `docs/shss-cases.md` section 8) ; `git
grep`/`git log -S` pour l'historique ; comptage d'occurrences ;
recherche de secrets en dur dans le code ; `fzf` interactif (nécessite
un vrai TTY — à valider avant d'écrire quoi que ce soit).

## Récupérer la base opérationnelle

Même mécanisme que `pc-stats` (voir son README pour le détail complet
des compromis) — depuis un clone git :

```bash
mkdir -p ~/.shss/profiles/grep-search/scripts
cp profiles/grep-search/cases.seed.json ~/.shss/profiles/grep-search/cases.json
cp -r profiles/grep-search/linux ~/.shss/profiles/grep-search/scripts/linux
./bin/shss-cases --profile grep-search reindex
```

Depuis le paquet `.deb` (`/opt/shss/profiles/grep-search/`), mêmes
commandes avec ce chemin, `shss-cases` sans le `./bin/`.

Ensuite, dans une ligne bash :

```bash
export SHSS_CASES_PROFILE=grep-search   # ou #@grep-search@ ... @# en ligne
#@ cherche "TODO" dans le code ici @#
```
