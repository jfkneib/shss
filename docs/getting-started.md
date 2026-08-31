# Démarrage, premiers tests, et comment ça marche

> **Toutes les commandes `./bin/miniai ...` de ce document supposent que
> tu es dans le dossier du dépôt** (`./` est un chemin relatif) :
>
> ```bash
> cd /home/jfk/git/dev/miniai
> ```
>
> Si tu es ailleurs (ex: `~`), bash renvoie
> `Aucun fichier ou dossier de ce nom`. Une fois `source
> shell-integration/miniai.bash` fait dans ton `~/.bashrc` (section 7),
> tu n'as par contre plus besoin d'être dans ce dossier ni de taper
> `./bin/miniai` du tout : `Ctrl-G` marche depuis n'importe où.

## 1. Comment ça marche, en bref

Le principe en 4 étapes, à chaque fois qu'une ligne contient `#@ demande @#` :

1. Tu tapes une ligne de bash normale, avec un ou plusieurs blocs
   `#@ demande en langage naturel @#` dedans, mélangés à du bash classique.
2. miniai repère ces blocs par une simple regex
   (`src/miniai/tags.py`).
3. Pour chaque bloc, le texte de la demande — **plus le contexte** (ce qui
   est écrit juste avant/après sur la ligne) — est envoyé à un petit LLM
   local, qui répond par un fragment de bash.
4. Ce fragment remplace la balise **exactement à sa place** dans la ligne.
   La ligne finale (bash normal + fragments générés) est alors exécutée.

Il y a deux façons de déclencher la résolution :

- **À l'exécution complète de la ligne** — dans le REPL `./bin/miniai` ou
  en mode `-c`, toute balise déjà fermée (`#@ ... @#`) est résolue
  automatiquement juste avant que la ligne parte au shell.
- **À la demande, via `Ctrl-G`** — résout la balise en train d'être tapée,
  même sans l'avoir fermée par `@#`. Ça marche aussi bien dans le REPL
  miniai que directement dans ta propre console bash (voir section 7).

Le LLM lui-même est un modèle **base** (pas chat/instruct) :
`qwen2.5-coder:1.5b-base`, chargé directement en mémoire par le process
Python via `llama-cpp-python` (liaison Python de llama.cpp), à partir du
fichier `.gguf` déjà présent sur le disque — celui qu'Ollama a téléchargé
— sans passer par le serveur/démon Ollama. Comme c'est un modèle base
(pas de format de chat), le code lui fournit un prompt "few-shot" (des
exemples de demande → fragment bash) pour qu'il complète par analogie.
Le détail exact de ce format de prompt est dans
`/home/jfk/miniai-llm-formats.md` (notes perso, hors dépôt).

## 2. Vérifier l'installation

Depuis la racine du dépôt :

```bash
ls .venv/bin/python || python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest tests/ -q
```

Les tests unitaires (`tests/`) ne chargent pas le modèle — ils valident le
parsing des balises et la logique CLI, donc ils passent même sans GPU/CPU
puissant et sans modèle présent.

## 3. Vérifier que le modèle est trouvable

```bash
./.venv/bin/python -c "from miniai.llm import discover_gguf_path; print(discover_gguf_path())"
```

- Si ça affiche un chemin `.gguf` → OK, passe à l'étape 4.
- Si ça lève `FileNotFoundError` → soit `ollama pull qwen2.5-coder:1.5b-base`
  n'a jamais été fait, soit le disque où sont stockés les modèles Ollama
  n'est pas monté, soit il faut pointer manuellement :

  ```bash
  export MINIAI_MODEL_PATH=/chemin/vers/qwen2.5-coder-1.5b-base.gguf
  ```

## 4. Premier essai en mode one-shot

Le plus simple pour tester sans rentrer dans le REPL — une ligne, un
résultat, ça quitte :

```bash
./bin/miniai -c 'ls #@ affiche aussi les fichiers caches @#'
```

Sortie attendue (le `→` montre la ligne réellement exécutée après
résolution de la balise par le LLM) :

