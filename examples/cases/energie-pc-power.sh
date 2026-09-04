#!/usr/bin/env bash
#
# pc-power.sh
#
# Estimation de la consommation électrique d'un PC Linux.
#
# Mesures utilisées :
#   - CPU / Package : Intel RAPL (root-only depuis noyau 5.10, sudo)
#   - RAM           : Intel RAPL DRAM si disponible, sinon estimation
#   - GPU NVIDIA    : nvidia-smi
#   - GPU AMD/Intel : hwmon/sysfs si disponible
#   - Disques       : activité + type de disque
#   - Écrans        : connecteurs DRM + estimation
#   - USB           : estimation
#
# IMPORTANT :
#   Les valeurs réellement mesurées sont indiquées "mesuré".
#   Les autres sont des estimations.
#
# La consommation totale à la prise ne peut pas être mesurée
# correctement par Linux sans wattmètre externe.
#

set -u

# LC_NUMERIC=C (pas LC_ALL, pour garder les messages dans la langue de
# l'utilisateur) : awk formate toujours ses nombres avec un point
# decimal, quelle que soit la locale -- mais le `printf` integre de
# bash, lui, PARSE ses arguments numeriques selon LC_NUMERIC. En
# locale fr_FR (virgule decimale), bash refuse "31.38" comme nombre
# valide et arrondit silencieusement (31,00 au lieu de 31,38) au lieu
# de planter -- constate en pratique sur cette machine.
export LC_NUMERIC=C

INTERVAL="${1:-2}"
KWH_PRICE="${KWH_PRICE:-0.25}"

###############################################################################
# Couleurs
###############################################################################

if [[ -t 1 ]]; then
    BOLD="\033[1m"
    RESET="\033[0m"
    DIM="\033[2m"
else
    BOLD=""
    RESET=""
    DIM=""
fi

###############################################################################
# Variables
###############################################################################

CPU_POWER=0
RAM_POWER=0
GPU_POWER=0
DISK_POWER=0
SCREEN_POWER=0
USB_POWER=0

CPU_METHOD="non disponible"
RAM_METHOD="non disponible"
GPU_METHOD="non disponible"
DISK_METHOD="estimation"
SCREEN_METHOD="estimation"
USB_METHOD="estimation"

CPU_DETAILS=""
RAM_DETAILS=""
GPU_DETAILS=""
DISK_DETAILS=""
SCREEN_DETAILS=""
USB_DETAILS=""

###############################################################################
# Outils
###############################################################################

have()
{
    command -v "$1" >/dev/null 2>&1
}

###############################################################################
# Lecture d'un compteur RAPL
#
# Root-only depuis le noyau 5.10 (mitigation d'un canal auxiliaire par
# mesure de consommation, CVE-2020-8694) : les bits de permission du
# fichier (souvent 0400 root:root) reflètent deja cette restriction,
# donc [[ -r ]] suffit a savoir si un `cat` direct marchera. Sinon, on
# retente avec sudo (demande le mot de passe une fois, mis en cache
# ensuite par sudo) plutot que d'abandonner tout de suite.
###############################################################################

read_energy()
{
    local file="$1"

    [[ -e "$file" ]] || return 1

    if [[ -r "$file" ]]; then
        cat "$file" 2>/dev/null
    else
        sudo cat "$file" 2>/dev/null
    fi
}

###############################################################################
# Calcul de puissance RAPL
###############################################################################

rapl_power()
{
    local energy_file="$1"
    local interval="$2"

    local e1 e2 diff

    e1=$(read_energy "$energy_file") || return 1
    [[ -n "$e1" ]] || return 1

    sleep "$interval"

    e2=$(read_energy "$energy_file") || return 1
    [[ -n "$e2" ]] || return 1

    # Gestion d'un éventuel rollover.
    if (( e2 >= e1 )); then
        diff=$((e2 - e1))
    else
        local max_range
        max_range=$(cat "$(dirname "$energy_file")/max_energy_range_uj" 2>/dev/null || echo 0)

        if (( max_range > 0 )); then
            diff=$((max_range - e1 + e2))
        else
            return 1
        fi
    fi

    # énergie en microjoules / secondes / 1 000 000 = watts
    awk -v d="$diff" -v t="$interval" \
        'BEGIN { printf "%.2f", d / t / 1000000 }'
}

###############################################################################
# CPU Intel RAPL
###############################################################################

