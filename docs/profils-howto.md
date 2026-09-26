# shss — ajouter ses scripts et parler le méta-langage

Guide pour écrire un profil shss (tes scripts + les phrases qui les déclenchent) et utiliser le méta-langage `#@ … @#`.

## shss en deux minutes

shss est une console bash augmentée : tu écris ta demande en français entre `#@` et `@#`, et shss la remplace par la bonne commande bash avant l'exécution. Le reste de la ligne reste du bash normal.

```bash
ls #@ affiche aussi les fichiers cachés @#     # devient : ls -la
```

La réponse vient de deux sources, dans cet ordre :

1. **Les cas curatés** d'un profil : des demandes déjà écrites, reliées à un script qui marche. Si ta demande ressemble assez à l'une d'elles (similarité ≥ 70 %), c'est ce script qui sort. C'est rapide, fiable et testé.
2. **Le petit LLM local** (qwen2.5-coder 1.5b par défaut, via llama.cpp) quand aucun cas ne colle.

Ton travail consiste donc à écrire des **profils** : tes scripts, plus les phrases qui doivent les déclencher.

### Installer depuis le dépôt

```bash
git clone git@github.com:jfkneib/shss.git ~/git/shss
```

```bash
echo 'source ~/git/shss/shell-integration/shss.bash' >> ~/.bashrc
```

Ouvre un nouveau terminal. Le modèle se télécharge au premier usage (~941 Mo). Il existe aussi un paquet `.deb` qui installe tout dans `/opt/shss/` (voir le README du dépôt).

## Le méta-langage shss

Tout tient dans une balise `#@ … @#` placée n'importe où dans une ligne bash. Ce qu'il y a juste après `#@` décide où shss cherche.

| Syntaxe | Effet |
| --- | --- |
| `#@ demande @#` | Cherche dans le profil actif (`SHSS_CASES_PROFILE`, sinon la base par défaut), puis le LLM |
| `#@tmux@ demande @#` | Force le profil `tmux` pour cette demande seulement (nom collé à `#@`, sans espace) |
| `#@all@ demande @#` | Cherche dans tous les profils installés, garde le meilleur score |
| `"texte"` dans la demande | Pour un cas « gabarit » : le premier texte entre guillemets est transmis au script sur stdin |
| `ls #@ … @# #@ … @#` | Plusieurs balises sur une ligne, mélangées à du bash normal |

### Commandes intégrées (instantanées, sans LLM)

| Commande | Effet |
| --- | --- |
| `#@ help @#` | Rappel des commandes |
| `#@ q <question> @#` | Liste les 20 cas les plus proches, tous profils, sans rien exécuter |
| `#@ history 10 @#` | Les 10 dernières balises tapées |
| `#@ feedback bon @#` | Note la résolution précédente comme bonne |
| `#@ feedback mauvais <commentaire> @#` | … ou mauvaise, avec un commentaire |
| `#@ models @#` | Liste les modèles, marque l'actif |
| `#@ model 3b @#` | Change de modèle (`0.5b`, `1.5b-base`, `3b`, `7b`) |
| `#@ model download 3b @#` | Télécharge un modèle |

### Trois façons de lancer

- **Ctrl-G dans ton bash habituel** : tape la ligne, **Ctrl-G** remplace la balise, tu relis, puis Entrée. C'est le seul mode avec un vrai terminal : il marche pour les commandes interactives (tmux, éditeurs). Attention, Entrée sans Ctrl-G fait de `#@ … @#` un simple commentaire bash.
- **La console shss** (`shss`) : les balises sont résolues à l'Entrée. Ctrl-G y demande une confirmation `[O/n]`.
- **Une seule commande** : `shss -c 'ls #@ affiche aussi les fichiers cachés @#'`.

### Exemples à coller

```bash
shss -c '#@ q consommation electrique du pc @#'
```

```bash
shss -c '#@all@ energie consommee par le pc pendant 10s @#'
```

```bash
shss -c '#@grep-search@ cherche "TODO" dans mes fichiers @#'
```

```bash
shss --history 10
```

## Anatomie d'un profil

Un profil, c'est un dossier dans `profiles/` du dépôt : tes scripts, plus un fichier JSON qui dit quelles phrases les déclenchent. Trois profils existent déjà : `pc-stats` (la référence, 12 cas), `grep-search` et `tmux`.

```text
profiles/<nom>/
  README.md          ce que fait le profil, installation, limites connues
  cases.seed.json    les cas : phrases -> script (texte, versionné)
  linux/
    bin/             un script exécutable par outil
    lib/             fonctions partagées entre les outils (optionnel)
```

Une fois installé, le profil vit dans `~/.shss/profiles/<nom>/` : `cases.json` plus `scripts/linux/…`.

### Un cas dans `cases.seed.json`

```json
{
  "id": "tmux-liste",
  "requests": [
    "liste mes sessions tmux",
    "quelles sessions tmux existent",
    "sessions tmux en cours"
  ],
  "script": "#!/usr/bin/env bash\n...",
  "note": "optionnel : un commentaire pour les humains",
  "input": "stdin",
  "danger": 1
}
```

