#!/usr/bin/env sh
cd "$(dirname "$0")" || exit 1
export DREAMCRAWLER_ALLOW_STANDALONE=1
exec python3 main.py
