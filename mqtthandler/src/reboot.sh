#! /bin/sh

# Device neustarten
# Vgl. https://www.balena.io/docs/learn/develop/runtime/#reboot-from-inside-the-container

curl -X POST --header "Content-Type:application/json" \
    "$BALENA_SUPERVISOR_ADDRESS/v1/reboot?apikey=$BALENA_SUPERVISOR_API_KEY"