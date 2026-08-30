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
    local out
    out=$("$_MINIAI_RESOLVE_INLINE" "$READLINE_LINE" "$READLINE_POINT") || return
    READLINE_LINE=$(head -n1 <<<"$out")
    READLINE_POINT=$(tail -n1 <<<"$out")
}

bind -x '"\C-g": miniai_resolve_tag'