| Champ | Rôle |
| --- | --- |
| `id` | Nom court et unique, préfixé par le profil (`tmux-liste`) |
| `requests` | 3 à 5 façons naturelles de demander la même chose |
| `script` | Le « lanceur » du cas : quelques lignes qui appellent ton vrai script |
| `input` | `"stdin"` pour un cas gabarit : le texte entre guillemets arrive sur stdin |
| `danger` | 0 lecture seule (défaut), 1 modifie un peu (réversible), 2 destructif |
| `note` | Libre, pour les humains |

### Le lanceur : toujours le même modèle

Le `script` d'un cas ne contient jamais la logique. Il route selon l'OS et appelle le vrai script via `$SHSS_PROFILE_DIR`, jamais un chemin en dur vers ton clone :

```bash
#!/usr/bin/env bash
os="$(uname -s)"
case "$os" in
    Linux)
        exec "$SHSS_PROFILE_DIR/scripts/linux/bin/tm-list"
        ;;
    *)
        echo "tmux-liste : pas encore pris en charge sur cet OS ($os)" >&2
        exit 1
        ;;
esac
```

### Variables que shss fournit à ton script

| Variable | Contenu |
| --- | --- |
| `SHSS_PROFILE_DIR` | `~/.shss/profiles/<nom>/` sur la machine courante |
| `SHSS_REQUEST` | La demande complète tapée |
| `SHSS_PREFIX` / `SHSS_SUFFIX` | Le bash avant / après la balise sur la ligne |
| `SHSS_MATCH_SCORE` | Le score qui a fait matcher (ex : `0.8412`) |
| `SHSS_CASE_ID` | L'`id` du cas retenu |

## Tuto : intégrer tes scripts dans un profil

Exemple complet : un profil `ports` avec deux cas, « quels ports écoutent » (cas fixe) et « qui écoute sur le port "8080" » (cas gabarit). Toutes les commandes se lancent depuis la racine du clone (`cd ~/git/shss`).

### 1. Créer le dossier et le script

```bash
mkdir -p profiles/ports/linux/bin
```

`profiles/ports/linux/bin/pt-listen` :

```bash
#!/usr/bin/env bash
#
# pt-listen [port] -- ports TCP en écoute, ou qui écoute sur un port précis.

set -u

if ! command -v ss >/dev/null; then
    echo "pt-listen : 'ss' introuvable (sudo apt install iproute2)" >&2
    exit 1
fi

port="${1:-}"
if [ -z "$port" ]; then
    ss -tlnp
elif [[ "$port" =~ ^[0-9]+$ ]]; then
    ss -tlnp "sport = :$port"
else
    echo "pt-listen : '$port' n'est pas un numéro de port" >&2
    exit 1
fi
```

```bash
chmod +x profiles/ports/linux/bin/pt-listen
```

Teste-le seul avant d'aller plus loin : `profiles/ports/linux/bin/pt-listen 8188`.

### 2. Écrire les lanceurs

`/tmp/ports-liste.sh` (cas fixe) :

```bash
#!/usr/bin/env bash
os="$(uname -s)"
case "$os" in
    Linux) exec "$SHSS_PROFILE_DIR/scripts/linux/bin/pt-listen" ;;
    *) echo "ports-liste : OS non pris en charge ($os)" >&2; exit 1 ;;
esac
```

`/tmp/ports-qui.sh` (cas gabarit, le port arrive sur stdin) :

```bash
#!/usr/bin/env bash
set -u
port=""
[ -t 0 ] || port=$(cat)
if [ -z "$port" ]; then
    echo "ports-qui : aucun port entre guillemets dans la demande" >&2
    exit 1
fi
os="$(uname -s)"
case "$os" in
    Linux) exec "$SHSS_PROFILE_DIR/scripts/linux/bin/pt-listen" "$port" ;;
    *) echo "ports-qui : OS non pris en charge ($os)" >&2; exit 1 ;;
esac
```

### 3. Installer les scripts côté utilisateur

```bash
mkdir -p ~/.shss/profiles/ports/scripts && cp -r profiles/ports/linux ~/.shss/profiles/ports/scripts/
```

### 4. Déclarer les cas

```bash
./bin/shss-cases --profile ports add ports-liste --script-file /tmp/ports-liste.sh --request "quels ports ecoutent" --request "ports ouverts sur la machine" --request "liste les ports en ecoute"
```

```bash
./bin/shss-cases --profile ports add ports-qui --stdin --script-file /tmp/ports-qui.sh --request 'qui ecoute sur le port "8080"' --request 'quel programme utilise le port "8080"'
```

```bash
./bin/shss-cases --profile ports reindex
```

Première fois : `./bin/shss-cases download-model` récupère le modèle d'embeddings (~81 Mo). Tu peux aussi tout faire à la souris avec `./bin/shss-cases gui`.

### 5. Vérifier que les bonnes phrases tombent sur le bon cas

```bash
./bin/shss-cases --profile ports test "qu'est-ce qui ecoute sur le port \"3000\""
```

