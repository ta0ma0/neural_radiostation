import os
import subprocess
import threading
from datetime import datetime

_tts_lock = threading.Lock()


def tty_log(message, style="info"):
    colors = {
        "info": "\033[32m[SYSTEM]\033[0m",
        "on_air": "\033[36m[ON AIR]\033[0m",
        "ai": "\033[35m[⚙️ AI]\033[0m",
        "error": "\033[31m[ERROR]\033[0m",
        "time": f"\033[90m{datetime.now().strftime('%H:%M:%S')}\033[0m",
    }
    prefix = colors.get(style, colors["info"])

    # 1. Формируем строку сообщения
    full_message = f"{colors['time']} {prefix} {message}"

    # 2. Пишем в файл (для контейнера)
    with open(
        "/home/ruslan/Develop/Music/dj_alyx/django-aws-terminal-websocket/dj_alyx_radio.log",
        "a",
        encoding="utf-8",
    ) as f:
        f.write(f"{full_message}\n")

    # 3. Выводим в консоль с flush=True
    print(full_message, flush=True)


class AlyxVoice:
    def __init__(self, model_path, ref_text, ref_audio, device="cpu"):
        self.model_path = model_path
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.device = device
        tty_log("[*] [System]: Voice Engine инициализирован.")

    def generate(self, text, output_path, speed=1.1):
        if not _tts_lock.acquire(blocking=False):
            tty_log("[!] TTS уже занят, пропускаю генерацию", "error")
            return None

        try:
            # 1. Определяем пути
            base_path = os.path.splitext(output_path)[0]
            wav_path = base_path + ".wav"
            mp3_path = base_path + ".mp3"

            output_dir = os.path.dirname(wav_path)
            output_filename = os.path.basename(wav_path)

            cmd = [
                "python",
                "-m",
                "f5_tts.infer.infer_cli",
                "-p",
                self.model_path,
                "-r",
                self.ref_audio,
                "-s",
                self.ref_text,
                "-t",
                text,
                "-o",
                output_dir,
                "-w",
                output_filename,
                "--device",
                self.device,
                "--nfe_step",
                "6",
                "--speed",
                str(speed),
            ]

            # 2. Генерация WAV (Popen чтобы убить при таймауте)
            nice_cmd = ["nice", "-n", "19"] + cmd
            proc = subprocess.Popen(nice_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                stdout, stderr = proc.communicate(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
                os.system("pkill -9 -f 'f5_tts.infer.infer_cli' 2>/dev/null")
                tty_log(f"[!] Таймаут TTS: {text[:50]}...", "error")
                return None

            if proc.returncode != 0:
                tty_log(f"[!] Ошибка CLI: {stderr.decode()}")
                return None

            if not os.path.exists(wav_path):
                return None

            # 3. Конвертация в MP3
            conv_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                wav_path,
                "-acodec",
                "libmp3lame",
                "-q:a",
                "2",
                mp3_path,
            ]
            conv_proc = subprocess.Popen(conv_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                conv_stdout, conv_stderr = conv_proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                conv_proc.kill()
                conv_proc.wait(timeout=5)
                tty_log(f"[!] Таймаут ffmpeg конвертации TTS", "error")
                return None

            if conv_proc.returncode != 0:
                tty_log(f"[!] Ошибка FFmpeg: {conv_stderr.decode()}")
                return None
            if os.path.exists(wav_path):
                os.remove(wav_path)

            return mp3_path
        finally:
            _tts_lock.release()
