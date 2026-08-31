# Paquet Debian shss

## Construire

```bash
./packaging/build.sh
```

Produit `shss_<version>_all.deb` à la racine du dépôt (la version vient
de `src/shss/__init__.py`). Le script assemble un dossier temporaire
(`DEBIAN/`, `opt/shss/`, `usr/bin/`, `usr/share/man/man1/`,
`usr/share/doc/shss/`), normalise les permissions, puis appelle
`dpkg-deb --build`.

## Installer / désinstaller

```bash
sudo apt install ./shss_0.2.0_all.deb   # ou : sudo dpkg -i ...
sudo apt remove shss                     # garde le modèle et le venv
sudo apt purge shss                      # supprime aussi le modèle
```

## Ce que fait le paquet

- **Fichiers installés** (suivis par dpkg, retirés automatiquement à la
  désinstallation) : le code source dans `/opt/shss/`, les commandes
  `/usr/bin/shss` et `/usr/bin/shss-resolve-inline`, les pages de
  manuel (`man shss`, `man shss-resolve-inline`), `copyright` et
  `changelog` dans `/usr/share/doc/shss/`.
- **`postinst`** (à l'installation) :
  1. crée un venv Python dans `/opt/shss/.venv` et y installe
     `requirements.txt` (nécessite une connexion réseau) ;
  2. cherche un modèle `qwen2.5-coder:1.5b-base` déjà présent (ex: via
     Ollama) — si trouvé, `/opt/shss/model/model.gguf` devient un lien
     symbolique vers ce fichier ; sinon, télécharge le `.gguf`
     (quantization Q4_K_M, ~950 Mo) depuis
     `QuantFactory/Qwen2.5-Coder-1.5B-GGUF` sur Hugging Face ;
  3. ajoute `source /opt/shss/shell-integration/shss.bash` au
     `~/.bashrc` de l'utilisateur détecté via `$SUDO_USER` (idempotent —
     ne l'ajoute pas deux fois). Si aucun utilisateur non-root n'est
     détecté (install en root direct, sans sudo), affiche la ligne à
     ajouter manuellement au lieu de deviner quel fichier modifier.
- **`postrm`** :
  - `remove` : supprime le venv (`/opt/shss/.venv`), garde le modèle
    téléchargé (pour ne pas le retélécharger en cas de réinstallation) ;
  - `purge` : supprime aussi le modèle. Ne retire **pas** automatiquement
    la ligne ajoutée au `~/.bashrc` (édition de dotfile risquée à faire
    à l'aveugle) — un message l'indique à l'utilisateur.

Une fois installé, `shss` fonctionne directement sans variable
d'environnement à définir : `discover_gguf_path()` (`src/shss/llm.py`)
reconnaît `/opt/shss/model/model.gguf` comme filet de sécurité après
avoir cherché du côté d'Ollama et de `SHSS_MODEL_PATH`.

## Notes de test / lintian

`lintian shss_0.2.0_all.deb` remonte deux catégories de messages sans
rapport avec un vrai défaut du paquet :

- `dir-or-file-in-opt` — lintian signale par principe tout usage de
  `/opt`, alors que c'est justement l'emplacement FHS prévu pour une
  application tierce autonome hors gestion par le système de paquets.
  Choix assumé, pas une erreur.
- `groff-message ... Segmentation fault` sur les pages de manuel — bug
  d'environnement de cette machine (le pipeline groff interne de
  lintian plante même sur une page de manuel triviale de 4 lignes créée
  pour vérifier ça), pas un défaut du fichier `.1` : `man -l
  packaging/shss.1` et un rendu `groff` direct fonctionnent sans
  erreur ni avertissement.

Le reste (permissions, dépendance `bash` inutile car essentielle,
`copyright`/`changelog` manquants) a été corrigé.
