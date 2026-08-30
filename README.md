# miniai

Console bash augmentée : dans n'importe quelle ligne, un bloc `#@ demande @#`
est résolu par un petit LLM local avant exécution, et remplacé en place par
du bash. Le reste de la ligne est du bash normal, exécuté dans une vraie
session bash persistante (cd, variables d'environnement, etc. sont
conservés d'une ligne à l'autre).

## Utilisation

```bash
./bin/miniai
miniai:/home/jfk$ ls #@ affiche aussi les fichiers caches @#
→ ls -la
...

miniai:/home/jfk$ exit
```

Plusieurs demandes peuvent apparaître sur une même ligne, mélangées à du
bash classique :

```bash
ls #@ 1ère demande @#  #@ 2ème demande @#
```

Mode one-shot (comme `bash -c`) :

```bash
./bin/miniai -c 'ls #@ affiche aussi les fichiers caches @#'
```

Dans le REPL, `Ctrl-G` résout immédiatement le `#@ ...` en cours de frappe
(sans attendre `@#` puis Entrée) et l'insère dans la ligne.

## Modèle LLM

Le modèle utilisé est `qwen2.5-coder:1.5b-base`, chargé **directement** via
[`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python) (liaison
Python de llama.cpp) — pas de serveur Ollama à l'exécution. Le fichier
`.gguf` déjà téléchargé par Ollama pour ce modèle est réutilisé tel quel
(voir `src/miniai/llm.py::discover_gguf_path`), sans le retélécharger.

Pour pointer vers un autre fichier `.gguf` :

```bash
export MINIAI_MODEL_PATH=/chemin/vers/modele.gguf
```

## Structure du dépôt

```text
bin/miniai        point d'entrée bash (utilise .venv si présent)
src/miniai/
  cli.py           REPL / mode -c, raccourci clavier Ctrl-G
  tags.py          détection/remplacement des balises #@ ... @#
  llm.py           chargement du modèle GGUF et génération du fragment bash
  shell.py         session bash persistante (sentinel-based)
tests/             tests (ne chargent pas le modèle, sauf mention contraire)
docs/              documentation
```

## Développement

Prérequis : Python 3.9+, bash, un modèle GGUF `qwen2.5-coder:1.5b-base`
accessible (déjà présent via Ollama, ou `MINIAI_MODEL_PATH`).

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest
```

## Licence

Apache License 2.0 — voir [LICENSE](LICENSE).
