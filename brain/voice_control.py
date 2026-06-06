import os
import re
import gc
import queue
import threading
import struct
import math
from config.logging import logger

# ─── Optional dependency capability flags ────────────────────────────────────
# Lazy-loaded at module level so a missing package never crashes the import.
# The rest of the system checks these flags before using voice features.

_sr = None
_pyttsx3 = None
SPEECH_RECOGNITION_AVAILABLE = False
TTS_SAPI5_AVAILABLE = False

try:
    import speech_recognition as _sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    logger.warning(
        "voice_control: 'speech_recognition' not installed — STT disabled. "
        "Fix: pip install SpeechRecognition"
    )

try:
    import pyttsx3 as _pyttsx3
    TTS_SAPI5_AVAILABLE = True
except ImportError:
    logger.warning(
        "voice_control: 'pyttsx3' not installed — SAPI5 TTS disabled. "
        "Fix: pip install pyttsx3"
    )


def _cwrite(text: str):
    """Safe console write — no-op when stdout is None (pythonw.exe)."""
    import sys
    if sys.stdout:
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except Exception:
            pass

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
        """Speaks the specified text verbally (blocking). No-op if TTS unavailable."""
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
                        
                        # Player loop (blocking) — emits tts_amplitude at ~30Hz
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
                            
                            # Compute RMS amplitude and publish ~30Hz events
                            chunk_size = max(1, sample_rate // 30)  # ~33ms chunks
                            for i in range(0, len(samples), chunk_size):
                                chunk = samples[i:i + chunk_size]
                                if len(chunk) > 0:
                                    rms = math.sqrt(max(0.0, sum(float(x) ** 2 for x in chunk) / len(chunk)))
                                    amplitude = min(1.0, rms / 0.3)  # normalize: 0.3 full-scale
                                    event_bus.publish("tts_amplitude", value=round(amplitude, 3))
                                stream.write(chunk.tobytes())
                            
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
        """Standard fallback SAPI5 TTS generation. No-op if pyttsx3 unavailable."""
        if not TTS_SAPI5_AVAILABLE or _pyttsx3 is None:
            logger.warning(f"TTS (SAPI5) unavailable — would have spoken: '{clean_text[:60]}'")
            return
        with self._lock:
            try:
                logger.debug(f"Speaking (SAPI5 Fallback): '{clean_text}'")
                engine = _pyttsx3.init()
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
    """Speech-to-text manager. Degrades gracefully if speech_recognition is missing."""

    def __init__(self):
        self.available = SPEECH_RECOGNITION_AVAILABLE
        self.recognizer = None
        self.microphone = None

        if not self.available:
            logger.warning(
                "SpeechToTextManager: speech_recognition unavailable — STT disabled. "
                "Fix: pip install SpeechRecognition pyaudio"
            )
            return

        self.recognizer = _sr.Recognizer()
        try:
            self.microphone = _sr.Microphone()
        except Exception as e:
            logger.warning(f"SpeechToTextManager: Could not open microphone: {e}")
            self.available = False
            return

        # Configure recognizer properties
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.2
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 0.6

        # Try local Whisper first, fall back to Google
        self._use_whisper = False
        self._whisper_model = None
        try:
            from faster_whisper import WhisperModel
            try:
                self._whisper_model = WhisperModel(
                    "small",
                    device="cuda",
                    compute_type="float16"
                )
                logger.info("SpeechToTextManager: Local Whisper (faster-whisper/small) loaded on GPU.")
            except Exception as cuda_err:
                logger.warning(f"Whisper CUDA init failed ({cuda_err}), falling back to CPU...")
                self._whisper_model = WhisperModel(
                    "small",
                    device="cpu",
                    compute_type="int8"
                )
                logger.info("SpeechToTextManager: Local Whisper loaded on CPU.")
            self._use_whisper = True
        except Exception as e:
            logger.info(f"SpeechToTextManager: Whisper not available ({e}). Will use Google STT.")

    def adjust_for_noise(self):
        """Adjusts the microphone threshold based on ambient background noise."""
        if not self.available or self.microphone is None:
            return
        try:
            logger.info("SpeechToText: Adjusting for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1.2)
            logger.info(f"SpeechToText: Noise adjustment complete. Energy threshold: {self.recognizer.energy_threshold}")
        except Exception as e:
            logger.error(f"SpeechToText failed to adjust for noise: {e}")
            
    def _post_process_transcript(self, text: str) -> str:
        """Fixes common phonetic transcription errors for wake phrases and commands."""
        if not text:
            return ""
            
        corrections = {
            r"\b(arora|orora|laura|flora|avrora|rora|aura|ourora|roro|rorah|alora)\b": "aurora",
            r"\b(note\s*pad|note\s*book|notepads)\b": "notepad",
            r"\b(coke|cal|elk|cow|calc\s*file|coal|celt)\b": "calc",
            r"\b(open\s+grave|open\s+rave|open\s+wave|open\s+crate)\b": "open brave",
            r"\b(bi|by|bi-bi|by-by|bye-bye)\b": "bye",
            r"\b(cmd\s*prompt|command\s*prompt|command\s*shell)\b": "cmd",
            r"\b(file\s*explorer|windows\s*explorer|my\s*computer|this\s*pc)\b": "explorer",
        }
        
        processed_text = text
        for pattern, correction in corrections.items():
            processed_text = re.sub(pattern, correction, processed_text, flags=re.IGNORECASE)
            
        return processed_text.strip()

    def _transcribe_whisper(self, audio_data) -> str:
        """Transcribe audio bytes using local faster-whisper model."""
        try:
            import io
            import numpy as np
            # Convert AudioData to raw WAV bytes → numpy float32 array
            wav_bytes = audio_data.get_wav_data()
            import wave
            with wave.open(io.BytesIO(wav_bytes)) as wf:
                frames = wf.readframes(wf.getnframes())
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

            segments, _ = self._whisper_model.transcribe(samples, language="en", beam_size=5)
            text = " ".join(seg.text for seg in segments).strip()
            logger.info(f"SpeechToText (Whisper): '{text}'")
            return text
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return ""

    def listen_and_transcribe(self, timeout: float = 6.0, phrase_time_limit: float = 10.0, mode: str = "command") -> str:
        """Listens to the microphone and returns the transcribed text. Returns '' if unavailable."""
        from config.event_bus import event_bus

        if not self.available or self.microphone is None or self.recognizer is None:
            logger.debug("SpeechToText: STT unavailable, skipping listen.")
            return ""

        try:
            event_bus.publish("listening_started", mode=mode)
            with self.microphone as source:
                logger.info("SpeechToText: Listening...")
                _cwrite("\nListening... ")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                
            logger.info("SpeechToText: Transcribing...")
            _cwrite("\rTranscribing... ")

            # Try local Whisper first
            if self._use_whisper and self._whisper_model is not None:
                text = self._transcribe_whisper(audio)
            else:
                # Fallback: Google online STT
                text = self.recognizer.recognize_google(audio)

            _cwrite("\r" + " " * 30 + "\r")
            logger.info(f"SpeechToText Transcribed (Raw): '{text}'")
            
            processed_text = self._post_process_transcript(text)
            logger.info(f"SpeechToText Transcribed (Processed): '{processed_text}'")
            
            event_bus.publish("listening_finished", transcript=processed_text.strip(), confidence=1.0)
            return processed_text.strip()

        except _sr.WaitTimeoutError:
            _cwrite("\r" + " " * 30 + "\r")
            logger.debug("SpeechToText listen timeout (no speech detected).")
            event_bus.publish("listening_finished", transcript="", confidence=0.0)
            return ""
        except _sr.UnknownValueError:
            _cwrite("\r" + " " * 30 + "\r")
            logger.debug("SpeechToText could not understand audio.")
            event_bus.publish("listening_finished", transcript="", confidence=0.0)
            return ""
        except _sr.RequestError as e:
            _cwrite("\r" + " " * 30 + "\r")
            logger.error(f"SpeechToText request error: {e}")
            event_bus.publish("listening_finished", transcript="", confidence=0.0)
            return ""
        except Exception as e:
            _cwrite("\r" + " " * 30 + "\r")
            logger.error(f"SpeechToText failed: {e}")
            event_bus.publish("listening_finished", transcript="", confidence=0.0)
            return ""
