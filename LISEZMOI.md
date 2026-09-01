# shss

***SH**ell **S**imple **S**uggestion*

*Version française. English: [README.md](README.md).*

Console bash augmentée : dans n'importe quelle ligne, un bloc `#@ demande @#`
est résolu par un petit LLM local avant exécution, et remplacé en place par
du bash. Le reste de la ligne est du bash normal, exécuté dans une vraie
session bash persistante (cd, variables d'environnement, etc. sont
conservés d'une ligne à l'autre).

## Installation via paquet Debian (.deb)

Le plus simple pour un usage courant — installe tout (dépendances Python
dans un venv dédié, modèle GGUF, intégration `Ctrl-G` dans `~/.bashrc`,
page de manuel) sans manipulation manuelle :

```bash
./packaging/build.sh
sudo apt install ./shss_0.2.3_all.deb
```

Le paquet installe dans `/opt/shss/` (venv Python, modèle, code), les
commandes `shss` / `shss-resolve-inline` dans `/usr/bin/`, et une
page de manuel (`man shss`). Il réutilise le modèle déjà présent via
Ollama s'il le trouve, sinon le télécharge depuis Hugging Face
(~950 Mo). Il ajoute aussi `source .../shell-integration/shss.bash` au
`~/.bashrc` de l'utilisateur qui a lancé `sudo` (variable `$SUDO_USER`) —
si ce n'est pas détecté, l'ajout manuel de cette ligne est affiché à
l'écran en fin d'installation.

Détails complets (contenu du paquet, scripts `postinst`/`postrm`,
suppression) dans [packaging/](packaging/).

## Installation via Docker

Pour **essayer** shss sans rien installer sur l'hôte, ou pour le
distribuer via un registre. Dans un conteneur, shss augmente le bash
**du conteneur** (pas celui de l'hôte) : idéal pour le mode `-c` et la
démo ; pour l'intégration `Ctrl-G` dans ton `~/.bashrc`, c'est le paquet
`.deb` qu'il faut.

Construire les images (une fois) :

```bash
docker build --target cpu  -t shss:cpu  .    # ~400 Mo sur disque, inférence CPU
docker build --target cuda -t shss:cuda .    # ~10 Go, GPU obligatoire (--gpus all)
```

L'image `cuda` embarque la wheel `llama-cpp-python` CUDA (pas de
compilation) ; elle **ne tourne qu'avec `--gpus all`** sur un hôte doté
du pilote NVIDIA (`libcuda.so.1` est fourni par le runtime conteneur au
lancement) — pas de repli CPU. Pour du CPU, utilise l'image `cpu`.

Puis, via le wrapper :

```bash
./run.sh                                 # REPL
./run.sh -c 'ls #@ trie par taille @#'   # one-shot
```

`run.sh` monte le dossier courant sur `/work`, garde le modèle dans un
volume `shss-models` (téléchargé une seule fois, ~941 Mo en `1.5b-base`),
passe `--gpus all` automatiquement si un GPU NVIDIA est détecté, et fixe
`SHSS_N_THREADS` au nombre de cœurs.

Le modèle n'est **pas** dans l'image ; l'entrypoint le télécharge au
premier lancement depuis la liste curatée de
[`src/shss/llm.py`](src/shss/llm.py). Choisir un modèle plus gros :

```bash
SHSS_MODEL_TAG=7b ./run.sh pull   # télécharge une fois dans le volume
SHSS_MODEL_TAG=7b ./run.sh        # puis l'utilise
```

Sans le wrapper :

```bash
docker volume create shss-models
docker run --rm -it \
  -v shss-models:/models -v "$PWD:/work" -w /work \
  shss:cpu
```

