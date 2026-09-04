import { useState, useEffect, useCallback, useRef } from 'react';

const DEFAULT_VOICE_CHANNELS = {
  aiChat: true,          // AI Stylist recommendations and conversational responses
  inventoryOos: true,    // Pre-check out-of-stock and runner-up substitution alerts
  failoverRails: true,   // Multi-rail bank decline and failover guidance
  postRefund: true       // Post-payment collision and instant refund alerts
};

const loadVoiceChannels = () => {
  try {
    const raw = localStorage.getItem('rasor_voice_channels');
    return raw ? { ...DEFAULT_VOICE_CHANNELS, ...JSON.parse(raw) } : DEFAULT_VOICE_CHANNELS;
  } catch (e) {
    return DEFAULT_VOICE_CHANNELS;
  }
};

export function useVoice() {
  const [voices, setVoices] = useState([]);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [voiceChannels, setVoiceChannelsState] = useState(loadVoiceChannels);
  const recognitionRef = useRef(null);
  const silenceTimeoutRef = useRef(null);

  const setVoiceChannel = useCallback((channelKey, enabled) => {
    setVoiceChannelsState(prev => {
      const next = { ...prev, [channelKey]: !!enabled };
      try {
        localStorage.setItem('rasor_voice_channels', JSON.stringify(next));
      } catch (e) {}
      return next;
    });
  }, []);

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

  // Clean up timers and audio recognition on unmount
  useEffect(() => {
    return () => {
      if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
      if (recognitionRef.current) {
        try { recognitionRef.current.abort(); } catch (e) {}
        recognitionRef.current = null;
      }
    };
  }, []);

  const stopListening = useCallback(() => {
    if (silenceTimeoutRef.current) {
      clearTimeout(silenceTimeoutRef.current);
      silenceTimeoutRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      recognitionRef.current = null;
    }
    setIsListening(false);
  }, []);

  // Lazy on-demand Speech Recognition instantiation (Zero background CPU / audio threads when idle)
  const startListening = useCallback(() => {
    if (window.speechSynthesis && window.speechSynthesis.speaking) {
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Speech Recognition not supported in this browser.");
      return;
    }

    // Stop any existing instance
    if (recognitionRef.current) {
      try { recognitionRef.current.abort(); } catch (e) {}
      recognitionRef.current = null;
    }

    setTranscript('');
    if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
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

        if (latestTranscript.trim()) {
          // If speech is present, stop listening as soon as user takes a pause of 3 seconds
          if (silenceTimeoutRef.current) clearTimeout(silenceTimeoutRef.current);
          silenceTimeoutRef.current = setTimeout(() => {
            stopListening();
          }, 3000);
        }
      };

      recognition.onerror = (event) => {
        if (event.error !== 'no-speech') {
          console.warn('Speech recognition notice:', event.error);
        }
        stopListening();
      };

      recognition.onend = () => {
        stopListening();
      };

      recognitionRef.current = recognition;
      recognition.start();
      setIsListening(true);

      // Initial silence timeout: if nothing spoken after 10 seconds, stop listening
      silenceTimeoutRef.current = setTimeout(() => {
        stopListening();
      }, 10000);
    } catch (err) {
      console.warn('Failed to start speech recognition:', err);
      setIsListening(false);
    }
  }, [stopListening]);

  // Promise-based speak function: waits for utterance to finish cleanly
  const speakAsync = useCallback((text, options = {}) => {
    return new Promise((resolve) => {
      if (!window.speechSynthesis || !text) {
        resolve();
        return;
      }

      const opts = typeof options === 'string' ? { voiceURI: options } : (options || {});
      const { category = null, voiceURI = null, interrupt = false } = opts;

      // Check if specific voice category is disabled by the user
      const currentChannels = loadVoiceChannels();
      if (category && currentChannels[category] === false) {
        resolve();
        return;
      }

      if (interrupt) {
        window.speechSynthesis.cancel();
      }

      // Clean text of emojis, markdown, and urls
      const cleanText = text
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/[\u{1F300}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1FA70}-\u{1FAFF}\u{1F900}-\u{1F9FF}\u{1F000}-\u{1F02F}\u{1F0A0}-\u{1F0FF}\u{1F100}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F1E6}-\u{1F1FF}]/gu, '')
        .replace(/https?:\/\/\S+/g, '')
        .replace(/[#_~`]/g, '')
        .replace(/\s+/g, ' ')
        .trim();

      if (!cleanText) {
        resolve();
        return;
      }

      const utterance = new SpeechSynthesisUtterance(cleanText);
      if (voiceURI && voices.length > 0) {
        const selectedVoice = voices.find(v => v.voiceURI === voiceURI);
        if (selectedVoice) utterance.voice = selectedVoice;
      }

      let resolved = false;
      let safetyTimer = null;
      const safeResolve = () => {
        if (!resolved) {
          resolved = true;
          if (safetyTimer) clearTimeout(safetyTimer);
          resolve();
        }
      };

      utterance.onend = safeResolve;
      utterance.onerror = safeResolve;

      // Safety timeout: max 12s, estimated from string length
      const expectedDurationMs = Math.min(12000, Math.max(1600, cleanText.length * 70));
      safetyTimer = setTimeout(safeResolve, expectedDurationMs + 400);

      window.speechSynthesis.speak(utterance);
    });
  }, [voices]);

  const speak = useCallback((text, options = null, onEnd = null) => {
    let opts = {};
    if (typeof options === 'string') {
      opts = { voiceURI: options };
    } else if (options && typeof options === 'object') {
      opts = options;
    }
    if (onEnd) opts.onEnd = onEnd;

    speakAsync(text, opts).then(() => {
      if (opts.onEnd) opts.onEnd();
    });
  }, [speakAsync]);

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
    speakAsync,
    stopSpeaking,
    voiceChannels,
    setVoiceChannel,
    hasRecognitionSupport: !!window.SpeechRecognition || !!window.webkitSpeechRecognition,
    hasSynthesisSupport: !!window.speechSynthesis,
    resetTranscript: () => setTranscript('')
  };
}
