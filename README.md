# shss

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
sudo apt install ./shss_0.1.0_all.deb
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
depuis Hugging Face (URLs vérifiées à la main, quantization Q4_K_M) —
c'est la seule famille testée/fiable avec le prompt de ce projet (voir
"Limites connues"). C'est ce qui répond au cas "pas d'Ollama installé" :

```bash
#@ model download 3b @#   # télécharge ~1,9 Go
#@ model 3b @#             # puis l'active (trouve le fichier déjà téléchargé)
```

Actuellement dans la liste : `1.5b-base` (~941 Mo, le défaut), `3b`
(~1,9 Go), `7b` (~4,5 Go). Le téléchargement est bloquant et peut prendre
du temps selon la connexion ; il ne se déclenche **que** sur cette
commande explicite, jamais automatiquement.

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
filtrable/navigable au clavier des modèles disponibles. Le choix devient
actif pour le reste de la session de terminal (`export
SHSS_MODEL_NAME`/`SHSS_MODEL_TAG` dans le shell courant).

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
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python -m pytest
```

## Licence

Apache License 2.0 — voir [LICENSE](LICENSE).
