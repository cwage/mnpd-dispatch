#!/bin/bash

# MNPD Dispatch Checker
# Query local MNPD dispatch API for nearby police/fire dispatches

API_BASE="http://127.0.0.1:5001"

usage() {
    echo "Usage: $0 -a <address> [-r <radius>] [-f]"
    echo "       $0 -l"
    echo ""
    echo "Options:"
    echo "  -a <addr>    Search near this address (required for proximity search)"
    echo "  -r <miles>   Search radius in miles (default: 2)"
    echo "  -f           Include fire department dispatches"
    echo "  -l           List all active dispatches (no proximity filter)"
    echo ""
    echo "Examples:"
    echo "  $0 -a '600 Broadway, Nashville, TN'"
    echo "  $0 -a '123 Main St, Nashville, TN' -r 1"
    echo "  $0 -a '123 Main St, Nashville, TN' -f -r 3"
    echo "  $0 -l"
    exit 1
}

format_timestamp() {
    local iso_ts="$1"
    TZ="America/Chicago" date -d "$iso_ts" "+%Y-%m-%d %I:%M:%S %p %Z" 2>/dev/null || echo "$iso_ts"
}

time_ago() {
    local iso_ts="$1"
    local then_epoch
    then_epoch=$(date -d "$iso_ts" +%s 2>/dev/null) || return
    local now_epoch
    now_epoch=$(date +%s)
    local diff=$(( now_epoch - then_epoch ))

    if [[ $diff -lt 60 ]]; then
        echo "${diff}s ago"
    elif [[ $diff -lt 3600 ]]; then
        echo "$(( diff / 60 ))m ago"
    elif [[ $diff -lt 86400 ]]; then
        local h=$(( diff / 3600 ))
        local m=$(( (diff % 3600) / 60 ))
        echo "${h}h ${m}m ago"
    else
        local d=$(( diff / 86400 ))
        local h=$(( (diff % 86400) / 3600 ))
        echo "${d}d ${h}h ago"
    fi
}

print_dispatch() {
    local item="$1"
    local search_address="$2"

    local incident_type incident_code address city source
    local call_received last_updated distance lat lng

    incident_type=$(echo "$item" | jq -r '.incident_type')
    incident_code=$(echo "$item" | jq -r '.incident_type_code')
    address=$(echo "$item" | jq -r '.address // "N/A"')
    city=$(echo "$item" | jq -r '.city // ""')
    source=$(echo "$item" | jq -r '.source')
    call_received=$(echo "$item" | jq -r '.call_received')
    last_updated=$(echo "$item" | jq -r '.last_updated')
    distance=$(echo "$item" | jq -r '.distance_miles')
    lat=$(echo "$item" | jq -r '.latitude')
    lng=$(echo "$item" | jq -r '.longitude')
    location_info=$(echo "$item" | jq -r '.location_info // empty')

    local source_label
    if [[ "$source" == "police" ]]; then
        source_label="MNPD"
    else
        source_label="NFD"
    fi

    local received_fmt ago_str
    received_fmt=$(format_timestamp "$call_received")
    ago_str=$(time_ago "$call_received")

    echo "───────────────────────────────────────────────────────"
    printf "  %-20s %s\n" "$source_label" "$incident_type"
    if [[ -n "$incident_code" && "$incident_code" != "" ]]; then
        printf "  %-20s %s\n" "Code:" "$incident_code"
    fi
    echo ""
    if [[ -n "$address" && "$address" != "N/A" && "$address" != "" ]]; then
        printf "  Address:          %s\n" "$address"
    fi
    if [[ -n "$city" && "$city" != "" ]]; then
        printf "  Area:             %s\n" "$city"
    fi
    if [[ -n "$location_info" ]]; then
        printf "  Location Info:    %s\n" "$location_info"
    fi
    echo ""
    printf "  Received:         %s (%s)\n" "$received_fmt" "$ago_str"
    echo ""
    if [[ -n "$distance" && "$distance" != "null" ]]; then
        printf "  Distance:         %s miles\n" "$distance"
    fi
    local dispatch_addr="${address}, ${city}, Nashville, TN"
    local encoded_dispatch=$(echo "$dispatch_addr" | tr -d '\n' | jq -sRr @uri)
    if [[ -n "$search_address" ]]; then
        local encoded_search=$(echo "$search_address" | tr -d '\n' | jq -sRr @uri)
        echo "  Map:              https://www.google.com/maps/dir/$encoded_search/$encoded_dispatch"
    else
        echo "  Map:              https://www.google.com/maps/search/$encoded_dispatch"
    fi
    echo ""
}

address=""
radius="2"
include_fire=""
list_all=false

while getopts "a:r:flh" opt; do
    case $opt in
        a) address="$OPTARG" ;;
        r) radius="$OPTARG" ;;
        f) include_fire="true" ;;
        l) list_all=true ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Check if API is running
if ! curl -s "$API_BASE/health" > /dev/null 2>&1; then
    echo "Error: API not running at $API_BASE"
    echo "Start it with: cd $(dirname "$0") && docker compose up -d"
    exit 1
fi

if $list_all; then
    response=$(curl -s "$API_BASE/dispatches/all")
    count=$(echo "$response" | jq '.count')

    echo ""
    echo "═══════════════════════════════════════════════════════"
    echo "  ALL ACTIVE DISPATCHES ($count)"
    echo "═══════════════════════════════════════════════════════"

    if [[ "$count" -eq 0 ]]; then
        echo ""
        echo "  No active dispatches."
        echo ""
        exit 0
    fi

    for i in $(seq 0 $((count - 1))); do
        item=$(echo "$response" | jq ".dispatches[$i]")
        print_dispatch "$item" ""
    done
    echo "═══════════════════════════════════════════════════════"
    exit 0
fi

if [[ -z "$address" ]]; then
    echo "Error: -a <address> is required for proximity search"
    echo ""
    usage
fi

encoded_address=$(echo "$address" | tr -d '\n' | jq -sRr @uri)
url="$API_BASE/nearby?address=$encoded_address&radius=$radius"
if [[ -n "$include_fire" ]]; then
    url="$url&fire=true"
fi
response=$(curl -s "$url")

if echo "$response" | jq -e '.error' > /dev/null 2>&1; then
    echo "Error: $(echo "$response" | jq -r '.error')"
    exit 1
fi

count=$(echo "$response" | jq -r '.count')

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  DISPATCHES NEAR: $address"
echo "  Radius: ${radius} mi | Found: $count"
echo "═══════════════════════════════════════════════════════"

if [[ "$count" -eq 0 ]]; then
    echo ""
    echo "  No active dispatches within ${radius} miles."
    echo ""
    echo "═══════════════════════════════════════════════════════"
    exit 0
fi

for i in $(seq 0 $((count - 1))); do
    item=$(echo "$response" | jq ".dispatches[$i]")
    print_dispatch "$item" "$address"
done
echo "═══════════════════════════════════════════════════════"
