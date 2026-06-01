#!/bin/sh
# Полный перезапуск радиостанции DJ ALYX
# Убивает все процессы и запускает заново через start_all.py

echo "=== DJ ALYX — полный перезапуск ==="
echo "$(date)"

# 1. Убить все процессы радио
echo "[*] Останавливаю процессы..."
pkill -9 -f 'start_all.py' 2>/dev/null
pkill -9 -f 'play_music.py' 2>/dev/null
pkill -9 -f 'ezstream' 2>/dev/null
pkill -9 -f 'ffmpeg.*icecast' 2>/dev/null
pkill -9 -f 'ffmpeg.*pipe:0' 2>/dev/null
pkill -9 -f 'ffmpeg.*pipe:1' 2>/dev/null
sleep 2

# 2. Убить network monitor
pkill -f 'network_monitor' 2>/dev/null

# 3. Проверить что всё остановилось
LEFT=$(ps aux | grep -E 'play_music|ezstream|ffmpeg' | grep -v grep | wc -l)
if [ "$LEFT" -gt 0 ]; then
    echo "[!] Осталось $LEFT процессов — принудительно:"
    ps aux | grep -E 'play_music|ezstream|ffmpeg' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
fi
echo "[✓] Все процессы остановлены"

# 4. Принудительно убить источник на Icecast (чтобы освободить mount)
ssh -o ConnectTimeout=5 firstbyte "curl -s -u admin:4MHs7KsM_bPwJSe3 'http://127.0.0.1:8000/admin/killsource?mount=/djalyx' 2>/dev/null" 2>&1
sleep 1

# 5. Очистить временные файлы речи (если залипли)
rm -f /home/ruslan/Develop/Music/dj_alyx/temp_speech/gen_*.mp3 2>/dev/null

# 5. Запустить радио через start_all.py
echo "[*] Запускаю радио..."
cd /home/ruslan/Develop/Music/dj_alyx
nohup python3 -u start_all.py &>/tmp/start_all_restart.log &
echo "[✓] start_all.py PID: $!"

# 6. Запустить network monitor
echo "[*] Запускаю network monitor..."
nohup python3 tools/network_monitor.py &>/tmp/netmon.log &
echo "[✓] network_monitor PID: $!"

# 7. Ждать и проверить
sleep 10
STATUS=$(curl -s --max-time 3 https://djalyx.2077911.xyz/api/status/ 2>&1 | grep -oP '(?<="streaming":)[^,]+')
echo "[*] Статус: $STATUS"

if [ "$STATUS" = " true" ]; then
    echo "[✓] Радио в эфире!"
else
    echo "[!] Статус: $STATUS — жду ещё 20 секунд..."
    sleep 20
    curl -s --max-time 3 https://djalyx.2077911.xyz/api/status/ 2>&1
fi
