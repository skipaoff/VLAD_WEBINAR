#!/bin/bash
# Новый бизнес из шаблона: tools/new-business.sh имя-клиента
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="${1:-}"
[ -z "$NAME" ] && { echo "Как: tools/new-business.sh имя-клиента"; exit 1; }
[ -d "business/$NAME" ] && { echo "business/$NAME уже есть — не перезаписываю"; exit 1; }

cp -R business/_template "business/$NAME"
echo "Создано: business/$NAME"
echo
echo "Дальше:"
echo "  1. заполнить метки {{...}} — начни с 03-prices.md и 10-limits.md"
echo "  2. в config.json поставить \"business\": \"$NAME\""
echo "  3. python3 -m pytest -q tests"
