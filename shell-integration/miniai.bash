# miniai — intégration directe dans une console bash normale.
#
# Ajoute ceci à ton ~/.bashrc :
#
#   source /home/jfk/git/dev/miniai/shell-integration/miniai.bash
#
# Ensuite, dans n'importe quelle ligne de commande :
#
#   ls #@ trie par taille @#
#
# Tape Ctrl-G (avec ou sans le "@#" fermant) pour résoudre la demande en
# place, directement dans ton prompt bash habituel — pas besoin de lancer
# ./bin/miniai.

_MINIAI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
_MINIAI_RESOLVE_INLINE="$_MINIAI_ROOT/bin/miniai-resolve-inline"

miniai_resolve_tag() {
    local out new_line new_point display

    out=$("$_MINIAI_RESOLVE_INLINE" "$READLINE_LINE" "$READLINE_POINT") || return
    new_line=$(sed -n '1p' <<<"$out")
    new_point=$(sed -n '2p' <<<"$out")
    display=$(tail -n +3 <<<"$out")

    # Pas de confirmation interactive ici (contrairement au REPL) : lire
    # une réponse au clavier depuis une fonction bind -x s'est révélé peu
    # fiable (les touches n'atteignent jamais `read`, même via /dev/tty,
    # sur certains terminaux — piège connu de bash, pas un bug miniai).
    # On affiche ce qui a été généré (utile surtout en mode script, où la
    # ligne ne montre qu'un chemin de fichier) puis on applique
    # directement — la ligne reste éditable avant Entrée, comme avant.
    if [ -n "$display" ]; then
        echo
        echo "miniai a généré :"
        echo "$display"
        echo
    fi

    READLINE_LINE="$new_line"
    READLINE_POINT="$new_point"
}

bind -x '"\C-g": miniai_resolve_tag'