```text
→ ls -la
total ...
drwxrwxr-x ...
```

Le premier appel est plus lent (~2-4s : chargement du modèle en mémoire),
les suivants sont plus rapides si le processus reste ouvert.

## 5. Autres demandes à essayer

```bash
./bin/miniai -c '#@ affiche la date du jour @#'
./bin/miniai -c 'ls #@ trie par taille @#'
./bin/miniai -c '#@ liste les fichiers python dans src/ @#'
```

Ces trois-là marchent bien avec le modèle 1.5B actuel (testés et vérifiés :
`date`, `ls -S`, `find src -iname "*.py"`). D'autres demandes
plus ambiguës (ex: mélanger `echo texte` + une vraie commande sur la même
ligne) peuvent donner un résultat bizarre — voir la limite connue dans le
README. C'est normal avec un petit modèle base et un prompt few-shot
minimal, pas un bug du mécanisme de balises/exécution.

## 6. Mode console interactive (REPL)

```bash
./bin/miniai
```

Puis, à l'invite `miniai:<dossier-courant>$` :

```text
miniai:/home/jfk/git/dev/miniai$ ls #@ affiche aussi les fichiers caches @#
→ ls -la
...
miniai:/home/jfk/git/dev/miniai$ cd src
miniai:/home/jfk/git/dev/miniai/src$ #@ liste les fichiers python ici @#
→ find . -iname "*.py"
...
miniai:/home/jfk/git/dev/miniai/src$ exit
```

Le `cd` est conservé d'une ligne à l'autre (vraie session bash persistante
derrière le REPL).

### Raccourci Ctrl-G

`Ctrl-G` résout la balise la plus proche du curseur — que tu l'aies fermée
par `@#` ou pas — et insère le résultat dans la ligne, sans attendre
Entrée. Marche aussi bien avec `#@ ta demande` (non fermée) qu'avec
`#@ ta demande @#` (fermée).

Avant d'insérer quoi que ce soit, `Ctrl-G` affiche ce qui serait utilisé
(le fragment, ou le script entier en mode script — voir section 8) et
demande confirmation : `Utiliser ce résultat ? [O/n]`. Dans le REPL,
tant que tu n'as pas confirmé, **rien n'est écrit ni journalisé** — la
confirmation se fait via `run_in_terminal()` de `prompt_toolkit`, qui
rend le terminal normal le temps de la question. Répondre non laisse la
ligne inchangée. C'est le seul moment où une confirmation est demandée :
la résolution automatique d'une balise fermée à l'Entrée (REPL/`-c`)
reste directe, pour ne pas gêner un usage scripté.

## 7. Intégration dans ta console bash normale (sans lancer ./bin/miniai)

Plutôt que de lancer un shell séparé, `Ctrl-G` peut être branché directement
dans ta session bash habituelle, via le mécanisme `bind -x` de bash (qui
expose `READLINE_LINE` / `READLINE_POINT`, modifiables par une fonction
shell).

Ajoute à `~/.bashrc` :

```bash
source /home/jfk/git/dev/miniai/shell-integration/miniai.bash
```

Puis ouvre un nouveau terminal (ou `source ~/.bashrc`). Ensuite, dans ton
prompt bash normal :

```text
jfk@jfk-XPS-8940 ~ $ ls #@ trie par taille
```