detect_cpu()
{
    local package="/sys/class/powercap/intel-rapl:0"
    local energy="$package/energy_uj"

    if [[ -e "$energy" ]]; then
        CPU_POWER=$(rapl_power "$energy" "$INTERVAL") || CPU_POWER=0

        if (( $(awk "BEGIN {print ($CPU_POWER > 0)}") )); then
            CPU_METHOD="mesuré"
            CPU_DETAILS=$(cat "$package/name" 2>/dev/null || echo "Intel RAPL")
            return
        fi
    fi

    CPU_METHOD="non disponible"
    CPU_DETAILS="Intel RAPL absent, ou sudo refusé"
}

###############################################################################
# RAM
###############################################################################

detect_ram()
{
    local dram_energy=""
    local dram_name=""

    # Recherche d'un domaine DRAM RAPL.
    while IFS= read -r dir; do
        [[ -e "$dir/energy_uj" ]] || continue

        dram_name=$(cat "$dir/name" 2>/dev/null || true)

        if [[ "${dram_name,,}" == *dram* ]]; then
            dram_energy="$dir/energy_uj"
            break
        fi
    done < <(find /sys/class/powercap -maxdepth 2 -type d \
             -name 'intel-rapl:*' 2>/dev/null)

    if [[ -n "$dram_energy" ]]; then
        RAM_POWER=$(rapl_power "$dram_energy" "$INTERVAL") || RAM_POWER=0

        if (( $(awk "BEGIN {print ($RAM_POWER > 0)}") )); then
            RAM_METHOD="mesuré"
            RAM_DETAILS="Intel RAPL DRAM"
            return
        fi
    fi

    # Sinon estimation basée sur la quantité de RAM.
    local ram_kb ram_gb

    ram_kb=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
    ram_gb=$(awk -v kb="$ram_kb" 'BEGIN {printf "%.1f", kb / 1024 / 1024}')

    # Estimation volontairement conservatrice.
    # ~0.25 W / Go.
    RAM_POWER=$(awk -v gb="$ram_gb" 'BEGIN {printf "%.2f", gb * 0.25}')

    RAM_METHOD="estimé"
    RAM_DETAILS="${ram_gb} Go"
}

###############################################################################
# GPU NVIDIA
###############################################################################

