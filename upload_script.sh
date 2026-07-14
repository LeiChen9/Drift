#!/usr/bin/env bash
set -euo pipefail

rclone copy --progress --exclude "_success/**" --exclude "_fails/**" asset/script cloudflare-r2:bonfire/script/
echo "Done"
