import { useState, useEffect, useCallback, useRef } from 'react';

export function useVoice() {
  const [voices, setVoices] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const recognitionRef = useRef(null);
  const silenceTimeoutRef = useRef(null);

  // Initialize Speech Synthesis Voices
  useEffect(() => {
    const loadVoices = () => {
      let sysVoices = window.speechSynthesis.getVoices();
      if (sysVoices.length > 0) {
        setVoices(sysVoices);
      }
    };
    
    loadVoices();
    if (window.speechSynthesis.onvoiceschanged !== undefined) {
      window.speechSynthesis.onvoiceschanged = loadVoices;
    }
  }, []);

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.continuous = true; // Keep listening until we stop it
      recognition.interimResults = true; // Give live feedback
      recognition.lang = 'en-US';

      recognition.onresult = (event) => {
        let finalTranscript = '';
        let interimTranscript = '';

        for (let i = 0; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript;
          } else {
            interimTranscript += event.results[i][0].transcript;
          }
        }
        
        const latestTranscript = (finalTranscript + interimTranscript).trim();
        setTranscript(latestTranscript);

        // Reset the 3 second silence timer if we got text
        if (latestTranscript.trim()) {
          if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
          silenceTimeoutRef.current = setTimeout(() => {
            recognition.stop();
          }, 3000);
        }
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error', event.error);
        if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
        setIsListening(false);
      };

      recognition.onend = () => {
        if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
    
    return () => {
      if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
    }
  }, []);

  const startListening = useCallback(() => {
    if (recognitionRef.current) {
      setTranscript(''); // Clear previous transcript
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e) {
        console.error("Could not start recognition:", e);
      }
    } else {
      console.warn("Speech Recognition not supported in this browser.");
    }
  }, []);

  const stopListening = useCallback(() => {
    if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  }, []);

  const speak = useCallback((text, voiceURI = null, onEnd = null) => {
    if (!window.speechSynthesis) return;

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    
    if (voiceURI && voices.length > 0) {
      const selectedVoice = voices.find(v => v.voiceURI === voiceURI);
      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
    }
    
    if (onEnd) {
      utterance.onend = onEnd;
    }

    window.speechSynthesis.speak(utterance);
  }, [voices]);

  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  return {
    voices,
    isListening,
    transcript,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    hasRecognitionSupport: !!window.SpeechRecognition || !!window.webkitSpeechRecognition,
    hasSynthesisSupport: !!window.speechSynthesis,
    resetTranscript: () => setTranscript('')
  };
}
