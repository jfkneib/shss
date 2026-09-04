# lib/pc-stats-common.sh -- fonctions partagees entre les outils pc-*.
# A sourcer, jamais executer directement (pas de shebang volontairement).

# stats_uptime START_EPOCH END_EPOCH
#
# Remplit STATS_ON_SECONDS / STATS_BOOT_COUNT / STATS_OFF_SECONDS /
# STATS_TOTAL_SECONDS pour l'intervalle [START_EPOCH, END_EPOCH),
# a partir de `journalctl --list-boots` -- rien a collecter en plus,
# ces informations existent deja dans le journal systemd, meme
# retroactivement pour les mois passes.
#
# LIMITE CONNUE : la duree "allume" d'un demarrage est mesuree comme
# l'intervalle entre sa premiere et sa derniere entree de journal --
# une mise en veille prolongee sans la moindre activite journalisee
# dedans compterait a tort comme du temps allume. Reste une bonne
# approximation en usage normal (veille/reveil generent des entrees).
stats_uptime()
{
    local range_start="$1"
    local range_end="$2"

    STATS_ON_SECONDS=0
    STATS_BOOT_COUNT=0

    local line first_us last_us first last clip_start clip_end
    while IFS= read -r line; do
        first_us=$(jq -r '.first_entry' <<<"$line")
        last_us=$(jq -r '.last_entry' <<<"$line")
        first=$(( first_us / 1000000 ))
        last=$(( last_us / 1000000 ))

        clip_start=$(( first > range_start ? first : range_start ))
        clip_end=$(( last < range_end ? last : range_end ))

        if (( clip_end > clip_start )); then
            STATS_ON_SECONDS=$(( STATS_ON_SECONDS + (clip_end - clip_start) ))
            STATS_BOOT_COUNT=$((STATS_BOOT_COUNT + 1))
        fi
    done < <(journalctl --list-boots -o json 2>/dev/null | jq -c '.[]')

    STATS_TOTAL_SECONDS=$(( range_end - range_start ))
    STATS_OFF_SECONDS=$(( STATS_TOTAL_SECONDS - STATS_ON_SECONDS ))
    (( STATS_OFF_SECONDS < 0 )) && STATS_OFF_SECONDS=0
}

# stats_fmt_hm SECONDES -> "H h MM min"
stats_fmt_hm()
{
    local total_s="$1"
    printf "%d h %02d min" "$(( total_s / 3600 ))" "$(( (total_s % 3600) / 60 ))"
}

# stats_require CMD HINT -- sort avec un message clair si CMD est absent,
# plutot que de planter plus loin sur une erreur "commande introuvable"
# qui ne dit pas quoi installer.
stats_require()
{
    local cmd="$1"
    local hint="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "$(basename "$0"): $cmd est requis ($hint)" >&2
        exit 1
    fi
}

# stats_parse_month [AAAA-MM|MM] -> ecrit STATS_YEAR / STATS_MONTH (deux
# chiffres) / STATS_MONTH_ARG (AAAA-MM). Normalise "8" ou "08" en annee
# courante -- 10#$arg force la base 10 : sans ca, bash lit un zero en
# tete comme de l'octal, et "08"/"09" ne sont pas de l'octal valide
# (constate en pratique).
stats_parse_month()
{
    local arg="${1:-$(date +%Y-%m)}"

    if [[ "$arg" =~ ^[0-9]{1,2}$ ]]; then
        arg="$(date +%Y)-$(printf "%02d" "$((10#$arg))")"
    fi

    if [[ ! "$arg" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
        echo "$(basename "$0"): argument invalide : $1 (attendu AAAA-MM ou MM)" >&2
        exit 1
    fi

    STATS_MONTH_ARG="$arg"
    STATS_YEAR="${arg%-*}"
    STATS_MONTH="${arg#*-}"
}

STATS_MOIS_FR=(Janvier Février Mars Avril Mai Juin Juillet Août Septembre Octobre Novembre Décembre)

# stats_month_name MM (deux chiffres) -> "Août"
stats_month_name()
{
    echo "${STATS_MOIS_FR[$((10#$1 - 1))]}"
}
