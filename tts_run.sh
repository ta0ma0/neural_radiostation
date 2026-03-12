python -m f5_tts.infer.infer_cli \
-p "/home/ruslan/Develop/Voice/f5-tts/f5-tts-model/F5-TTS_RUSSIA/f5-tts-model/F5TTS_Russian/F5TTS_v1_Base_v2/model_last.pt" \
--ref_audio "rachel.capell_audiobook_16_07_24_short.wav" \
--ref_text "How could he get back his title as the smelliest, stinkiest skunk?" \
--gen_text "Привет всем, это ваш DJ Alyx на волнах! Готовьтесь окунуться в атмосферу, потому что сегодня у нас на очереди группа Aviators. Ох, ребята, эта история просто загляденье!" \
--device cpu