Tape `Ctrl-G` (pas besoin de fermer par `@#`, ni d'appuyer sur Entrée) :
miniai affiche ce qu'il a généré (`-S`), puis l'applique directement — la
ligne devient `ls -S`, modifiable avant de l'exécuter comme n'importe
quelle commande bash normale. Si tu préfères fermer la balise toi-même
(`ls #@ trie par taille @#`) avant de faire `Ctrl-G`, ça marche aussi —
dans les deux cas c'est `Ctrl-G` qui déclenche la résolution, jamais
Entrée seul.

**Pas de confirmation Oui/non ici**, contrairement au REPL (section 6).
Une première version en demandait une (comme dans le REPL), mais lire une
réponse au clavier *depuis le sous-processus Python* appelé par
`bind -x`, ou même directement via `read ... < /dev/tty` dans la fonction
bash elle-même, s'est avéré peu fiable — testé et confirmé en conditions
réelles (terminal Terminator) : même un `read` totalement indépendant de
miniai ne recevait aucune touche tant que la fonction tournait (seul
Ctrl-C débloquait). C'est un piège documenté de bash (`bind -x` + `read`
interactif), pas un bug miniai, et rien ne garantit qu'il ne se
reproduirait pas ailleurs — donc pas de confirmation bloquante ici. La
ligne éditable avant Entrée sert de vérification, comme avant l'ajout de
ce mécanisme.

**Piège à connaître** : si tu tapes la balise complète `#@ ... @#` et
appuies directement sur Entrée **sans** passer par Ctrl-G, bash traite
tout ce qui suit `#@` comme un **commentaire** (le `#` précédé d'un
espace) — la partie LLM est donc silencieusement ignorée, sans erreur.
Exemple : `ls #@ trie par taille @#` + Entrée directe exécute juste `ls`.
Il faut toujours résoudre avec `Ctrl-G` avant de valider.

Ce mécanisme appelle `bin/miniai-resolve-inline` à chaque `Ctrl-G` (donc
recharge le modèle à chaque fois, ~2s) — voir la limite connue plus bas si
la latence gêne à l'usage.

## 8. Scripts et historique

Pour une demande trop complexe pour tenir sur une ligne (plusieurs
étapes, transformation de fichier...), le modèle peut répondre par un
script complet au lieu d'un simple fragment bash. Il choisit lui-même le
langage en commençant sa réponse par une ligne shebang
(`#!/usr/bin/env python3`, `#!/usr/bin/env bash`, ...). Le script est
alors écrit dans un fichier temporaire nommé par date + identifiant
unique, rendu exécutable, et c'est ce chemin qui remplace la balise :

```bash
./bin/miniai -c '#@ formate le fichier /tmp/dede.txt en json et écris le résultat dans /tmp/result.json @#'
# → /tmp/miniai-1000/20260830-161859_d80a29.py
```

En mode `-c`/REPL (résolution à l'Entrée), le script est écrit **et
exécuté** directement, sans rien afficher au préalable — seul son chemin
apparaît dans la ligne. Via `Ctrl-G`, le script complet est affiché
avant d'être appliqué : avec confirmation Oui/non dans le REPL (section
6), ou juste affiché puis appliqué directement dans une console normale
(section 7, pas de confirmation possible dans ce contexte) — dans les
deux cas, c'est le moyen le plus sûr de relire ce qui va tourner avant
de valider avec Entrée.