detect_nvidia()
{
    have nvidia-smi || return 1

    local output
    output=$(nvidia-smi \
        --query-gpu=name,power.draw \
        --format=csv,noheader,nounits 2>/dev/null) || return 1

    [[ -n "$output" ]] || return 1

    GPU_POWER=$(awk -F',' '
        {
            gsub(/^[ \t]+|[ \t]+$/, "", $2)
            sum += $2
            names = names (names ? " + " : "") $1
        }
        END {
            printf "%.2f\n", sum
        }
    ' <<< "$output")

    GPU_DETAILS=$(awk -F',' '
        {
            gsub(/^[ \t]+|[ \t]+$/, "", $1)
            names = names (names ? " + " : "") $1
        }
        END {
            print names
        }
    ' <<< "$output")

    GPU_METHOD="mesuré"

    return 0
}

###############################################################################
# GPU AMD / Intel via hwmon
###############################################################################

detect_hwmon_gpu()
{
    # NVIDIA déjà traité.
    (( $(awk "BEGIN {print ($GPU_POWER > 0)}") )) && return 0

    local total=0
    local found=0
    local details=""

    for hw in /sys/class/hwmon/hwmon*; do
        [[ -d "$hw" ]] || continue

        local name
        name=$(cat "$hw/name" 2>/dev/null || true)

        case "${name,,}" in
            amdgpu|i915|xe)
                for power_file in "$hw"/power*_average "$hw"/power*_input; do
                    [[ -r "$power_file" ]] || continue

                    local value
                    value=$(cat "$power_file" 2>/dev/null || echo 0)

                    if [[ "$value" =~ ^[0-9]+$ ]]; then
                        # power*_average est généralement en µW.
                        total=$(awk -v a="$total" -v b="$value" \
                            'BEGIN {printf "%.2f", a + b / 1000000}')
                        found=1
                    fi
                done

                if (( found )); then
                    details="$name"
                fi
                ;;
        esac
    done

    if (( found )); then
        GPU_POWER="$total"
        GPU_METHOD="mesuré"
        GPU_DETAILS="$details"
    fi
}

detect_gpu()
{
    detect_nvidia || true

    if [[ "$GPU_METHOD" != "mesuré" ]]; then
        detect_hwmon_gpu
    fi

    if [[ "$GPU_METHOD" == "non disponible" ]]; then
        GPU_DETAILS="aucun compteur GPU trouvé"
    fi
}

###############################################################################
# Disques
###############################################################################

detect_disks()
{
    local total=0
    local details=""
    local found=0

    for dev in /sys/block/*; do
        [[ -r "$dev/device/model" ]] || continue

        local device
        device=$(basename "$dev")

        # Ignorer les périphériques virtuels.
        case "$device" in
            loop*|ram*|dm-*|zram*|sr*)
                continue
                ;;
        esac

        local model
        model=$(tr -s ' ' < "$dev/device/model" 2>/dev/null | sed 's/^ *//;s/ *$//')

        local rotational
        rotational=$(cat "$dev/queue/rotational" 2>/dev/null || echo 0)

        local power

        if [[ "$rotational" == "1" ]]; then
            # HDD : estimation en fonction de son activité.
            local stat1 stat2 sectors1 sectors2

            stat1=$(cat "$dev/stat" 2>/dev/null || echo "")
            sleep "$INTERVAL"
            stat2=$(cat "$dev/stat" 2>/dev/null || echo "")

            sectors1=$(awk '{print $3+$7}' <<< "$stat1")
            sectors2=$(awk '{print $3+$7}' <<< "$stat2")

            if [[ -n "$sectors1" && -n "$sectors2" ]] &&
               [[ "$sectors1" =~ ^[0-9]+$ && "$sectors2" =~ ^[0-9]+$ ]] &&
               (( sectors2 > sectors1 )); then
                power=5.5
            else
                power=0.8
            fi

            details="${details}${device}=${model:-HDD} (${power}W), "
        else
            # SSD / NVMe.
            if [[ "$device" == nvme* ]]; then
                power=2.5
            else
                power=1.5
            fi

            details="${details}${device}=${model:-SSD} (${power}W), "
        fi

        total=$(awk -v a="$total" -v b="$power" \
            'BEGIN {printf "%.2f", a+b}')

        found=1
    done

    if (( found )); then
        DISK_POWER="$total"
        DISK_METHOD="estimé"
        DISK_DETAILS="${details%, }"
    else
        DISK_DETAILS="aucun disque détecté"
    fi
}

###############################################################################
# Écrans
###############################################################################

detect_screens()
{
    local count=0
    local details=""

    for connector in /sys/class/drm/*; do
        [[ -f "$connector/status" ]] || continue

        local status
        status=$(cat "$connector/status" 2>/dev/null || true)

        [[ "$status" == "connected" ]] || continue

        local name
        name=$(basename "$connector")

        # Estimation moyenne, PAS une mesure : un écran moderne peut
        # être entre ~10 et 50W selon taille/luminosité/fréquence/HDR.
        local power=25

        SCREEN_POWER=$(awk \
            -v a="$SCREEN_POWER" -v b="$power" \
            'BEGIN {printf "%.2f", a+b}')

        count=$((count + 1))

        details="${details}${name}=${power}W, "
    done

    if (( count > 0 )); then
        SCREEN_METHOD="estimé"
        SCREEN_DETAILS="${count} écran(s) : ${details%, }"
    else
        SCREEN_DETAILS="aucun écran détecté"
    fi
}

###############################################################################
# USB
###############################################################################

detect_usb()
{
    local count=0

    if [[ -d /sys/bus/usb/devices ]]; then
        for device in /sys/bus/usb/devices/*; do
            [[ -f "$device/idVendor" ]] || continue
            count=$((count + 1))
        done
    fi

    # Estimation très prudente : on évite de compter les périphériques
    # USB à plusieurs watts chacun.
    USB_POWER=$(awk -v n="$count" 'BEGIN {
        if (n == 0) print "0.00";
        else print "2.00";
    }')

    if (( count > 0 )); then
        USB_DETAILS="${count} périphérique(s) USB"
    else
        USB_DETAILS="aucun périphérique USB détecté"
    fi
}

###############################################################################
# Total
###############################################################################

calculate_total()
{
    awk \
        -v cpu="$CPU_POWER" \
        -v ram="$RAM_POWER" \
        -v gpu="$GPU_POWER" \
        -v disk="$DISK_POWER" \
        -v screen="$SCREEN_POWER" \
        -v usb="$USB_POWER" \
        'BEGIN {
            total=cpu+ram+gpu+disk+screen+usb
            printf "%.2f\n", total
        }'
}

###############################################################################
# Affichage
###############################################################################

print_line()
{
    local component="$1"
    local power="$2"
    local method="$3"
    local details="$4"

    printf "│ %-12s │ %8.2f W │ %-10s │ %-42s │\n" \
        "$component" "$power" "$method" "$details"
}

###############################################################################
# Informations système
###############################################################################

print_system_info()
{
    local hostname
    local kernel
    local cpu
    local mem

    hostname=$(hostname)
    kernel=$(uname -r)

    cpu=$(lscpu 2>/dev/null |
        awk -F: '/Model name:/ {
            sub(/^[ \t]+/, "", $2)
            print $2
            exit
        }')

    mem=$(free -h 2>/dev/null |
        awk '/^Mem:/ {print $2}')

    echo
    echo "${BOLD}Informations système${RESET}"
    echo "  Machine : $hostname"
    echo "  Kernel  : $kernel"
    echo "  CPU     : ${cpu:-inconnu}"
    echo "  RAM     : ${mem:-inconnue}"
    echo
}

###############################################################################
# Programme principal
###############################################################################

main()
{
    print_system_info

    echo "${DIM}Mesure en cours (${INTERVAL}s)...${RESET}"
    echo

    detect_cpu
    detect_ram
    detect_gpu
    detect_disks
    detect_screens
    detect_usb

    local total
    total=$(calculate_total)

    echo "${BOLD}Consommation estimée${RESET}"
    echo

    echo "┌──────────────┬────────────┬────────────┬──────────────────────────────────────────────┐"
    echo "│ Composant    │ Puissance  │ Méthode    │ Détail                                       │"
    echo "├──────────────┼────────────┼────────────┼──────────────────────────────────────────────┤"

    print_line "CPU"    "$CPU_POWER"    "$CPU_METHOD"    "$CPU_DETAILS"
    print_line "RAM"    "$RAM_POWER"    "$RAM_METHOD"    "$RAM_DETAILS"
    print_line "GPU"    "$GPU_POWER"    "$GPU_METHOD"    "$GPU_DETAILS"
    print_line "SSD/HDD" "$DISK_POWER" "$DISK_METHOD"    "$DISK_DETAILS"
    print_line "Écran"  "$SCREEN_POWER" "$SCREEN_METHOD" "$SCREEN_DETAILS"
    print_line "USB"    "$USB_POWER"    "$USB_METHOD"    "$USB_DETAILS"

    echo "├──────────────┼────────────┼────────────┼──────────────────────────────────────────────┤"
    printf "│ ${BOLD}TOTAL${RESET}        │ ${BOLD}%8.2f W${RESET} │            │ estimation logicielle                      │\n" "$total"
    echo "└──────────────┴────────────┴────────────┴──────────────────────────────────────────────┘"

    echo
    echo "${BOLD}Énergie${RESET}"

    local kwh_day
    local kwh_month
    local cost_day
    local cost_month

    kwh_day=$(awk -v w="$total" \
        'BEGIN {printf "%.3f", w * 24 / 1000}')

    kwh_month=$(awk -v w="$total" \
        'BEGIN {printf "%.2f", w * 24 * 30 / 1000}')

    cost_day=$(awk -v k="$kwh_day" -v p="$KWH_PRICE" \
        'BEGIN {printf "%.2f", k*p}')

    cost_month=$(awk -v k="$kwh_month" -v p="$KWH_PRICE" \
        'BEGIN {printf "%.2f", k*p}')

    echo "  À ${total} W constants :"
    echo "    1 jour   : ${kwh_day} kWh  ≈ ${cost_day} €"
    echo "    30 jours : ${kwh_month} kWh ≈ ${cost_month} €"
    echo
    echo "  Prix utilisé : ${KWH_PRICE} €/kWh"

    echo
    echo "${DIM}Attention :"
    echo "  CPU/GPU/RAPL = mesures matérielles lorsque disponibles."
    echo "  RAM/disques/écrans/USB = estimations lorsque Linux ne fournit pas"
    echo "  directement leur consommation."
    echo
    echo "  La consommation à la prise est supérieure au total ci-dessus"
    echo "  à cause de la carte mère, ventilateurs, pertes de l'alimentation,"
    echo "  convertisseurs, périphériques, etc."
    echo
    echo "  Pour connaître la vraie consommation du PC : wattmètre à la prise."
    echo "${RESET}"
}

main "$@"