Cette commande affiche les cas les plus proches avec leur score, sans rien exécuter. Vise un bon cas nettement au-dessus de 70 %, avec de l'écart sur le deuxième.

### 6. Tester en vrai, hors du dépôt

```bash
cd /tmp && ~/git/shss/bin/shss -c '#@ports@ qui ecoute sur le port "8188" @#'
```

Lancer depuis `/tmp` démasque les chemins qui ne marchaient que par hasard depuis le clone.

### 7. Figer le résultat dans le dépôt

```bash
cp ~/.shss/profiles/ports/cases.json profiles/ports/cases.seed.json
```

Ajoute un `profiles/ports/README.md` (ce que ça fait, comment l'installer, limites), puis commit. Ne versionne jamais `cases.embeddings.json` : ce fichier est propre à chaque machine.

## Rendre les commandes cool

Une bonne commande shss se déclenche avec une phrase naturelle, répond vite et proprement, et ne casse jamais sans dire pourquoi.

### Les phrases (`requests`)

- **3 à 5 formulations variées** : comme tu parles vraiment (« combien consomme mon ordi », pas seulement « consommation énergétique »).
- **Sans accents**, comme dans les profils existants : la plupart des gens tapent sans accents en console.
- **Un cas = une intention**. Si deux cas se ressemblent (« tuer une session » et « tuer tout tmux »), leurs phrases doivent insister sur ce qui les distingue.
- **Croise toujours** avec `shss-cases test` : chaque nouvelle phrase contre tous les cas du profil, dans les deux sens. C'est comme ça qu'on trouve les faux positifs.
- **Cas gabarit** : mets le texte variable entre guillemets dans les exemples (`'cherche "TODO" dans mes fichiers'`). S'il matche trop large, monte son seuil (`--threshold 0.82`).

### Les scripts

- **Préfixe court par profil** : `pc-*`, `tm-*`, `gs-*`. On voit tout de suite d'où vient un outil.
- **Un script = un outil**, dans `linux/bin/`. La logique commune va dans `linux/lib/*.sh` (sourcé, sans shebang).
- **Sonder, jamais deviner** : liste `/sys/class/power_supply/*` au lieu de supposer `BAT0`, et teste `command -v outil` avec un message qui dit quoi installer.
- **Erreurs claires sur stderr**, préfixées du nom du script, avec un code de sortie non nul. « Aucune session tmux en cours » vaut mieux qu'une erreur brute.
- **Sortie lisible** : des colonnes alignées, des unités, des totaux. Attention, `printf "%-10s"` compte des octets : un texte accentué décale les colonnes.
- **Commandes interactives** (tmux, éditeurs) : vérifie `[ -t 0 ] && [ -t 1 ]` et refuse proprement. Elles ne marchent que via Ctrl-G, pas dans `shss -c`.
- **Pas de confirmation dans le script** : shss a déjà montré la commande avant exécution. Marque plutôt le risque avec `--danger`.

### Le danger

| Niveau | Quand | Exemple |
| --- | --- | --- |
| 0 | Lecture seule (défaut) | lister les ports |
| 1 | Modifie quelque chose de limité ou réversible | tuer une session tmux précise |
| 2 | Destructif ou de portée large | `tmux kill-server` |

Pour l'instant, ce champ est seulement informatif. Renseigne-le quand même : il servira plus tard à des confirmations renforcées.

## Installer un profil, tester, proposer

### Installer un profil existant

Rien ne s'active tout seul, ni via `git pull` ni via le `.deb`. Pour chaque profil voulu (ici `tmux`) :

```bash
mkdir -p ~/.shss/profiles/tmux/scripts && cp profiles/tmux/cases.seed.json ~/.shss/profiles/tmux/cases.json && cp -r profiles/tmux/linux ~/.shss/profiles/tmux/scripts/
```

```bash
./bin/shss-cases --profile tmux reindex
```

Ensuite, utilise `#@tmux@ … @#` ou `#@all@ … @#`, ou fais `export SHSS_CASES_PROFILE=tmux` pour le rendre actif par défaut.

### Avant de proposer ton profil

- [ ] Le script marche seul, puis via shss depuis `/tmp`
- [ ] `shss-cases test` : le bon cas sort en tête pour chaque phrase, sans vol sur les autres cas
- [ ] `cases.seed.json` régénéré depuis `~/.shss/profiles/<nom>/cases.json`
- [ ] `README.md` du profil : ce qui est vérifié, ce qui est supposé (ex : jamais testé sur un portable)
- [ ] `pytest` passe
- [ ] Commit sur une branche, puis PR vers `dev` sur [github.com/jfkneib/shss](https://github.com/jfkneib/shss)

Le paquet `.deb` embarque automatiquement tout `profiles/` : rien à changer dans le packaging.

### Pour aller plus loin

Dans le dépôt : [`profiles/README.md`](../profiles/README.md) (conventions et checklist), [`docs/shss-cases.md`](shss-cases.md) (mécanisme complet) et [`profiles/pc-stats/`](../profiles/pc-stats/) (profil de référence).
