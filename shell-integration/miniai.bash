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
    local out new_line new_point display reply

    out=$("$_MINIAI_RESOLVE_INLINE" "$READLINE_LINE" "$READLINE_POINT") || return
    new_line=$(sed -n '1p' <<<"$out")
    new_point=$(sed -n '2p' <<<"$out")
    display=$(tail -n +3 <<<"$out")

    if [ -z "$display" ]; then
        # Rien à confirmer : aucune balise n'a été résolue (ligne inchangée)
        # ou resolve_pending_tag n'a rien trouvé.
        READLINE_LINE="$new_line"
        READLINE_POINT="$new_point"
        return
    fi

    echo
    echo "miniai propose :"
    echo "$display"
    echo
    read -r -p "Utiliser ce résultat ? [O/n] " reply
    case "$reply" in
        ""|[oO]|[oO][uU][iI]|[yY]|[yY][eE][sS])
            READLINE_LINE="$new_line"
            READLINE_POINT="$new_point"
            ;;
    esac
}

bind -x '"\C-g": miniai_resolve_tag'
