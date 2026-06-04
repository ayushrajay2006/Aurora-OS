import threading
import speech_recognition as sr
import pyttsx3
from config.logging import logger

class TextToSpeechManager:
    def __init__(self, rate: int = 180, voice_index: int = 1, volume: float = 1.0):
        self.rate = rate
        self.voice_index = voice_index
        self.volume = volume
        self._engine = None
        self._lock = threading.Lock()
        
    def _init_engine(self):
        if self._engine is None:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', self.rate)
                self._engine.setProperty('volume', self.volume)
                
                voices = self._engine.getProperty('voices')
                if 0 <= self.voice_index < len(voices):
                    self._engine.setProperty('voice', voices[self.voice_index].id)
                logger.info("pyttsx3 TextToSpeech initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize pyttsx3 TextToSpeech: {e}")
                
    def speak(self, text: str):
        """Speaks the specified text verbally (blocking)."""
        with self._lock:
            self._init_engine()
            if self._engine:
                try:
                    logger.debug(f"Speaking: '{text}'")
                    # Clean text to remove system markers or JSON code blocks if they exist
                    clean_text = self._clean_speech_text(text)
                    if clean_text:
                        self._engine.say(clean_text)
                        self._engine.runAndWait()
                except Exception as e:
                    logger.error(f"Error in pyttsx3 speak: {e}")

    def _clean_speech_text(self, text: str) -> str:
        """Strips out markdown syntax, urls, and JSON blocks for clean text-to-speech output."""
        # 1. Remove markdown code blocks (e.g. ```json ... ```)
        import re
        clean = re.sub(r"```[a-zA-Z]*\s*.*?\s*```", "", text, flags=re.DOTALL)
        
        # 2. Remove URLs
        clean = re.sub(r"https?://\S+", "", clean)
        
        # 3. Clean up formatting symbols like bold/italics
        clean = clean.replace("**", "").replace("*", "").replace("`", "").replace("_", "")
        
        return clean.strip()


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
