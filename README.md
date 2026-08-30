# miniai

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
sudo apt install ./miniai_0.1.0_all.deb
```

Le paquet installe dans `/opt/miniai/` (venv Python, modèle, code), les
commandes `miniai` / `miniai-resolve-inline` dans `/usr/bin/`, et une
page de manuel (`man miniai`). Il réutilise le modèle déjà présent via
Ollama s'il le trouve, sinon le télécharge depuis Hugging Face
(~950 Mo). Il ajoute aussi `source .../shell-integration/miniai.bash` au
`~/.bashrc` de l'utilisateur qui a lancé `sudo` (variable `$SUDO_USER`) —
si ce n'est pas détecté, l'ajout manuel de cette ligne est affiché à
l'écran en fin d'installation.

Détails complets (contenu du paquet, scripts `postinst`/`postrm`,
suppression) dans [packaging/](packaging/).

## Utilisation (depuis un checkout git, sans paquet)

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
sans attendre Entrée. Avant d'appliquer le résultat, `Ctrl-G` affiche ce
qui serait inséré (le fragment, ou le contenu complet du script en mode
script) et demande confirmation :

```text
miniai propose :
-S

Utiliser ce résultat ? [O/n]
```

Répondre non (`n`) laisse la ligne inchangée, comme si `Ctrl-G` n'avait
pas été pressé — dans le REPL, rien n'est écrit ni journalisé tant que
tu n'as pas confirmé. Cette confirmation n'existe que pour `Ctrl-G` — la
résolution automatique d'une balise déjà fermée à l'Entrée (REPL ou `-c`)
reste directe, sans prompt, pour ne pas casser des usages non
interactifs.

### Intégration dans ta console bash normale (sans ./bin/miniai)

`Ctrl-G` peut aussi être branché directement dans ta session bash
habituelle (pas besoin de lancer `./bin/miniai`) :

```bash
echo 'source /home/jfk/git/dev/miniai/shell-integration/miniai.bash' >> ~/.bashrc
```

La confirmation `Ctrl-G` fonctionne aussi ici, mais différemment du REPL :
comme lire une réponse interactive depuis le sous-processus Python
appelé par `bind -x` n'est pas fiable dans ce contexte (le terminal reste
dans le mode raw de readline — voir `shell-integration/miniai.bash`), la
génération se termine et s'enregistre (script écrit, historique
journalisé) **avant** que la confirmation soit demandée ; c'est la
confirmation elle-même, faite par le `read` intégré de bash, qui décide
seulement si le résultat est **inséré dans ta ligne**. Répondre non ne
supprime donc pas le script déjà écrit dans `/tmp/miniai-<uid>/`, il
empêche juste son chemin d'atterrir dans ton prompt.

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

**Ollama n'est pas requis.** Le code ne lance jamais le binaire `ollama`
ni ne contacte de serveur — il lit juste un fichier `.gguf` sur disque.
Ollama sert uniquement de raccourci pratique pour obtenir ce fichier sans
le télécharger soi-même (via `discover_gguf_path`, qui lit le manifest
qu'Ollama a laissé sur disque). Sans Ollama installé, `MINIAI_MODEL_PATH`
vers n'importe quel `.gguf` (téléchargé par exemple depuis Hugging Face)
suffit à faire fonctionner miniai de la même façon.

## Scripts et historique

Pour une demande trop complexe pour tenir sur une ligne (plusieurs
étapes, transformation de fichier...), le modèle peut répondre par un
script complet au lieu d'un fragment bash — il choisit lui-même le
langage (Python, bash, ...) via la ligne shebang en tête de sa réponse
(`#!/usr/bin/env python3`, `#!/usr/bin/env bash`, ...). Le script est
écrit dans un fichier temporaire nommé par date + identifiant unique
(`/tmp/miniai-<uid>/20260830-161859_d80a29.py`), rendu exécutable, et
c'est ce chemin qui remplace la balise dans la ligne :

```bash
#@ formate le fichier /tmp/dede.txt en json et écris le résultat dans /tmp/result.json @#
# → /tmp/miniai-1000/20260830-161859_d80a29.py
```

Testé en réel : fonctionne, mais avec les mêmes limites de fiabilité
qu'ailleurs sur ce modèle 1.5B (ex: peut légèrement s'écarter du nom de
fichier demandé, ou ne pas gérer une structure de données complexe).

Pour aider le modèle à écrire un script adapté au **contenu réel** d'un
fichier plutôt que de deviner, un aperçu (quelques premières lignes) de
tout fichier explicitement nommé dans la demande est glissé dans le
prompt caché (`src/miniai/context.py::build_context`) — invisible pour
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
historique — `~/.miniai/history.jsonl`, une ligne JSON par entrée
(horodatage, demande, résultat, type) :

```bash
miniai --history        # les 20 dernières résolutions
miniai --history 50     # les 50 dernières
```

`--history` n'a pas besoin de charger le modèle, donc c'est instantané.

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
  cli.py                   REPL / mode -c / --history, raccourci clavier Ctrl-G
  inline.py                résolution ponctuelle (utilisé par bin/miniai-resolve-inline)
  tags.py                  détection/remplacement des balises #@ ... @#
  llm.py                   modèle GGUF, prompt, dispatch fragment/script
  history.py               journal JSONL des résolutions (~/.miniai/history.jsonl)
  context.py               aperçu des fichiers mentionnés, injecté dans le prompt caché
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
