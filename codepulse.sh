#!/bin/bash
# Convenience launcher — activates venv then runs codepulse
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/.venv/bin/codepulse" "$@"
