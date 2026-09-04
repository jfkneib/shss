# Base de cas curatés (`shss-cases`)

> Cette page documente une fonctionnalité de la branche `miniRAG`,
> pas encore fusionnée. `SHSS_CASES_PATH`, `SHSS_CASES_THRESHOLD` et
> les autres variables citées ici n'existent que sur cette branche.

## 1. Le problème que ça résout

Le petit LLM de shss (`qwen2.5-coder`, 0.5b à 7b) invente une réponse
plausible même quand il ne peut pas savoir la bonne — par exemple
`#@ energie consommee par le pc @#` donnait `psutil.cpu_percent()`,
qui mesure un taux d'usage CPU, pas une consommation électrique.

La base de cas curatés permet d'écrire, une fois et à la main, le bon
script pour ce genre de demande, puis de le faire retrouver
automatiquement par similarité de sens — sans jamais reproposer la
mauvaise réponse du LLM pour cette demande précise.

## 2. Démarrage rapide

```bash
cd /home/jfk/git/dev/shss
./bin/shss-cases
```

Lancé **sans aucun argument**, `shss-cases` :

- ouvre une fenêtre (Tk) si `tkinter` est installé et qu'un affichage
  est disponible — c'est le chemin le plus simple, tout se fait à la
  souris (voir section 4) ;
- sinon, affiche directement l'aide de la ligne de commande (section 3)
  — rien à configurer, ça marche dans les deux cas, y compris en SSH
  sans X.

Pour forcer explicitement l'un ou l'autre :

```bash
./bin/shss-cases gui    # erreur claire si impossible, plutôt qu'un repli silencieux
./bin/shss-cases list   # (ou n'importe quelle autre sous-commande : toujours en CLI)
```

## 3. Ligne de commande

`./bin/shss-cases --help` affiche un exemple complet ; en résumé :

| Commande | Effet |
|---|---|
| `add <id> --request "..." [--request "..."] [--note "..."]` | ajoute un cas (script sur stdin, ou `--script-file`) |
| `edit <id> [--request "..."] [--note "..."] [--script-file f]` | modifie **seulement** les champs fournis, le reste ne bouge pas |
| `remove <id>` | retire un cas |
| `list` | liste les cas existants |
| `test "une demande"` | montre les cas les plus proches + score, **n'exécute rien** |
| `reindex [--force]` | recalcule le cache d'embeddings (à faire après tout `add`/`edit`/`remove`) |
| `download-model` | télécharge le modèle d'embeddings curaté (~81 Mo, sans Ollama) |

Exemple complet :

```bash
./bin/shss-cases add energie \
    --request "energie consommee par le pc" \
    --request "combien consomme mon ordinateur" \
    --note "le LLM invente n'importe quoi ici"
# colle le script sur stdin, Ctrl-D pour terminer

./bin/shss-cases reindex
./bin/shss-cases test "quelle est la consommation electrique de ma machine"
```

`edit` ne redemande jamais tout le cas : pour changer juste la note,
par exemple, sans retoucher le script ni les formulations :

```bash
./bin/shss-cases edit energie --note "RAPL = CPU seulement, pas le total"
```

## 4. Interface graphique

Deux panneaux : la liste des cas à gauche, le détail du cas
sélectionné à droite (formulations, note, script). En bas, les mêmes
actions que la ligne de commande, en boutons :

- **Ajouter…** / **Modifier…** — un formulaire (identifiant,
  formulations une par ligne, note, script — avec un bouton pour
  charger le script depuis un fichier existant).
- **Supprimer** — sur le cas sélectionné, avec confirmation.
- **Tester une demande…** — une zone de texte + résultats classés par
  score, sans rien exécuter, comme `shss-cases test`.
- **Réindexer** / **Modèle d'embeddings…** — tournent en arrière-plan
  (barre de progression) : la fenêtre reste utilisable pendant le
  calcul ou le téléchargement.

Aucune logique propre à la fenêtre : chaque bouton appelle exactement
les mêmes fonctions que la ligne de commande (`src/shss/cases.py`), la
fenêtre n'est qu'une autre façade.

## 5. Comment c'est utilisé au moment de la résolution

Branché dans `llm.generate_bash()`, juste après les commandes internes
(`#@ model @#`, etc.) et avant tout appel au modèle de génération. Une
demande dont le meilleur score dépasse `SHSS_CASES_THRESHOLD` (0.70 par
défaut) réutilise le script curaté tel quel, sans jamais charger le
modèle de génération — visible dans `#@ history @#` avec le type
`case`, distinct de `script`/`inline` (générés) et `builtin`.

Si la base est vide (le cas par défaut, rien de curaté au départ), rien
n'est chargé : aucun coût ajouté pour une demande ordinaire.

## 6. Limites connues

- Le modèle d'embeddings (`nomic-embed-text`, distinct du modèle de
  génération) est nécessaire : le modèle de génération seul ne sépare
  pas fiablement "proche" de "pas proche" en similarité cosinus (testé
  en pratique).
- Le seuil par défaut (0.70) est calibré sur un tout petit échantillon
  — à affiner avec plus de cas réels avant d'y faire vraiment
  confiance.
- Pas de palier intermédiaire "le LLM adapte un script proche mais pas
  identique" dans cette première version — volontaire, pour rester
  simple à tester. Uniquement : réutilisation telle quelle au-dessus du
  seuil, génération normale en dessous.
- La base (`~/.shss/cases.json`) est personnelle, pas partagée par
  défaut avec les autres utilisateurs de la machine ni livrée avec
  shss.
