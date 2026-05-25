#!/bin/sh
# Запуск радиостанции DJ ALYX
# Без аргументов — только интернет-вещание
# С флагом --fm — ещё и FM-трансмиттер (HackRF на 95 MHz)

exec python3 start_all.py "$@"
