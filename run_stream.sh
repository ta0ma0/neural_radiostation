#!/bin/sh
# Радиостанция DJ ALYX
# Для запуска нейродиджея (без FM):
#   ./run_stream.sh
# Для запуска с FM-трансмиттером:
#   ./run_stream.sh --fm

exec python3 start_all.py "$@"