L'historique des résolutions est écrit dans le volume
(`/models/history.jsonl`), donc persistant. En revanche un résultat en
**mode script** est écrit dans le `/tmp` du conteneur : le chemin affiché
n'est pas accessible depuis l'hôte (limite inhérente au conteneur — le
mode fragment sur une ligne, lui, s'exécute normalement dans `/work`).

Alternative `compose` (profil `gpu` inclus) : voir
[compose.yaml](compose.yaml). L'image **`cpu`** est publiée sur GHCR à
chaque tag `v*` (`ghcr.io/jfkneib/shss:<version>` + `:latest`) et sur
`main` (`:edge`) — voir [.github/workflows/docker.yml](.github/workflows/docker.yml) ;
l'image `cuda` se construit en local.

**Podman** : `podman` remplace `docker` dans toutes les commandes
ci-dessus (`podman build`, `podman compose build`, `podman pull …`).
Pour le GPU, podman utilise `--device nvidia.com/gpu=all` au lieu de
`--gpus all` ; `run.sh` reste spécifique à Docker.

### Réglage des performances (variables d'env)

| Variable | Effet |
| --- | --- |
| `SHSS_N_THREADS` | nombre de threads d'inférence — à mettre au nombre de cœurs **physiques** (llama.cpp devine souvent mal en conteneur) ; `run.sh` utilise `nproc` |
| `SHSS_N_CTX` | fenêtre de contexte (défaut 2048) — `1024` suffit largement au prompt few-shot + aperçu de fichier, et réduit RAM et temps de *prompt-eval* |
| `SHSS_N_GPU_LAYERS` | `auto` (défaut) : tout offloader si `nvidia-smi` est présent, rien sinon. Un entier force la valeur. Sans effet sur un binaire llama.cpp compilé sans CUDA (donc l'image `cpu` ignore la variable). |
| `SHSS_MODEL_TAG` | `0.5b`, `1.5b-base` (défaut), `3b`, `7b` — le GPU n'apporte quasi rien sous 1.5b, mais devient utile en 7b |

Pense à donner assez de ressources au conteneur : `--cpus 4` au minimum,
et `--memory` ≥ 1,5 Go (1.5b) / 6 Go (7b).

## Mise à jour

Selon la méthode d'installation :

| Installé via | Mettre à jour |
| --- | --- |
| Paquet `.deb` | `cd <checkout> && git pull && ./packaging/build.sh && sudo apt install ./shss_<version>_all.deb` |
| Checkout git seul | `git pull` (rien d'autre) |
| Docker | `docker pull ghcr.io/jfkneib/shss:latest` (ou `git pull && docker build --target cpu -t shss:cpu .`) |

Dans tous les cas, ce qui est **conservé** : le modèle GGUF (jamais
re-téléchargé), le venv Python, la ligne `~/.bashrc`, et tes réglages
(`SHSS_MODEL_TAG`, `SHSS_MODEL_PATH`… vivent dans `~/.bashrc`, pas dans le
paquet). Le modèle Docker vit dans le volume `shss-models`, également
préservé.

**Piège `.deb`** : `apt install ./fichier.deb` ne met à jour que si la
version est **plus grande** — chaque release incrémente
`src/shss/__init__.py`. Pour forcer la même version :
`sudo apt install --reinstall ./shss_<version>_all.deb`.

### Via apt (`sudo apt upgrade`)

Le CI publie, à chaque tag `v*`, le `.deb` en pièce jointe de la
[Release](https://github.com/jfkneib/shss/releases) **et** dans un dépôt
apt plat sur la branche `apt`. Comme le dépôt GitHub est privé, apt s'y
authentifie avec un jeton personnel (scope `repo`, lecture seule
suffit) :

```bash
# 1. authentification (jeton dans un fichier lisible root uniquement)
sudo tee /etc/apt/auth.conf.d/shss.conf >/dev/null <<'EOF'
machine raw.githubusercontent.com
login x-access-token
password ghp_TON_JETON_ICI
EOF
sudo chmod 600 /etc/apt/auth.conf.d/shss.conf

# 2. la source apt
echo 'deb [trusted=yes] https://raw.githubusercontent.com/jfkneib/shss/apt/ ./' \
  | sudo tee /etc/apt/sources.list.d/shss.list

# 3. installer, puis mettre à jour comme n'importe quel paquet
sudo apt update && sudo apt install shss
sudo apt upgrade            # à chaque nouvelle release
```

Notes :

- `[trusted=yes]` : le dépôt n'est pas encore signé GPG (à ajouter).
- le fichier d'auth s'applique à **tout** `raw.githubusercontent.com` —
  acceptable sur une machine perso.
- `raw.githubusercontent.com` a un cache CDN (~5 min) : un `apt update`
  juste après une release peut ne pas voir la nouvelle version tout de
  suite.

Passer à un modèle plus petit/gros après coup :

```bash
sudo shss -c '#@ model download 0.5b @#'   # une fois (partagé machine)
echo 'export SHSS_MODEL_TAG=0.5b' >> ~/.bashrc && source ~/.bashrc
```

## Utilisation (depuis un checkout git, sans paquet)

```bash
./bin/shss
shss:/home/jfk$ ls #@ affiche aussi les fichiers caches @#
→ ls -la
...

shss:/home/jfk$ exit
```

Plusieurs demandes peuvent apparaître sur une même ligne, mélangées à du
bash classique :

```bash
ls #@ 1ère demande @#  #@ 2ème demande @#
```

Mode one-shot (comme `bash -c`) :

```bash
./bin/shss -c 'ls #@ affiche aussi les fichiers caches @#'
```

Dans le REPL, `Ctrl-G` résout immédiatement la balise la plus proche du
curseur — qu'elle soit déjà fermée par `@#` ou encore en cours de frappe —
sans attendre Entrée. Avant d'appliquer le résultat, `Ctrl-G` affiche ce
qui serait inséré (le fragment, ou le contenu complet du script en mode
script) et demande confirmation :

```text
shss propose :
-S

Utiliser ce résultat ? [O/n]
```

Répondre non (`n`) laisse la ligne inchangée, comme si `Ctrl-G` n'avait
pas été pressé — dans le REPL, rien n'est écrit ni journalisé tant que
tu n'as pas confirmé. Cette confirmation n'existe que pour `Ctrl-G` — la
résolution automatique d'une balise déjà fermée à l'Entrée (REPL ou `-c`)
reste directe, sans prompt, pour ne pas casser des usages non
interactifs.

### Intégration dans ta console bash normale (sans ./bin/shss)

`Ctrl-G` peut aussi être branché directement dans ta session bash
habituelle (pas besoin de lancer `./bin/shss`) :

```bash
echo 'source /home/jfk/git/dev/shss/shell-integration/shss.bash' >> ~/.bashrc
```

Contrairement au REPL, il n'y a **pas** de confirmation Oui/non ici :
lire une réponse au clavier depuis une fonction `bind -x` s'est avéré peu
fiable — testé et confirmé sur un vrai poste (terminal Terminator) :
même un `read` minimal, sans rapport avec shss, ne recevait aucune
touche (piège connu de bash, pas un bug shss — voir
`shell-integration/shss.bash` pour le détail). `Ctrl-G` affiche donc ce
qui a été généré (utile surtout en mode script, où la ligne ne montre
qu'un chemin de fichier) puis l'applique **directement** — la ligne reste
éditable avant Entrée, comme n'importe quelle commande bash, ce qui sert
de vérification.

Détails, limites et piège à connaître (bash traite `#@ ... @#` comme un
commentaire si on presse Entrée sans passer par `Ctrl-G` d'abord) dans
[docs/getting-started.md](docs/getting-started.md#7-intégration-dans-ta-console-bash-normale-sans-lancer-binshss).

## Modèle LLM

Le modèle utilisé est `qwen2.5-coder:1.5b-base`, chargé **directement** via
[`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python) (liaison
Python de llama.cpp) — pas de serveur Ollama à l'exécution. Le fichier
`.gguf` déjà téléchargé par Ollama pour ce modèle est réutilisé tel quel
(voir `src/shss/llm.py::discover_gguf_path`), sans le retélécharger.

Pour pointer vers un autre fichier `.gguf` :

```bash
export SHSS_MODEL_PATH=/chemin/vers/modele.gguf
```

**Ollama n'est pas requis.** Le code ne lance jamais le binaire `ollama`
ni ne contacte de serveur — il lit juste un fichier `.gguf` sur disque.
Ollama sert uniquement de raccourci pratique pour obtenir ce fichier sans
le télécharger soi-même (via `discover_gguf_path`, qui lit le manifest
qu'Ollama a laissé sur disque). Sans Ollama installé, `SHSS_MODEL_PATH`
vers n'importe quel `.gguf` (téléchargé par exemple depuis Hugging Face)
suffit à faire fonctionner shss de la même façon.

**Nuance pour les commandes utilitaires (section suivante) :** `#@ models @#`,
`#@ model <tag> @#` et `Ctrl-Y` ne peuvent lister/proposer que des modèles
**déjà gérés par Ollama** — c'est le seul « registre » de modèles
disponible sur disque, il n'y a pas d'équivalent générique pour un
`.gguf` isolé. Sans Ollama, `#@ models @#` l'indique clairement et
affiche quand même le modèle réellement actif (celui pointé par
`SHSS_MODEL_PATH`) plutôt que de laisser croire qu'il n'y a rien de
configuré ; pour changer de modèle dans ce cas, il faut changer
`SHSS_MODEL_PATH` toi-même.

## Scripts et historique

Pour une demande trop complexe pour tenir sur une ligne (plusieurs
étapes, transformation de fichier...), le modèle peut répondre par un
script complet au lieu d'un fragment bash — il choisit lui-même le
langage (Python, bash, ...) via la ligne shebang en tête de sa réponse
(`#!/usr/bin/env python3`, `#!/usr/bin/env bash`, ...). Le script est
écrit dans un fichier temporaire nommé par date + identifiant unique
(`/tmp/shss-<uid>/20260830-161859_d80a29.py`), rendu exécutable, et
c'est ce chemin qui remplace la balise dans la ligne :

```bash
#@ formate le fichier /tmp/dede.txt en json et écris le résultat dans /tmp/result.json @#
# → /tmp/shss-1000/20260830-161859_d80a29.py
```

Testé en réel : fonctionne, mais avec les mêmes limites de fiabilité
qu'ailleurs sur ce modèle 1.5B (ex: peut légèrement s'écarter du nom de
fichier demandé, ou ne pas gérer une structure de données complexe).

Pour aider le modèle à écrire un script adapté au **contenu réel** d'un
fichier plutôt que de deviner, un aperçu (quelques premières lignes) de
tout fichier explicitement nommé dans la demande est glissé dans le
prompt caché (`src/shss/context.py::build_context`) — invisible pour
l'utilisateur, qui ne voit toujours que ce qu'il tape. Sur un CSV avec
en-tête, le résultat est net (utilise `csv.DictReader`, bons noms de
clés) ; sur un format moins standard (ex: valeurs séparées par `;` sans
en-tête), le modèle sait qu'il doit utiliser le module `csv` mais ne
détecte pas toujours le bon séparateur tout seul. Volontairement, **aucun
listing du dossier courant n'est ajouté par défaut** : une première
version le faisait systématiquement et ça cassait des demandes simples
sans rapport avec des fichiers (`ls #@ trie par taille @#` générait un
résultat aberrant à cause de ce bruit non pertinent) — seul un fichier
explicitement mentionné (et qui existe) déclenche un aperçu.

Chaque résolution (fragment ou script) est enregistrée dans un
historique — `~/.shss/history.jsonl`, une ligne JSON par entrée
(horodatage, demande, résultat, type) :

```bash
shss --history        # les 20 dernières résolutions
shss --history 50     # les 50 dernières
```

`--history` n'a pas besoin de charger le modèle, donc c'est instantané.

## Commandes utilitaires

Certaines demandes entre `#@ ... @#` sont reconnues et traitées
directement par shss — jamais envoyées au LLM, donc instantanées :

```bash
#@ models @#                # liste les modèles Ollama + curatés, indique l'actif
#@ model 3b @#                # change de modèle (ex: 3b, ou deepseek-coder:1.3b)
#@ model download 3b @#       # télécharge un modèle curaté (sans Ollama)
#@ history 10 @#               # équivalent de shss --history 10
#@ help @#                     # rappelle ces commandes
```

`#@ model <tag> @#` change le modèle pour la suite de la session **REPL**
en cours ; en mode `-c` ou via `Ctrl-G` dans une console normale, chaque
appel relance un process, donc le changement ne survit pas à cette seule
résolution — exporte `SHSS_MODEL_TAG` dans `~/.bashrc` pour un
changement permanent, ou utilise le sélecteur `Ctrl-Y` ci-dessous, qui
lui persiste vraiment pour toute la session de terminal.

### Modèles téléchargeables sans Ollama

`#@ models @#` liste toujours, en plus des modèles Ollama, une liste
**curatée** de modèles `qwen2.5-coder` téléchargeables directement
depuis Hugging Face (URLs vérifiées à la main, Q4_K_M, sauf `0.5b` en
Q8_0) — c'est la seule famille testée/fiable avec le prompt de ce projet
(voir "Limites connues"). C'est ce qui répond au cas "pas d'Ollama
installé" :

```bash
#@ model download 3b @#   # télécharge ~1,9 Go
#@ model 3b @#             # l'active pour la session REPL en cours
```

Pour l'activer **en permanence** (y compris en mode `-c` et via
`Ctrl-G`), une fois le fichier téléchargé :

```bash
export SHSS_MODEL_TAG=3b   # dans ~/.bashrc ; discover_gguf_path() trouve
                           # le modèle curaté déjà téléchargé
```

Actuellement dans la liste : `0.5b` (~506 Mo, Q8_0), `1.5b-base`
(~941 Mo, le défaut), `3b` (~1,9 Go), `7b` (~4,5 Go). `0.5b` est le plus
léger (machine très contrainte, latence minimale) au prix d'une qualité
plus faible sur les demandes composées. Le téléchargement est bloquant
et peut prendre du temps selon la connexion ; il ne se déclenche **que**
sur cette commande explicite, jamais automatiquement.

**Licence des modèles.** `0.5b`, `1.5b-base` et `7b` sont sous
**Apache 2.0** (usage libre, y compris commercial). `3b` fait exception :
**Qwen Research License**, donc **usage non commercial / recherche
uniquement** — c'est le seul de la liste dans ce cas. shss n'embarque
aucun poids (il les télécharge depuis Hugging Face ou réutilise ceux
d'Ollama), donc distribuer shss lui-même ne pose pas de question de
licence modèle ; c'est l'usage que tu fais du modèle qui compte.

**Stockage — partagé si possible, individuel sinon** (le fichier
`.gguf` est partagé pour ne pas le retélécharger, mais **quel** modèle
est actif reste toujours un choix individuel, par session) :

- Lancé avec `sudo` (ex: `sudo shss -c '#@ model download 3b @#'`),
  le téléchargement va dans `/opt/shss/models/` — un seul
  téléchargement, **partagé par tous les utilisateurs de la machine**,
  cohérent avec l'installation via le paquet Debian ("installé une
  fois, tout le monde en bénéficie").
- Sans `sudo`, il va dans `~/.shss/models/` (par utilisateur) — un
  utilisateur normal ne peut pas écrire dans `/opt/shss/`.
- `#@ models @#` et `#@ model <tag> @#` consultent toujours l'emplacement
  partagé en premier, avant celui de l'utilisateur — si un admin a déjà
  téléchargé un modèle pour tout le monde, personne d'autre n'a besoin
  de le refaire.

### Sélecteur de modèle interactif (Ctrl-Y)

Si [`fzf`](https://github.com/junegunn/fzf) est installé
(`sudo apt install fzf`), `Ctrl-Y` (dans une console où
`shell-integration/shss.bash` est sourcé) ouvre une vraie liste
filtrable/navigable au clavier des modèles **activables** : ceux gérés
par Ollama, plus les modèles curatés déjà téléchargés. Le choix devient
actif pour le reste de la session de terminal (`export
SHSS_MODEL_NAME`/`SHSS_MODEL_TAG` dans le shell courant). Si la liste est
vide (pas d'Ollama, aucun modèle curaté téléchargé), `Ctrl-Y` l'indique
et rappelle `#@ model download <tag> @#`.

Ça n'a été possible qu'après avoir vérifié que `fzf` gère correctement
le terminal dans un contexte `bind -x` sur cette machine — contrairement
à un `read` de bash, qui n'y arrivait pas (voir la section précédente
sur la confirmation `Ctrl-G` retirée pour la même raison). `Ctrl-Y`
écrase la liaison readline par défaut (`yank`, coller le dernier texte
supprimé) — change la touche dans `shell-integration/shss.bash` si tu
t'en sers.

## Limites connues

`qwen2.5-coder:1.5b-base` est un petit modèle base avec un prompt few-shot
minimal (voir `src/shss/llm.py`) — il ne comprend pas toujours toute la
demande, surtout si elle **combine plusieurs critères**. Exemple observé :

```bash
ls #@ affiche les fichiers textes classer par taille @#
# → ls -S   (le tri est pris en compte, le filtre "fichiers textes" est ignoré)
```

Testé aussi avec un exemple few-shot dédié à ce cas précis (filtre +
tri) : aucune amélioration, même sur une demande presque identique à
l'exemple. Ce n'est donc pas un problème d'exemples manquants mais une
limite de capacité du modèle 1.5B sur ce type de raisonnement composé —
un modèle plus gros (3B/7B) serait nécessaire pour fiabiliser ce genre de
demande, au prix d'une latence plus élevée.

Le mécanisme lui-même (détection des balises, injection en place,
exécution) fonctionne correctement dans tous les cas testés — c'est la
qualité de la génération qui varie selon la complexité de la demande.

Autre piège observé et corrigé : sans pénalité de répétition,
`llama-cpp-python` peut faire boucler le modèle sur un motif dégénéré
jusqu'à la coupure de `max_tokens` — ex. une demande complexe a généré
`grep -E "^[^ ]+ [^ ]+ [^ ]+ ..."` répété des dizaines de fois, un
fragment cassé (guillemet jamais fermé) qui bloquait bash en attente de
la fin de la commande. `repeat_penalty=1.1` (voir `generate_bash` dans
`llm.py`) corrige cette classe de bug ; une valeur plus agressive
(testée à 1.3) a en revanche dégradé un cas qui marchait bien (fuite du
caractère `█` du prompt dans un script généré) — `1.1` est le compromis
retenu après ce test.

## Structure du dépôt

```text
bin/shss                 point d'entrée bash du REPL (utilise .venv si présent)
bin/shss-resolve-inline  point d'entrée pour l'intégration Ctrl-G dans bash
shell-integration/
  shss.bash              à sourcer dans ~/.bashrc : Ctrl-G "natif", Ctrl-Y (fzf)
src/shss/
  cli.py                   REPL / -c / --history / --list-models, Ctrl-G
  inline.py                résolution ponctuelle (utilisé par bin/shss-resolve-inline)
  tags.py                  détection/remplacement des balises #@ ... @#
  llm.py                   modèle GGUF, prompt, dispatch fragment/script, liste des modèles
  commands.py              commandes utilitaires (models, model, history, help)
  history.py               journal JSONL des résolutions (~/.shss/history.jsonl)
  context.py               aperçu des fichiers mentionnés, injecté dans le prompt caché
  shell.py                 session bash persistante (sentinel-based)
tests/                     tests (ne chargent pas le modèle, sauf mention contraire)
docs/                      documentation
```

## Développement

Prérequis : Python 3.9+, bash, un modèle GGUF `qwen2.5-coder:1.5b-base`
accessible (déjà présent via Ollama, ou `SHSS_MODEL_PATH`).

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
./.venv/bin/python -m pytest
```

Les tests n'importent ni `llama-cpp-python` ni `prompt_toolkit` (import
différé partout), donc `pip install -r requirements-dev.txt` seul suffit
pour lancer `pytest`.

## Licence

Apache License 2.0 — voir [LICENSE](LICENSE).
