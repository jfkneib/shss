# examples/cases/ — profils de cas curatés

Chaque sous-dossier ici est un **profil** de cas curatés pour shss
(voir `docs/shss-cases.md` à la racine du dépôt pour le mécanisme
général) : un domaine de spécialité — supervision système, aide sur
un outil interne, autre chose — activable indépendamment via
`SHSS_CASES_PROFILE`. `pc-stats/` est le premier, sert de référence
complète (12 cas, tout le mécanisme mis en pratique, y compris ses
pièges).

shss lui-même reste un outil de console minimal ; les profils
spécialisés vivent ici, à part, chacun optionnel et opt-in — rien
n'installe ni n'active un profil tout seul, ni via `git pull`, ni via
le paquet `.deb` (voir plus bas).

## Structure attendue pour un nouveau profil

```
examples/cases/<nom>/
  README.md          -- ce que fait le profil, comment l'installer, limites connues
  cases.seed.json     -- instantané de la base curatée (texte pur, versionné)
  <os>/                -- linux/, windows/, macos/... -- scripts par OS
    bin/               -- un script exécutable par outil
    lib/                -- logique partagée entre outils (optionnel)
```

Jamais de `cases.embeddings.json` ici — toujours dérivé, jamais
partagé (propre au modèle d'embeddings de la machine qui l'a généré,
voir `docs/shss-cases.md`) ; un `.gitignore` à la racine du dépôt
l'exclut par sécurité si jamais un tout un `~/.shss/profiles/<nom>/`
était copié par erreur au lieu du seul `cases.json`.

## Pourquoi cette structure

- **`cases.seed.json` séparé du cache d'embeddings** : le premier est
  du texte lisible et relisable (demandes + scripts), le second un
  cache de vecteurs à régénérer sur chaque machine — voir
  `docs/shss-cases.md`.
- **Répertoire par OS** (`linux/`, et un jour `windows/`, `macos/`...)
  : les scripts dépendent presque toujours de l'OS (`systemd`/`apt`
  sous Linux, WMI/PowerShell sous Windows...) — jamais les mélanger,
  même si un seul OS est couvert pour l'instant.
- **Scripts appelés via `SHSS_PROFILE_DIR`, jamais copiés dans les
  cas** : shss fournit cette variable d'environnement à tout cas qui
  matche, pointant vers `~/.shss/profiles/<nom>/` sur la machine
  courante — jamais un chemin figé vers ce dépôt. Un cas type :
  `exec "$SHSS_PROFILE_DIR/scripts/<os>/bin/<script>"`. Deux cas de
  `pc-stats` avaient d'abord été écrits avec un chemin codé en dur
  (dont un vers `/home/jfk/...`, spécifique à une seule machine) —
  fonctionnait par hasard, cassait dès qu'exécuté ailleurs.

## Checklist avant de considérer un cas terminé

Chaque point ici a réellement fait échouer quelque chose en
construisant `pc-stats` — pas une liste théorique :

1. Explorer les vraies données du système avant d'écrire le script —
   ne jamais deviner un chemin ou un format.
2. Coder défensivement : sonder ce qui existe réellement au runtime
   plutôt que coder un chemin en dur (ex : `pc-battery-info` sonde
   `/sys/class/power_supply/*`, ne suppose jamais `BAT0`).
3. Vérifier l'alignement des colonnes précisément (un script Python
   qui mesure les positions, jamais à l'œil) — `printf "%-Ns"` compte
   des octets, pas des caractères, et casse tout texte accentué.
4. Ajouter le cas (`shss-cases --profile <nom> add ...`), `reindex`.
5. Croiser la similarité du nouveau cas contre **tous** les cas
   existants du profil, dans les deux sens (`shss-cases test`) — a
   débusqué plusieurs faux positifs réels dans `pc-stats`, jamais
   trouvés en testant le nouveau cas seul.
6. Tester de bout en bout : `generate_bash()` puis **exécution
   réelle** de la ligne résolue, **depuis un répertoire hors du
   dépôt** (`/tmp` par exemple) — seul moyen fiable de détecter un
   chemin qui ne marchait que par hasard depuis la racine du dépôt
   (vérifié deux fois différentes dans `pc-stats`).
7. Régénérer le seed :
   `cp ~/.shss/profiles/<nom>/cases.json examples/cases/<nom>/cases.seed.json`.
8. Documenter honnêtement ce qui est vérifié vs supposé — un script
   écrit sans le matériel ou le logiciel correspondant sous la main
   (ex : `pc-battery-info`, jamais testé sur un vrai portable) doit
   le dire clairement, pas se présenter comme fiable à 100 %.
9. Lancer la suite de tests (`pytest`) avant de committer.

## Distribution

- **Via git** : `git pull` donne les fichiers, mais n'active rien —
  toujours une étape manuelle (voir le README du profil, section
  « Récupérer la base opérationnelle »).
- **Via le paquet `.deb`** : `packaging/build.sh` copie tout
  `examples/cases/` automatiquement — aucune modification du script
  de packaging n'est nécessaire pour un nouveau profil. Seule
  l'installation côté utilisateur reste manuelle, même depuis le
  paquet.

## Profils existants

- **`pc-stats/`** — supervision système (énergie, disques, réseau,
  services, paquets, Docker, virtualisation, batterie, bilan de
  santé). Référence complète du mécanisme — à relire avant d'en
  écrire un nouveau.
