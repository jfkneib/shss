# Démarrage et premiers tests

## 1. Vérifier l'installation

Depuis la racine du dépôt :

```bash
ls .venv/bin/python || python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest tests/ -q
```

Les tests unitaires (`tests/`) ne chargent pas le modèle — ils valident le
parsing des balises et la logique CLI, donc ils passent même sans GPU/CPU
puissant et sans modèle présent.

## 2. Vérifier que le modèle est trouvable

```bash
./.venv/bin/python -c "from miniai.llm import discover_gguf_path; print(discover_gguf_path())"
```

- Si ça affiche un chemin `.gguf` → OK, passe à l'étape 3.
- Si ça lève `FileNotFoundError` → soit `ollama pull qwen2.5-coder:1.5b-base`
  n'a jamais été fait, soit le disque où sont stockés les modèles Ollama
  n'est pas monté, soit il faut pointer manuellement :

  ```bash
  export MINIAI_MODEL_PATH=/chemin/vers/qwen2.5-coder-1.5b-base.gguf
  ```

## 3. Premier essai en mode one-shot

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

## 4. Autres demandes à essayer

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

## 5. Mode console interactive (REPL)

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

## 6. Intégration dans ta console bash normale (sans lancer ./bin/miniai)

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

## 7. Dépannage rapide

| Symptôme | Cause probable | Action |
| --- | --- | --- |
| `FileNotFoundError: GGUF introuvable` | modèle non trouvé | voir étape 2 |
| Réponse lente au premier appel | chargement du modèle | normal, ~2-4s |
| Ligne exécutée bizarre après résolution | modèle 1.5B + prompt minimal | voir "Limite connue" dans le README |
| `ModuleNotFoundError: llama_cpp` | venv pas utilisé | vérifier que `.venv/bin/python` existe et que `bin/miniai` le détecte |
| `Ctrl-G` ne fait rien dans mon terminal | `shell-integration/miniai.bash` pas sourcé | vérifier `~/.bashrc`, ouvrir un nouveau terminal |
| `#@ ... @#` exécuté tel quel / ignoré silencieusement | Entrée pressée sans passer par `Ctrl-G` d'abord | toujours résoudre avec `Ctrl-G` avant Entrée (voir section 6) |
