# shss — intégration directe dans une console bash normale.
#
# Ajoute ceci à ton ~/.bashrc :
#
#   source /home/jfk/git/dev/shss/shell-integration/shss.bash
#
# Ensuite, dans n'importe quelle ligne de commande :
#
#   ls #@ trie par taille @#
#
# Tape Ctrl-G (avec ou sans le "@#" fermant) pour résoudre la demande en
# place, directement dans ton prompt bash habituel — pas besoin de lancer
# ./bin/shss.
#
# Ctrl-Y ouvre un sélecteur de modèle interactif (via fzf, s'il est
# installé — `sudo apt install fzf`) : le modèle choisi devient actif
# pour le reste de cette session de terminal (export SHSS_MODEL_NAME/
# SHSS_MODEL_TAG dans le shell courant, donc ça persiste vraiment,
# contrairement à #@ model <tag> @# qui ne change qu'une résolution
# ponctuelle). Ctrl-Y écrase la liaison readline par défaut "yank"
# (coller le dernier texte tué) — change la touche ci-dessous si tu
# t'en sers.

_SHSS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_SHSS_RESOLVE_INLINE="$_SHSS_ROOT/bin/shss-resolve-inline"

shss_resolve_tag() {
    local out new_line new_point display

    out=$("$_SHSS_RESOLVE_INLINE" "$READLINE_LINE" "$READLINE_POINT") || return
    new_line=$(sed -n '1p' <<<"$out")
    new_point=$(sed -n '2p' <<<"$out")
    display=$(tail -n +3 <<<"$out")

    # Pas de confirmation interactive ici (contrairement au REPL) : lire
    # une réponse au clavier depuis une fonction bind -x s'est révélé peu
    # fiable (les touches n'atteignent jamais `read`, même via /dev/tty,
    # sur certains terminaux — piège connu de bash, pas un bug shss).
    # On affiche ce qui a été généré (utile surtout en mode script, où la
    # ligne ne montre qu'un chemin de fichier) puis on applique
    # directement — la ligne reste éditable avant Entrée, comme avant.
    if [ -n "$display" ]; then
        echo
        echo "shss a généré :"
        echo "$display"
        echo
    fi

    READLINE_LINE="$new_line"
    READLINE_POINT="$new_point"
}

bind -x '"\C-g": shss_resolve_tag'

shss_pick_model() {
    if ! command -v fzf >/dev/null 2>&1; then
        echo
        echo "shss: fzf n'est pas installe (sudo apt install fzf) -- pas de selecteur interactif."
        echo "shss: utilise #@ models @# / #@ model <tag> @# en attendant."
        return
    fi

    local models choice name tag
    models=$("$_SHSS_ROOT/bin/shss" --list-models)

    if [ -z "$models" ]; then
        echo
        echo "shss: aucun modele selectionnable (pas d'Ollama, aucun modele curate telecharge)."
        echo "shss: telecharge-en un avec  #@ model download <tag> @#  (ex: 0.5b, 3b, 7b)."
        return
    fi

    choice=$(printf '%s\n' "$models" | fzf --prompt="shss modele > " --height=40% --reverse)

    if [ -z "$choice" ]; then
        return  # Echap : rien ne change
    fi

    name=${choice%%:*}
    tag=${choice#*:}
    export SHSS_MODEL_NAME="$name"
    export SHSS_MODEL_TAG="$tag"
    echo
    echo "shss: modele actif -> $choice (pour le reste de cette session de terminal)"
}

bind -x '"\C-y": shss_pick_model'
