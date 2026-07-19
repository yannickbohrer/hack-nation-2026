#!/usr/bin/env bash

for i in {1..1000}; do
    echo "$(date +%H:%M:%S) [INFO] module01.amrfinder_runner: AMRFinderPlus found $((RANDOM % 15 + 1)) hits for 562.$((100000 + RANDOM % 899999))"
    sleep 0.01
done
