#!/bin/sh
# Штатное завершение радиостанции DJ ALYX
# Убивает все процессы в правильном порядке

echo "=== DJ ALYX — завершение работы ==="
echo "$(date)"

# 1. Сначала start_all.py (чтобы не перезапускал упавшие процессы)
echo "[*] Останавливаю supervisor..."
pkill -f 'start_all.py' 2>/dev/null
sleep 1

# 2. Потом play_music.py
echo "[*] Останавливаю play_music.py..."
pkill -f 'play_music.py' 2>/dev/null
sleep 1

# 3. Потом ezstream и ffmpeg
echo "[*] Останавливаю ezstream и ffmpeg..."
pkill -9 -f 'ezstream' 2>/dev/null
pkill -9 -f 'ffmpeg.*pipe:0' 2>/dev/null
pkill -9 -f 'ffmpeg.*pipe:1' 2>/dev/null
sleep 1

# 4. Старый icecast источник и network monitor
echo "[*] Останавливаю network monitor..."
pkill -f 'network_monitor' 2>/dev/null

# 5. Проверка что всё встало
LEFT=$(ps aux | grep -E 'play_music|ezstream|ffmpeg.*pipe' | grep -v grep | wc -l)
if [ "$LEFT" -gt 0 ]; then
    echo "[!] Осталось $LEFT процессов — принудительно:"
    ps aux | grep -E 'play_music|ezstream|ffmpeg.*pipe' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
fi

echo "[✓] Все процессы радио остановлены"
echo "Для запуска: python3 start_all.py [--fm]"