Testé en réel — ça marche, avec les mêmes limites de fiabilité que le
reste sur ce modèle 1.5B (le nom de fichier exact ou la structure des
données peuvent légèrement s'écarter de la demande).

Chaque résolution (fragment ou script) est enregistrée dans un
historique JSON Lines, une ligne par entrée :

```bash
./bin/miniai --history        # les 20 dernières résolutions
./bin/miniai --history 50     # les 50 dernières
```

Fichier : `~/.miniai/history.jsonl` (surchargeable via
`MINIAI_HISTORY_PATH`). `--history` ne charge pas le modèle, donc c'est
instantané, même sans GPU/CPU disponible.

## 9. Commandes utilitaires et sélecteur de modèle

Certaines demandes entre `#@ ... @#` sont reconnues et traitées
directement par miniai — jamais envoyées au LLM, donc instantanées
(vérifié : `time ./bin/miniai -c '#@ models @#'` ≈ 0,07s, pas de
chargement du modèle) :

```bash
./bin/miniai -c '#@ models @#'                # liste les modèles, indique l'actif
./bin/miniai -c '#@ model 3b @#'               # change de modèle
./bin/miniai -c '#@ model download 3b @#'      # télécharge un modèle curaté
./bin/miniai -c '#@ history 5 @#'              # équivalent de --history 5
./bin/miniai -c '#@ help @#'                   # rappelle ces commandes
```

`model <tag>` accepte un tag seul (suppose `qwen2.5-coder`, ex: `3b`) ou
`nom:tag` complet (ex: `deepseek-coder:1.3b`) pour changer de famille de
modèle. Le changement persiste pour le reste de la session **REPL** en
cours, mais pas en mode `-c` ou via `Ctrl-G` dans une console normale —
chaque appel y relance un process, donc l'effet ne dépasse pas cette
seule résolution (message rappelé dans la sortie de la commande).

### Modèles curatés, téléchargeables sans Ollama

`#@ models @#` liste toujours, en plus des modèles Ollama, une petite
liste **curatée** de `qwen2.5-coder` (seule famille testée avec le
prompt de ce projet) téléchargeables directement depuis Hugging Face —
URLs vérifiées à la main avant d'être codées en dur, quantization
Q4_K_M :

| tag | taille |
| --- | --- |
| `1.5b-base` | ~941 Mo (le défaut) |
| `3b` | ~1,9 Go |
| `7b` | ~4,5 Go |

```bash
./bin/miniai -c '#@ model download 3b @#'   # télécharge dans ~/.miniai/models/
./bin/miniai -c '#@ model 3b @#'             # puis l'active (trouve le fichier)
```

Testé en réel (`1.5b-base`, ~941 Mo) : le téléchargement fonctionne, le
fichier est bien retrouvé et activé ensuite via `#@ model 1.5b-base @#`.
Bloquant (peut prendre du temps selon la connexion), et ne se déclenche
**que** sur cette commande explicite — jamais automatiquement, y
compris via `#@ model <tag> @#` sur un modèle non téléchargé (qui
indique juste la commande à taper plutôt que de télécharger tout seul).

C'est la réponse au cas "pas d'Ollama installé" : sans lui, `models` /
`model <tag>` seuls ne peuvent rien proposer d'autre qu'indiquer le
modèle réellement actif (`MINIAI_MODEL_PATH`) — voir "Nuance" dans le
README, section Modèle LLM.

### Ctrl-Y : sélecteur de modèle interactif

Testé et confirmé en conditions réelles : un vrai menu de sélection
(flèches, filtre en tapant) est possible dans le contexte `bind -x`, à
condition d'utiliser un outil qui gère lui-même le terminal en bas
niveau plutôt que le `read` de bash (qui, lui, échoue dans ce contexte —
voir section 7). [`fzf`](https://github.com/junegunn/fzf) est cet outil,
et c'est exactement ce que des intégrations bash connues (recherche
d'historique `Ctrl-R`, etc.) utilisent déjà avec succès.

```bash
sudo apt install fzf
```

Ensuite, dans une console où `shell-integration/miniai.bash` est
sourcé, `Ctrl-Y` ouvre la liste de tous les modèles Ollama présents
(`miniai --list-models` en coulisses, piped dans `fzf`). Le choix
devient actif pour le reste de la session de terminal — `export
MINIAI_MODEL_NAME`/`MINIAI_MODEL_TAG` est fait directement dans le shell
courant (pas dans un sous-processus), donc ça persiste vraiment,
contrairement à `#@ model <tag> @#`. Sans `fzf` installé, `Ctrl-Y`
affiche un message l'indiquant au lieu d'échouer silencieusement.

`Ctrl-Y` écrase la liaison readline par défaut `yank` (coller le
dernier texte supprimé avec Ctrl-K/Ctrl-U) — change la touche dans
`shell-integration/miniai.bash` (`bind -x '"\C-y": miniai_pick_model'`)
si tu t'en sers.

## 10. Le code : qui fait quoi

```text
bin/miniai                 point d'entrée bash du REPL
bin/miniai-resolve-inline  point d'entrée bash pour le Ctrl-G "natif" dans ta console
shell-integration/
  miniai.bash              bind -x "\C-g" (résolution) + "\C-y" (fzf), à sourcer
src/miniai/
  cli.py                   REPL (prompt_toolkit), -c / --history / --list-models
  inline.py                résolution ponctuelle appelée par bin/miniai-resolve-inline
  tags.py                  regex #@ ... @#, expand_line(), resolve_pending_tag()
  llm.py                   modèle GGUF, prompt, dispatch fragment/script, liste modèles
  commands.py              commandes utilitaires (models, model, history, help)
  history.py               journal JSONL des résolutions (~/.miniai/history.jsonl)
  context.py               aperçu des fichiers mentionnés, injecté dans le prompt caché
  shell.py                 session bash persistante (subprocess + marqueur sentinel)
requirements.txt           dépendances Python : llama-cpp-python, prompt_toolkit
tests/                     tests unitaires (chargent jamais le vrai modèle)
```

Le rôle précis de chaque fichier :

- **`bin/miniai`** — script bash minimal. Cherche `.venv/bin/python` (sinon
  se rabat sur `python3` système), met `src/` dans `PYTHONPATH`, lance
  `python -m miniai.cli`.
- **`bin/miniai-resolve-inline`** — même principe, mais lance
  `python -m miniai.inline`. Appelé par `shell-integration/miniai.bash` à
  chaque `Ctrl-G`, avec la ligne courante et la position du curseur en
  arguments.
- **`src/miniai/tags.py`** — logique pure, sans I/O :
  - `TAG_RE` = la regex `#@\s*(.*?)\s*@#`.
  - `find_requests(line)` — liste les demandes présentes dans une ligne.
  - `expand_line(line, resolver)` — remplace **toutes** les balises
    fermées d'une ligne (utilisé à l'exécution, REPL/`-c`).
  - `resolve_pending_tag(line, point, resolver)` — trouve la **dernière**
    balise ouverte avant le curseur et la résout (utilisé par `Ctrl-G`,
    dans le REPL comme dans l'intégration bash).
- **`src/miniai/llm.py`** :
  - `discover_gguf_path()` — cherche le fichier `.gguf` déjà téléchargé
    par Ollama, en lisant son manifest JSON. Voir "Configuration"
    ci-dessous pour l'ordre de recherche et comment le surcharger.
  - `FEW_SHOT` — le gabarit de prompt (exemples + `{prefix}`/`█`/`{suffix}`
    /`{context}`), y compris les exemples qui enseignent l'escalade vers
    un script (réponse commençant par un shebang) et l'usage du contexte
    fichier (exemple CSV avec en-tête → `csv.DictReader`).
  - `MiniLLM.generate_bash(request, prefix, suffix, confirm=None)` —
    vérifie d'abord `commands.try_builtin(request, self)` (voir plus bas) ;
    si reconnu, court-circuite tout le reste (pas de modèle chargé, pas
    de `confirm`, résultat enveloppé en script d'affichage via
    `_as_display_script()` + `_write_script()`, journalisé avec
    `kind="builtin"`). Sinon, charge le modèle au premier appel (lazy),
    appelle `context.build_context(request)` puis construit le prompt,
    appelle `llama_cpp.Llama(...)` (avec `repeat_penalty=1.1` — voir
    "Limites connues" dans le README pour le bug de répétition dégénérée
    que ça corrige). Détermine le texte à afficher/utiliser (script
    entier si la réponse commence par `#!`, sinon sa première ligne). Si
    `confirm` est fourni, l'appelle avec ce texte ; un retour faux lève
    `ResolutionCancelled` (rien n'est écrit ni journalisé). Sinon, écrit le
    script via `_write_script()` dans `SCRIPT_DIR` (`/tmp/miniai-<uid>/`)
    et journalise le résultat via `history.log_event()`.
  - `ResolutionCancelled` — exception levée quand `confirm` refuse ;
    attrapée par `cli.py`/`inline.py` pour laisser la ligne inchangée.
  - `list_local_models()` — parcourt `_KNOWN_OLLAMA_DIRS` et liste tous
    les `(nom, tag)` dont un manifest existe, sans filtrer par
    compatibilité (utilisé par `commands.py` et `cli.py --list-models`).
  - `MiniLLM.switch_model(model=None, tag=None, path=None)` — recharge
    `self.model_path` via `discover_gguf_path()` (ou un chemin direct) et
    vide `self._llm` pour forcer un rechargement lazy au prochain appel.
- **`src/miniai/commands.py`** — `try_builtin(request, mini_llm)` :
  reconnaît `models`, `model <tag>`, `history [N]`, `help` (insensible à
  la casse) et retourne le texte à afficher, ou `None` si `request` n'est
  pas une commande connue (le flux normal vers le LLM reprend alors).
  Volontairement du texte pur, jamais de picker interactif à navigation
  clavier ici — voir section 9 pour pourquoi (et où ce picker existe
  quand même, côté bash, via `fzf`).
- **`src/miniai/history.py`** — `log_event(...)` ajoute une ligne JSON à
  `~/.miniai/history.jsonl` (ou `MINIAI_HISTORY_PATH`) ; `read_events(limit)`
  relit les dernières entrées, utilisé par `cli.py --history`.
- **`src/miniai/context.py`** — `build_context(request)` : repère les
  noms de fichiers plausibles dans la demande (regex), et pour ceux qui
  existent vraiment sur disque, ajoute un aperçu (5 lignes / 300
  caractères max) au prompt caché envoyé au modèle. N'ajoute
  délibérément **aucun** listing du dossier courant par défaut — une
  version antérieure le faisait et ça cassait les demandes simples sans
  rapport avec des fichiers (bruit non pertinent pour le modèle).
- **`src/miniai/shell.py`** — `PersistentShell` : un seul processus
  `bash --norc --noprofile` gardé ouvert (via `subprocess.Popen`), à qui
  on envoie chaque ligne suivie d'un `echo` avec un marqueur aléatoire
  unique pour savoir où s'arrête la sortie et récupérer le code de
  retour. C'est ce qui permet à `cd`, aux variables d'environnement, etc.
  de persister d'une ligne à l'autre.
- **`src/miniai/cli.py`** — assemble tout : `build_parser()` (argparse,
  option `-c`/`--history`), `repl()` (boucle `prompt_toolkit` +
  `PersistentShell`), `run_once()` (mode `-c`, sans confirmation),
  `build_key_bindings()` (branche `Ctrl-G` sur un handler **async**
  `async def _(event)`, requis pour pouvoir faire
  `await run_in_terminal(do_resolve)` — la fonction `run_in_terminal` du
  module `prompt_toolkit.application` (PAS une méthode de `Application`,
  contrairement à ce qu'un essai précédent supposait) hand le terminal en
  mode normal le temps de `do_resolve()`, qui appelle
  `resolve_pending_tag(...)` avec un `confirm=ask_confirm` — tout ça
  bloque via `input()` en toute sécurité pendant ce laps de temps.
  `ResolutionCancelled` y est attrapée pour laisser le buffer inchangé si
  l'utilisateur refuse ; dans ce cas rien n'a encore été écrit ni
  journalisé, puisque `confirm` est appelée par `generate_bash` avant
  d'écrire le script ou d'appeler `history.log_event()`.
- **`src/miniai/inline.py`** — variante non-interactive de la résolution
  `Ctrl-G`, utilisée par `bin/miniai-resolve-inline` (appelé depuis
  `shell-integration/miniai.bash`). Ne demande **jamais** de confirmation
  elle-même — son `confirm` interne (`record_display`) se contente de
  mémoriser le texte généré et répond toujours vrai, donc la génération
  se termine normalement (script écrit, historique journalisé) sans
  jamais bloquer sur une entrée clavier. Elle imprime trois choses sur
  stdout : la nouvelle ligne, la nouvelle position, puis le texte généré
  à afficher (vide si aucune balise n'a été résolue, sur plusieurs lignes
  pour un script). `shell-integration/miniai.bash` lit ces trois parties
  (`sed`/`tail`), affiche la troisième à titre informatif si non vide, et
  applique `READLINE_LINE`/`READLINE_POINT` directement — sans demander
  Oui/non (contrairement au REPL). Une version antérieure demandait une
  confirmation ici aussi, via le `read` intégré de bash ; retirée après
  avoir confirmé en conditions réelles qu'un `read` interactif — même
  minimal, sans rapport avec miniai, même lu depuis `/dev/tty` — ne
  recevait aucune touche pendant qu'une fonction `bind -x` tournait (sauf
  Ctrl-C). Piège documenté de bash, pas un bug miniai, mais pas assez
  fiable pour en dépendre.

## 11. Configuration

Tout se fait par variables d'environnement, pas de fichier de config :

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `MINIAI_MODEL_PATH` | Force le chemin exact du `.gguf`, court-circuite la recherche automatique | (aucun) |
| `MINIAI_MODEL_NAME` | Nom du modèle Ollama à chercher si `MINIAI_MODEL_PATH` n'est pas défini | `qwen2.5-coder` |
| `MINIAI_MODEL_TAG` | Tag du modèle Ollama à chercher | `1.5b-base` |
| `OLLAMA_MODELS` | Dossier où Ollama range ses modèles, utilisé par la recherche automatique | (voir ci-dessous) |
| `MINIAI_HISTORY_PATH` | Chemin du fichier d'historique JSON Lines | `~/.miniai/history.jsonl` |

Sans `MINIAI_MODEL_PATH`, `discover_gguf_path()` (dans `llm.py`) cherche le
manifest `registry.ollama.ai/library/<name>/<tag>` dans, dans l'ordre :

1. `$OLLAMA_MODELS`
2. `~/.ollama/models`
3. `/usr/share/ollama/.ollama/models`
4. `/media/jfk/Ollama/MODEL_OLLAMA` (chemin codé en dur pour cette
   machine précise — c'est là qu'Ollama stocke ses modèles ici, voir
   `OLLAMA_MODELS` dans le service systemd `ollama`)

Le 4e emplacement est spécifique à cette machine et ne marchera pas tel
quel ailleurs — si le dépôt part sur une autre machine/GitHub, corriger ou
supprimer cette entrée dans `_KNOWN_OLLAMA_DIRS` (`src/miniai/llm.py`),
ou toujours passer par `MINIAI_MODEL_PATH`.

### Dépendances (`requirements.txt`)

```text
llama-cpp-python   # charge et fait tourner le .gguf (liaison Python de llama.cpp)
prompt_toolkit     # REPL avec édition de ligne + raccourci Ctrl-G
```

Installées dans `.venv/` (voir étape 2), pas au niveau système — la
machine est en environnement Python "externally managed" (Debian/Ubuntu),
d'où le `python3 -m venv .venv` plutôt qu'un `pip install` direct.

## 12. Dépannage rapide

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `FileNotFoundError: GGUF introuvable` | modèle non trouvé | voir étape 3 / section 11 |
| Réponse lente au premier appel | chargement du modèle | normal, ~2-4s |
| Ligne exécutée bizarre après résolution | modèle 1.5B + prompt minimal | voir "Limite connue" dans le README |
| `ModuleNotFoundError: llama_cpp` | venv pas utilisé | vérifier que `.venv/bin/python` existe et que `bin/miniai` le détecte |
| `Ctrl-G` ne fait rien dans mon terminal | `shell-integration/miniai.bash` pas sourcé | vérifier `~/.bashrc`, ouvrir un nouveau terminal |
| `#@ ... @#` exécuté tel quel / ignoré silencieusement | Entrée pressée sans passer par `Ctrl-G` d'abord | toujours résoudre avec `Ctrl-G` avant Entrée (voir section 7) |
| `Ctrl-Y` affiche juste un message, pas de liste | `fzf` non installé | `sudo apt install fzf` (voir section 9) |
