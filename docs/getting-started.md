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

En cours de frappe, après avoir tapé `#@ ta demande` (sans `@#` fermant),
`Ctrl-G` déclenche la résolution immédiatement et insère le résultat dans
la ligne — pratique pour voir/corriger avant de valider avec Entrée.

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

Tape `Ctrl-G` (pas besoin de taper `@#`, ni d'appuyer sur Entrée) : la
ligne devient immédiatement `ls -S`, modifiable avant de valider avec
Entrée comme n'importe quelle commande bash normale.

**Piège à connaître** : si tu tapes la balise complète `#@ ... @#` et
appuies directement sur Entrée **sans** passer par Ctrl-G, bash traite
tout ce qui suit `#@` comme un **commentaire** (le `#` précédé d'un
espace) — la partie LLM est donc silencieusement ignorée, sans erreur.
Exemple : `ls #@ trie par taille @#` + Entrée directe exécute juste `ls`.
Il faut toujours résoudre avec `Ctrl-G` avant de valider.

Ce mécanisme appelle `bin/miniai-resolve-inline` à chaque `Ctrl-G` (donc
recharge le modèle à chaque fois, ~2s) — voir la limite connue plus bas si
la latence gêne à l'usage.

## 8. Le code : qui fait quoi

```text
bin/miniai                 point d'entrée bash du REPL
bin/miniai-resolve-inline  point d'entrée bash pour le Ctrl-G "natif" dans ta console
shell-integration/
  miniai.bash              fonction bash + `bind -x "\C-g"`, à sourcer dans ~/.bashrc
src/miniai/
  cli.py                   REPL (prompt_toolkit), mode -c, boucle principale, argparse
  inline.py                résolution ponctuelle appelée par bin/miniai-resolve-inline
  tags.py                  regex #@ ... @#, expand_line(), resolve_pending_tag()
  llm.py                   chargement du modèle GGUF, découverte du fichier, prompt, génération
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
  - `FEW_SHOT` — le gabarit de prompt (exemples + `{prefix}`/`█`/`{suffix}`).
  - `MiniLLM.generate_bash(request, prefix, suffix)` — charge le modèle
    au premier appel (lazy), construit le prompt, appelle
    `llama_cpp.Llama(...)`, renvoie le texte généré.
- **`src/miniai/shell.py`** — `PersistentShell` : un seul processus
  `bash --norc --noprofile` gardé ouvert (via `subprocess.Popen`), à qui
  on envoie chaque ligne suivie d'un `echo` avec un marqueur aléatoire
  unique pour savoir où s'arrête la sortie et récupérer le code de
  retour. C'est ce qui permet à `cd`, aux variables d'environnement, etc.
  de persister d'une ligne à l'autre.
- **`src/miniai/cli.py`** — assemble tout : `build_parser()` (argparse,
  option `-c`), `repl()` (boucle `prompt_toolkit` + `PersistentShell`),
  `run_once()` (mode `-c`), `build_key_bindings()` (branche `Ctrl-G` sur
  `resolve_pending_tag`).
- **`src/miniai/inline.py`** — variante non-interactive de la résolution
  `Ctrl-G` : reçoit `(ligne, position_curseur)` en arguments, appelle
  `resolve_pending_tag`, imprime la nouvelle ligne puis la nouvelle
  position sur deux lignes de stdout (lu par `shell-integration/miniai.bash`).

## 9. Configuration

Tout se fait par variables d'environnement, pas de fichier de config :

| Variable | Rôle | Défaut |
| --- | --- | --- |
| `MINIAI_MODEL_PATH` | Force le chemin exact du `.gguf`, court-circuite la recherche automatique | (aucun) |
| `MINIAI_MODEL_NAME` | Nom du modèle Ollama à chercher si `MINIAI_MODEL_PATH` n'est pas défini | `qwen2.5-coder` |
| `MINIAI_MODEL_TAG` | Tag du modèle Ollama à chercher | `1.5b-base` |
| `OLLAMA_MODELS` | Dossier où Ollama range ses modèles, utilisé par la recherche automatique | (voir ci-dessous) |

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

## 10. Dépannage rapide

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `FileNotFoundError: GGUF introuvable` | modèle non trouvé | voir étape 3 / section 9 |
| Réponse lente au premier appel | chargement du modèle | normal, ~2-4s |
| Ligne exécutée bizarre après résolution | modèle 1.5B + prompt minimal | voir "Limite connue" dans le README |
| `ModuleNotFoundError: llama_cpp` | venv pas utilisé | vérifier que `.venv/bin/python` existe et que `bin/miniai` le détecte |
| `Ctrl-G` ne fait rien dans mon terminal | `shell-integration/miniai.bash` pas sourcé | vérifier `~/.bashrc`, ouvrir un nouveau terminal |
| `#@ ... @#` exécuté tel quel / ignoré silencieusement | Entrée pressée sans passer par `Ctrl-G` d'abord | toujours résoudre avec `Ctrl-G` avant Entrée (voir section 7) |
