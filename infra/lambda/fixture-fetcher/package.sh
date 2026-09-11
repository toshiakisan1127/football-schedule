#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:-/asset-output}"

python -m pip install --no-cache-dir -r requirements.txt -t "$output_dir"
cp ./*.py "$output_dir"/
