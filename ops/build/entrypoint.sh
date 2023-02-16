#!/bin/bash
# This is the entrypoint for the network-tracing image

set -e

if [[ -n "$DEBUG" ]]; then
    set -x
fi

title() {
    echo -e "\e[1;34m[$(date '+%F %T')]" "$@" "\e[0m"
}

error() {
    echo -e "\e[1;31m[$(date '+%F %T')]" "$@" "\e[0m"
}

log() {
    echo -e "[$(date '+%F %T')]" "$@"
}

NTD_CONFIG=/etc/network-tracing/ntd-config.json
NTCTL_CONFIG=/root/.config/network-tracing/ntctl-config.json

title "Updating daemon config from environment variables"

if [[ ! -f "$NTD_CONFIG" ]]; then
    mkdir -p "$(dirname "$NTD_CONFIG")"
    echo '{}' > "$NTD_CONFIG"
    log "Initialized daemon config file at $NTD_CONFIG"
fi

if [[ -n "$NTD_API_HOST" ]]; then
    EXPR=".api.host = \"$NTD_API_HOST\""
    jq "$EXPR" "$NTD_CONFIG" | sponge "$NTD_CONFIG"
    log "Updated $EXPR"
fi

if [[ -n "$NTD_API_PORT" ]]; then
    EXPR=".api.port = $NTD_API_PORT"
    jq "$EXPR" "$NTD_CONFIG" | sponge "$NTD_CONFIG"
    log "Updated $EXPR"
fi

if [[ -n "$NTD_API_CORS" ]]; then
    EXPR=".api.cors = true"
    jq "$EXPR" "$NTD_CONFIG" | sponge "$NTD_CONFIG"
    log "Updated $EXPR"
fi

if [[ -n "$NTD_LOGGING_LEVEL" ]]; then
    EXPR=".logging.level = \"$NTD_LOGGING_LEVEL\""
    jq "$EXPR" "$NTD_CONFIG" | sponge "$NTD_CONFIG"
    log "Updated $EXPR"
fi

title "Updating CLI config from environment variables"

if [[ ! -f "$NTCTL_CONFIG" ]]; then
    mkdir -p "$(dirname "$NTCTL_CONFIG")"
    echo '{}' > "$NTCTL_CONFIG"
    log "Initialized CLI config file at $NTCTL_CONFIG"
fi

if [[ -n "$NTCTL_BASE_URL" ]]; then
    EXPR=".base_url = \"$NTCTL_BASE_URL\""
    jq "$EXPR" "$NTCTL_CONFIG" | sponge "$NTCTL_CONFIG"
    log "Updated $EXPR"
fi

if [[ -n "$NTCTL_LOGGING_LEVEL" ]]; then
    EXPR=".logging_level = \"$NTCTL_LOGGING_LEVEL\""
    jq "$EXPR" "$NTCTL_CONFIG" | sponge "$NTCTL_CONFIG"
    log "Updated $EXPR"
fi

if [[ -n "$NTCTL_BUFFER_SIZE" ]]; then
    EXPR=".buffer_size = $NTCTL_BUFFER_SIZE"
    jq "$EXPR" "$NTCTL_CONFIG" | sponge "$NTCTL_CONFIG"
    log "Updated $EXPR"
fi

if [[ -n "$NTCTL_INFLUXDB_CONFIG" ]]; then
    EXPR=".influxdb_config = \"$NTCTL_INFLUXDB_CONFIG\""
    jq "$EXPR" "$NTCTL_CONFIG" | sponge "$NTCTL_CONFIG"
    log "Updated $EXPR"
fi

title "Starting application"

exec "$@"
