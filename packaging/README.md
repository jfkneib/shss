# Paquet Debian miniai

## Construire

```bash
./packaging/build.sh
```

Produit `miniai_<version>_all.deb` à la racine du dépôt (la version vient
de `src/miniai/__init__.py`). Le script assemble un dossier temporaire
(`DEBIAN/`, `opt/miniai/`, `usr/bin/`, `usr/share/man/man1/`,
`usr/share/doc/miniai/`), normalise les permissions, puis appelle
`dpkg-deb --build`.

## Installer / désinstaller

```bash
sudo apt install ./miniai_0.1.0_all.deb   # ou : sudo dpkg -i ...
sudo apt remove miniai                     # garde le modèle et le venv
sudo apt purge miniai                      # supprime aussi le modèle
```

## Ce que fait le paquet

- **Fichiers installés** (suivis par dpkg, retirés automatiquement à la
  désinstallation) : le code source dans `/opt/miniai/`, les commandes
  `/usr/bin/miniai` et `/usr/bin/miniai-resolve-inline`, les pages de
  manuel (`man miniai`, `man miniai-resolve-inline`), `copyright` et
  `changelog` dans `/usr/share/doc/miniai/`.
- **`postinst`** (à l'installation) :
  1. crée un venv Python dans `/opt/miniai/.venv` et y installe
     `requirements.txt` (nécessite une connexion réseau) ;
  2. cherche un modèle `qwen2.5-coder:1.5b-base` déjà présent (ex: via
     Ollama) — si trouvé, `/opt/miniai/model/model.gguf` devient un lien
     symbolique vers ce fichier ; sinon, télécharge le `.gguf`
     (quantization Q4_K_M, ~950 Mo) depuis
     `QuantFactory/Qwen2.5-Coder-1.5B-GGUF` sur Hugging Face ;
  3. ajoute `source /opt/miniai/shell-integration/miniai.bash` au
     `~/.bashrc` de l'utilisateur détecté via `$SUDO_USER` (idempotent —
     ne l'ajoute pas deux fois). Si aucun utilisateur non-root n'est
     détecté (install en root direct, sans sudo), affiche la ligne à
     ajouter manuellement au lieu de deviner quel fichier modifier.
- **`postrm`** :
  - `remove` : supprime le venv (`/opt/miniai/.venv`), garde le modèle
    téléchargé (pour ne pas le retélécharger en cas de réinstallation) ;
  - `purge` : supprime aussi le modèle. Ne retire **pas** automatiquement
    la ligne ajoutée au `~/.bashrc` (édition de dotfile risquée à faire
    à l'aveugle) — un message l'indique à l'utilisateur.

Une fois installé, `miniai` fonctionne directement sans variable
d'environnement à définir : `discover_gguf_path()` (`src/miniai/llm.py`)
reconnaît `/opt/miniai/model/model.gguf` comme filet de sécurité après
avoir cherché du côté d'Ollama et de `MINIAI_MODEL_PATH`.

## Notes de test / lintian

`lintian miniai_0.1.0_all.deb` remonte deux catégories de messages sans
rapport avec un vrai défaut du paquet :

- `dir-or-file-in-opt` — lintian signale par principe tout usage de
  `/opt`, alors que c'est justement l'emplacement FHS prévu pour une
  application tierce autonome hors gestion par le système de paquets.
  Choix assumé, pas une erreur.
- `groff-message ... Segmentation fault` sur les pages de manuel — bug
  d'environnement de cette machine (le pipeline groff interne de
  lintian plante même sur une page de manuel triviale de 4 lignes créée
  pour vérifier ça), pas un défaut du fichier `.1` : `man -l
  packaging/miniai.1` et un rendu `groff` direct fonctionnent sans
  erreur ni avertissement.

Le reste (permissions, dépendance `bash` inutile car essentielle,
`copyright`/`changelog` manquants) a été corrigé.
