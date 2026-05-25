#!/bin/sh
echo "Start GNU Radio"
python fm.py 2>&1 &
echo "Ждем запуска 3 сек"
conda avtivate f5-tts
sleep 3
echo "Запуск радиостанции ждем 3 секунды"
python play_music.py 2>&1 &
sleep 3
echo "Запуск стрима"
./run_stream.sh
