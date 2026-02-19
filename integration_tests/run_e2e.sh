#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PNET_IP:-}" ]]; then
  echo "PNET_IP is required. Example: export PNET_IP=192.168.0.108"
  exit 1
fi

export DJANGO_SETTINGS_MODULE=Cyberpolygon.settings
echo "Starting e2e tests with live logs..."
echo "PNET_IP: ${PNET_IP}"
pytest -m integration integration_tests/test_*_e2e.py -vv -s --log-cli-level=INFO --durations=0
