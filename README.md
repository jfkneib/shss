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

Dans le REPL, `Ctrl-G` résout immédiatement la balise la plus proche du
curseur — qu'elle soit déjà fermée par `@#` ou encore en cours de frappe —
sans attendre Entrée.

### Intégration dans ta console bash normale (sans ./bin/miniai)

`Ctrl-G` peut aussi être branché directement dans ta session bash
habituelle (pas besoin de lancer `./bin/miniai`) :

```bash
echo 'source /home/jfk/git/dev/miniai/shell-integration/miniai.bash' >> ~/.bashrc
```

Détails, limites et piège à connaître (bash traite `#@ ... @#` comme un
commentaire si on presse Entrée sans passer par `Ctrl-G` d'abord) dans
[docs/getting-started.md](docs/getting-started.md#7-intégration-dans-ta-console-bash-normale-sans-lancer-binminiai).

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

## Limites connues

`qwen2.5-coder:1.5b-base` est un petit modèle base avec un prompt few-shot
minimal (voir `src/miniai/llm.py`) — il ne comprend pas toujours toute la
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

## Structure du dépôt

```text
bin/miniai                 point d'entrée bash du REPL (utilise .venv si présent)
bin/miniai-resolve-inline  point d'entrée pour l'intégration Ctrl-G dans bash
shell-integration/
  miniai.bash              à sourcer dans ~/.bashrc pour le Ctrl-G "natif"
src/miniai/
  cli.py                   REPL / mode -c, raccourci clavier Ctrl-G
  inline.py                résolution ponctuelle (utilisé par bin/miniai-resolve-inline)
  tags.py                  détection/remplacement des balises #@ ... @#
  llm.py                   chargement du modèle GGUF et génération du fragment bash
  shell.py                 session bash persistante (sentinel-based)
tests/                     tests (ne chargent pas le modèle, sauf mention contraire)
docs/                      documentation
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
