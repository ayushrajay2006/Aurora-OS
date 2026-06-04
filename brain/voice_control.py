import os
import re
import gc
import queue
import threading
import speech_recognition as sr
import pyttsx3
from config.logging import logger

class TextToSpeechManager:
    def __init__(self, rate: int = 180, voice_index: int = 1, volume: float = 1.0, voice_name: str = "af_bella"):
        self.rate = rate
        self.voice_index = voice_index
        self.volume = volume
        self.voice_name = voice_name
        self._lock = threading.Lock()
        
        self.use_neural = False
        self._kokoro = None
        self._pyaudio_instance = None
        
        # Try loading Kokoro ONNX neural engine
        try:
            from kokoro_onnx import Kokoro
            import pyaudio
            
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(project_root, "models", "kokoro-v1.0.onnx")
            voices_path = os.path.join(project_root, "models", "voices-v1.0.bin")
            
            if os.path.exists(model_path) and os.path.exists(voices_path):
                logger.info("TextToSpeechManager: Initializing neural engine (Kokoro)...")
                self._kokoro = Kokoro(model_path, voices_path)
                self._pyaudio_instance = pyaudio.PyAudio()
                self.use_neural = True
                logger.info("TextToSpeechManager: Neural engine initialized successfully.")
            else:
                logger.warning(f"TextToSpeechManager: Model files not found at '{model_path}' or '{voices_path}'. Falling back to SAPI5.")
        except Exception as e:
            logger.warning(f"TextToSpeechManager: Could not initialize neural engine: {e}. Falling back to SAPI5.")

    def speak(self, text: str):
        """Speaks the specified text verbally (blocking)."""
        clean_text = self._clean_speech_text(text)
        if not clean_text:
            return
            
        from config.event_bus import event_bus
        event_bus.publish("speech_started", text=clean_text)
        
        try:
            if self.use_neural and self._kokoro and self._pyaudio_instance:
                with self._lock:
                    try:
                        logger.debug(f"Speaking (Neural): '{clean_text}'")
                        sentences = self._split_into_sentences(clean_text)
                        if not sentences:
                            return
                        
                        audio_queue = queue.Queue(maxsize=2)
                        
                        # Determine voice name dynamically
                        voice = self.voice_name
                        if self.voice_index == 0:
                            voice = "am_adam"
                        elif self.voice_index == 2:
                            voice = "af_sarah"
                        elif self.voice_index == 3:
                            voice = "af_sky"
                        
                        speed = max(0.5, min(2.0, self.rate / 180.0))
                        
                        def synthesizer_worker():
                            try:
                                for s in sentences:
                                    s_text = s.strip()
                                    if not s_text:
                                        continue
                                    logger.debug(f"Neural TTS Synthesizing: '{s_text}' using voice '{voice}'")
                                    samples, sample_rate = self._kokoro.create(
                                        s_text,
                                        voice=voice,
                                        speed=speed,
                                        lang="en-us"
                                    )
                                    audio_queue.put((samples, sample_rate))
                            except Exception as e:
                                logger.error(f"Error in neural synthesizer worker: {e}")
                            finally:
                                audio_queue.put(None)
                                
                        # Start synthesizer thread
                        t = threading.Thread(target=synthesizer_worker, daemon=True)
                        t.start()
                        
                        # Player loop (blocking)
                        import pyaudio
                        stream = None
                        while True:
                            item = audio_queue.get()
                            if item is None:
                                break
                            
                            samples, sample_rate = item
                            if stream is None:
                                stream = self._pyaudio_instance.open(
                                    format=pyaudio.paFloat32,
                                    channels=1,
                                    rate=sample_rate,
                                    output=True
                                )
                            stream.write(samples.tobytes())
                            
                        if stream is not None:
                            stream.stop_stream()
                            stream.close()
                            
                    except Exception as e:
                        logger.error(f"Error in neural TTS playback: {e}. Falling back to SAPI5.")
                        self._speak_sapi5(clean_text)
            else:
                self._speak_sapi5(clean_text)
        finally:
            event_bus.publish("speech_completed", text=clean_text)

    def _speak_sapi5(self, clean_text: str):
        """Standard fallback SAPI5 TTS generation."""
        with self._lock:
            try:
                logger.debug(f"Speaking (SAPI5 Fallback): '{clean_text}'")
                engine = pyttsx3.init()
                engine.setProperty('rate', self.rate)
                engine.setProperty('volume', self.volume)
                
                voices = engine.getProperty('voices')
                if 0 <= self.voice_index < len(voices):
                    engine.setProperty('voice', voices[self.voice_index].id)
                
                engine.say(clean_text)
                engine.runAndWait()
                engine.stop()
                del engine
                gc.collect()
            except Exception as e:
                logger.error(f"Error in SAPI5 fallback speak: {e}")

    def _split_into_sentences(self, text: str) -> list:
        """Splits text into clean sentences for streaming playback."""
        sentence_end = re.compile(r'(?<=[.!?])\s+')
        sentences = sentence_end.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _clean_speech_text(self, text: str) -> str:
        """Strips out markdown syntax, urls, and JSON blocks for clean text-to-speech output."""
        # 1. Remove markdown code blocks (e.g. ```json ... ```)
        clean = re.sub(r"```[a-zA-Z]*\s*.*?\s*```", "", text, flags=re.DOTALL)
        
        # 2. Remove URLs
        clean = re.sub(r"https?://\S+", "", clean)
        
        # 3. Clean up formatting symbols like bold/italics
        clean = clean.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
        
        return clean.strip()

    def __del__(self):
        try:
            if hasattr(self, '_pyaudio_instance') and self._pyaudio_instance:
                self._pyaudio_instance.terminate()
        except Exception:
            pass


class SpeechToTextManager:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
    def adjust_for_noise(self):
        """Adjusts the microphone threshold based on ambient background noise."""
        try:
            logger.info("SpeechToText: Adjusting for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            logger.info("SpeechToText: Ambient noise adjustment complete.")
        except Exception as e:
            logger.error(f"SpeechToText failed to adjust for noise: {e}")
            
    def listen_and_transcribe(self, timeout: float = 6.0, phrase_time_limit: float = 10.0) -> str:
        """Listens to the microphone and returns the transcribed text (non-blocking when quiet)."""
        try:
            with self.microphone as source:
                logger.info("SpeechToText: Listening...")
                print("\nListening... ", end="", flush=True)
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                
            logger.info("SpeechToText: Transcribing...")
            print("\rTranscribing... ", end="", flush=True)
            text = self.recognizer.recognize_google(audio)
            print("\r" + " " * 30 + "\r", end="", flush=True) # Clear status line
            logger.info(f"SpeechToText Transcribed: '{text}'")
            return text.strip()
        except sr.WaitTimeoutError:
            print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.debug("SpeechToText listen timeout (no speech detected).")
            return ""
        except sr.UnknownValueError:
            print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.debug("SpeechToText could not understand audio.")
            return ""
        except sr.RequestError as e:
            print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.error(f"SpeechToText request error: {e}")
            return ""
        except Exception as e:
            print("\r" + " " * 30 + "\r", end="", flush=True)
            logger.error(f"SpeechToText failed: {e}")
            return ""
