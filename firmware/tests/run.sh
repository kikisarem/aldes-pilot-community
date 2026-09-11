#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
D=$(mktemp -d /tmp/workbench-tests.XXXXXX)
trap 'rm -rf "$D"' EXIT
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined -I src tests/test_protocol.c src/control_protocol.c -o "$D/protocol"
"$D/protocol"
cc -std=c11 -Wall -Wextra -Wno-unused-function -Wno-unused-parameter -fsanitize=address,undefined -I tests/stubs -I src tests/test_netcontrol.c src/control_protocol.c -o "$D/tcp"
"$D/tcp"
python3 tests/test_tx.py
PYTHONDONTWRITEBYTECODE=1 python3 tests/test_client.py
