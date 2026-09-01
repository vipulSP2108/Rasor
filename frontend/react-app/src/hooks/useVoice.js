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

        // Reset the silence timer: 2.5 seconds of silence after speaking completes the input
        if (latestTranscript.trim()) {
          if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
          silenceTimeoutRef.current = setTimeout(() => {
            if (recognitionRef.current) {
              try { recognitionRef.current.stop(); } catch (e) {}
            }
            setIsListening(false);
          }, 2500);
        }
      };

      recognition.onerror = (event) => {
        if (event.error !== 'no-speech') {
          console.warn('Speech recognition notice:', event.error);
        }
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

  const stopListening = useCallback(() => {
    if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      setIsListening(false);
    }
  }, []);

  const startListening = useCallback(() => {
    // Don't listen if speech synthesis is currently speaking
    if (window.speechSynthesis && window.speechSynthesis.speaking) {
      return;
    }
    if (recognitionRef.current) {
      setTranscript(''); // Clear previous transcript
      if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
      
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e) {
        // Recognition may already be running
      }

      // Initial 8-second silence timeout: if no one speaks, automatically turn off listening
      silenceTimeoutRef.current = setTimeout(() => {
        stopListening();
      }, 8000);
    } else {
      console.warn("Speech Recognition not supported in this browser.");
    }
  }, [stopListening]);

  const speak = useCallback((text, voiceURI = null, onEnd = null) => {
    if (!window.speechSynthesis || !text) return;

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    // Strip emojis, markdown, and unwanted symbols so TTS doesn't speak emoji names aloud
    const cleanText = text
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/\*(.*?)\*/g, '$1')
      .replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1FA70}-\u{1FAFF}\u{1F900}-\u{1F9FF}\u{1F000}-\u{1F02F}\u{1F0A0}-\u{1F0FF}\u{1F100}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F1E6}-\u{1F1FF}]/gu, '')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/[#_~`]/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    if (!cleanText) {
      if (onEnd) onEnd();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(cleanText);
    
    if (voiceURI && voices.length > 0) {
      const selectedVoice = voices.find(v => v.voiceURI === voiceURI);
      if (selectedVoice) {
        utterance.voice = selectedVoice;
      }
    }
    
    utterance.onend = () => {
      if (onEnd) onEnd();
    };
    utterance.onerror = () => {
      if (onEnd) onEnd();
    };

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
