import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import './Dashboard.css';

function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [section, setSection] = useState('upload'); // sections: upload, interview, results
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [jobRole, setJobRole] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [focusAreas, setFocusAreas] = useState('');
  const [evaluationWeights, setEvaluationWeights] = useState({
    technical: 40,
    communication: 30,
    confidence: 30
  });
  const [resumeFile, setResumeFile] = useState(null);
  const [interviewId, setInterviewId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answerText, setAnswerText] = useState('');
  const [submittedAnswers, setSubmittedAnswers] = useState([]);
  const [finalScore, setFinalScore] = useState(null);
  const [showPermissionModal, setShowPermissionModal] = useState(false);
  const [permissionsGranted, setPermissionsGranted] = useState(false);
  const [deviceMonitorActive, setDeviceMonitorActive] = useState(false);
  const [connectedDevices, setConnectedDevices] = useState([]);
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [mediaStreams, setMediaStreams] = useState(null);
  const videoRef = useRef(null);
  const fullScreenRef = useRef(null);
  const deviceCheckIntervalRef = useRef(null);

  const [violations, setViolations] = useState(0);
  const [violationSummary, setViolationSummary] = useState([]);
  
  //  state variables for disable krne ka feature
    const [accessibilityEnabled, setAccessibilityEnabled] = useState(false);
    const [textToSpeechEnabled, setTextToSpeechEnabled] = useState(false);
    const [speechToTextEnabled, setSpeechToTextEnabled] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const speechSynthesisRef = useRef(null);
    const speechRecognitionRef = useRef(null);
    
  // Timer and follow-up question state
  const [interviewTimeRemaining, setInterviewTimeRemaining] = useState(1800); // 30 minutes in seconds
  const [questionTimeRemaining, setQuestionTimeRemaining] = useState(300); // 5 minutes in seconds
  const [questionStartTime, setQuestionStartTime] = useState(null);
  const [isFollowupQuestion, setIsFollowupQuestion] = useState(false);
  const [followupQuestion, setFollowupQuestion] = useState(null);
  const [parentQuestionId, setParentQuestionId] = useState(null);
  const interviewTimerRef = useRef(null);
  const questionTimerRef = useRef(null);
  
  // Personalized feedback state
  const [personalizedFeedback, setPersonalizedFeedback] = useState(null);
  const [loadingFeedback, setLoadingFeedback] = useState(false);
  
  // Multi-round interview state
  const [isMultiRound, setIsMultiRound] = useState(false);
  const [suggestedRounds, setSuggestedRounds] = useState([]);
  const [selectedRounds, setSelectedRounds] = useState([]);
  const [currentRound, setCurrentRound] = useState(null);
  const [allRounds, setAllRounds] = useState([]);
  const [roundProgress, setRoundProgress] = useState([]);
  const [loadingRounds, setLoadingRounds] = useState(false);
    
  const token = localStorage.getItem('token');

  
  // Required permissions for the interview
  const requiredPermissions = [
    { name: 'microphone', description: 'Required for voice recording during interview' },
    { name: 'camera', description: 'Required for video recording during interview' },
    { name: 'device access', description: 'Required to monitor external devices during interview' }
  ];

  const reportViolation = async (violationMessage) => {
  if (!interviewId) return; // Only report if an interview is active
  try {
    const response = await fetch('http://127.0.0.1:5000/api/report-violation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        interviewId,
        violation: violationMessage
      })
    });
    
    const data = await response.json();
    if (response.ok) {
      setViolations(data.violations);
      setViolationSummary(data.violation_summary.split('|').map(item => item.trim()));
    }
    
    console.log('Violation reported:', violationMessage);
  } catch (error) {
    console.error('Error reporting violation:', error);
  }
};

  // Timer helper functions
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const startInterviewTimer = () => {
    setInterviewTimeRemaining(1800);
    if (interviewTimerRef.current) {
      clearInterval(interviewTimerRef.current);
    }
    
    interviewTimerRef.current = setInterval(() => {
      setInterviewTimeRemaining(prev => {
        if (prev <= 1) {
          clearInterval(interviewTimerRef.current);
          handleTimeoutSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const startQuestionTimer = (timeLimit = 300) => {
    setQuestionTimeRemaining(timeLimit);
    setQuestionStartTime(Date.now());
    
    if (questionTimerRef.current) {
      clearInterval(questionTimerRef.current);
    }
    
    questionTimerRef.current = setInterval(() => {
      setQuestionTimeRemaining(prev => {
        if (prev <= 1) {
          clearInterval(questionTimerRef.current);
          handleTimeoutSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const stopAllTimers = () => {
    if (interviewTimerRef.current) {
      clearInterval(interviewTimerRef.current);
    }
    if (questionTimerRef.current) {
      clearInterval(questionTimerRef.current);
    }
  };

  const handleTimeoutSubmit = async () => {
    if (answerText.trim()) {
      await handleSubmitAnswer();
    } else {
      alert('Time is up! Moving to next question.');
      if (currentQuestionIndex + 1 < questions.length) {
        setCurrentQuestionIndex(currentQuestionIndex + 1);
        startQuestionTimer(300);
      } else {
        finishInterview();
      }
    }
  };


  useEffect(() => {
      const storedAccessibility = localStorage.getItem('accessibilityEnabled');
      if (storedAccessibility === 'true') {
        setAccessibilityEnabled(true);
        setTextToSpeechEnabled(localStorage.getItem('textToSpeechEnabled') === 'true');
        setSpeechToTextEnabled(localStorage.getItem('speechToTextEnabled') === 'true');
      }
    }, []);
    
    // Cleanup timers on unmount
    useEffect(() => {
      return () => {
        stopAllTimers();
      };
    }, []);
    
    
    // Handle role-based interview data from location state
    useEffect(() => {
      if (location.state && location.state.isRoleBased) {
        setInterviewId(location.state.interviewId);
        setQuestions(location.state.questions);
        setJobRole(location.state.role);
        setSection('interview');
        startInterviewTimer();
        startQuestionTimer(300);
        // Clear location state
        window.history.replaceState({}, document.title);
      }
    }, [location]);
    
    // Fetch personalized feedback when results section loads
    useEffect(() => {
      if (section === 'results' && interviewId) {
        fetchPersonalizedFeedback(interviewId);
      }
    }, [section, interviewId]);
    
    
    
    // Add this effect to handle text-to-speech for questions
    useEffect(() => {
      if (section === 'interview' && textToSpeechEnabled && currentQuestionIndex < questions.length) {
        // Read the question when it changes
        speakText(questions[currentQuestionIndex].question);
      }
      
      return () => {
        // Stop speaking if component unmounts or question changes
        stopSpeaking();
      };
    }, [currentQuestionIndex, section, textToSpeechEnabled, questions]);
    
    // Function to speak text using Web Speech API
    const speakText = (text) => {
      if (!textToSpeechEnabled || !text) return;
      
      // Cancel any ongoing speech
      stopSpeaking();
      
      // Create speech synthesis utterance
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.volume = 1.0;
      
      // Set voice to a more natural voice if available
      const voices = window.speechSynthesis.getVoices();
      const preferredVoice = voices.find(voice => 
        voice.name.includes('Google') || 
        voice.name.includes('Natural') || 
        voice.name.includes('Female')
      );
      
      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }
      
      // Add event listeners
      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = (event) => {
        console.error('Speech synthesis error:', event.error);
        setIsSpeaking(false);
      };
      
      // Store reference to current utterance
      speechSynthesisRef.current = utterance;
      
      // Speak the text
      window.speechSynthesis.speak(utterance);
    };
    
    // Function to stop speaking
    const stopSpeaking = () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        setIsSpeaking(false);
      }
    };
    
    // Function to start speech recognition
    const startSpeechRecognition = () => {
      if (!speechToTextEnabled) return;
      
      try {
        // Initialize speech recognition
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        
        recognition.onstart = () => {
          setIsListening(true);
        };
        
        recognition.onresult = (event) => {
          let interimTranscript = '';
          let finalTranscript = answerText;
          
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              finalTranscript += transcript + ' ';
            } else {
              interimTranscript += transcript;
            }
          }
          
          // Update the answer text with the recognized speech
          setAnswerText(finalTranscript);
        };
        
        recognition.onerror = (event) => {
          console.error('Speech recognition error:', event.error);
          setIsListening(false);
        };
        
        recognition.onend = () => {
          setIsListening(false);
        };
        
        // Store reference to current recognition
        speechRecognitionRef.current = recognition;
        
        // Start listening
        recognition.start();
        
      } catch (error) {
        console.error('Speech recognition not supported:', error);
        alert('Speech recognition is not supported in your browser.');
        setSpeechToTextEnabled(false);
      }
    };
    
    // Function to stop speech recognition
    const stopSpeechRecognition = () => {
      if (speechRecognitionRef.current) {
        speechRecognitionRef.current.stop();
        setIsListening(false);
      }
    };
    
    // Toggle accessibility settings
    const toggleAccessibility = () => {
      const newValue = !accessibilityEnabled;
      setAccessibilityEnabled(newValue);
      localStorage.setItem('accessibilityEnabled', newValue);
      
      if (!newValue) {
        // If turning off accessibility, stop any active speech or recognition
        stopSpeaking();
        stopSpeechRecognition();
      }
    };
    
    // Toggle text-to-speech
    const toggleTextToSpeech = () => {
      const newValue = !textToSpeechEnabled;
      setTextToSpeechEnabled(newValue);
      localStorage.setItem('textToSpeechEnabled', newValue);
      
      if (newValue && section === 'interview' && currentQuestionIndex < questions.length) {
        // If turning on and in interview, read current question
        speakText(questions[currentQuestionIndex].question);
      } else if (!newValue) {
        // If turning off, stop any active speech
        stopSpeaking();
      }
    };
    
    // Toggle speech-to-text
    const toggleSpeechToText = () => {
      const newValue = !speechToTextEnabled;
      setSpeechToTextEnabled(newValue);
      localStorage.setItem('speechToTextEnabled', newValue);
      
      if (!newValue && isListening) {
        // If turning off, stop any active recognition
        stopSpeechRecognition();
      }
    };
    
    // Handle microphone button click
    const handleMicrophoneClick = () => {
      if (isListening) {
        stopSpeechRecognition();
      } else {
        startSpeechRecognition();
      }
    };
    
    // Handle speaker button click
    const handleSpeakerClick = () => {
      if (isSpeaking) {
        stopSpeaking();
      } else if (currentQuestionIndex < questions.length) {
        speakText(questions[currentQuestionIndex].question);
      }
    };
  
    // Add this component for accessibility controls
    const AccessibilityControls = () => (
      <div className="accessibility-controls">
        <div className="accessibility-toggle">
          <input
            type="checkbox"
            id="accessibility-toggle"
            checked={accessibilityEnabled}
            onChange={toggleAccessibility}
          />
          <label htmlFor="accessibility-toggle">Enable Accessibility Features</label>
        </div>
        
        {accessibilityEnabled && (
          <div className="accessibility-options">
            <div className="accessibility-option">
              <input
                type="checkbox"
                id="text-to-speech-toggle"
                checked={textToSpeechEnabled}
                onChange={toggleTextToSpeech}
              />
              <label htmlFor="text-to-speech-toggle">Read Questions Aloud</label>
              {textToSpeechEnabled && (
                <button 
                  className={`btn btn-icon ${isSpeaking ? 'active' : ''}`}
                  onClick={handleSpeakerClick}
                  title={isSpeaking ? "Stop Speaking" : "Read Question"}
                >
                  {isSpeaking ? "🔇" : "🔊"}
                </button>
              )}
            </div>
            
            <div className="accessibility-option">
              <input
                type="checkbox"
                id="speech-to-text-toggle"
                checked={speechToTextEnabled}
                onChange={toggleSpeechToText}
              />
              <label htmlFor="speech-to-text-toggle">Answer by Speaking</label>
              {speechToTextEnabled && (
                <button 
                  className={`btn btn-icon ${isListening ? 'active' : ''}`}
                  onClick={handleMicrophoneClick}
                  title={isListening ? "Stop Listening" : "Start Listening"}
                >
                  {isListening ? "🛑" : "🎤"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    );

  useEffect(() => {
    // Check if permissions have been granted previously
    const storedPermissions = localStorage.getItem('interviewPermissions');
    if (storedPermissions === 'granted') {
      setPermissionsGranted(true);
    } else {
      // Show permission modal when component mounts if permissions not previously granted
      setShowPermissionModal(true);
    }
  }, []);

  // Handle security features when in interview mode
  useEffect(() => {
    if (section === 'interview') {
      // Enable security features
      enableSecurityFeatures();
      
      // Clean up security features when component unmounts or section changes
      return () => {
        disableSecurityFeatures();
      };
    }
  }, [section]);

  useEffect(() => {
    const handleFullScreenChange = () => {
      const isDocumentFullScreen = document.fullscreenElement !== null;
      setIsFullScreen(isDocumentFullScreen);
      
      // Enforce fullscreen only if the interview isn't finished
      if (!isDocumentFullScreen && section === 'interview' && currentQuestionIndex < questions.length) {
        alert('Fullscreen mode is required for the interview. Please click OK to re-enter fullscreen.');
        reportViolation('Exited fullscreen mode.');
        enterFullScreen();
      }
    };
  
    document.addEventListener('fullscreenchange', handleFullScreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullScreenChange);
    };
  }, [section, currentQuestionIndex, questions.length]);

  // Set up key event listeners
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (section === 'interview') {
        // Disable tab, alt+tab, windows key, ctrl+c, ctrl+v, alt+f4, etc.
        const forbiddenKeys = ['Tab', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F11', 'F12', 'Escape', 'Meta', 'ContextMenu'];
        
        if (forbiddenKeys.includes(e.key) || 
            (e.ctrlKey && ['c', 'v', 'x', 'Tab', 'w', 'a'].includes(e.key)) || 
            (e.altKey && ['Tab', 'F4'].includes(e.key))) {
          e.preventDefault();
          e.stopPropagation();
          reportViolation(`Forbidden key pressed: ${e.key}`);
          return false;
        }
      }
    };

    // Handle visibility change (tab switching)
    const handleVisibilityChange = () => {
      if (section === 'interview' && document.visibilityState === 'hidden') {
        reportViolation('Tab switching or exiting the frontend detected.');
        alert('Warning: Leaving the interview page may result in disqualification.');
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown, true);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [section]);

  // Handle right-click prevention
  useEffect(() => {
    const handleContextMenu = (e) => {
      if (section === 'interview') {
        e.preventDefault();
        reportViolation('Right-click detected.');
        return false;
      }
    };

    document.addEventListener('contextmenu', handleContextMenu);
    
    return () => {
      document.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [section]);



    // Device monitoring effect
    useEffect(() => {
      if (deviceMonitorActive && section === 'interview') {
        checkConnectedDevices();
        deviceCheckIntervalRef.current = setInterval(checkConnectedDevices, 2000);
      }
      return () => {
        if (deviceCheckIntervalRef.current) {
          clearInterval(deviceCheckIntervalRef.current);
          deviceCheckIntervalRef.current = null;
        }
      };
    }, [deviceMonitorActive, section]);
  
    // Function to check connected devices using the Web USB and WebHID APIs
    const checkConnectedDevices = async () => {
      try {
        // Store initial device state if first check
        if (connectedDevices.length === 0) {
          // Check USB devices
          if (navigator.usb) {
            const usbDevices = await navigator.usb.getDevices();
            const initialUsbDevices = usbDevices.map(device => ({
              id: device.serialNumber || `usb-${Math.random().toString(36).substring(7)}`,
              type: 'usb',
              name: device.productName || 'USB Device',
              allowed: true // Initially allow existing devices
            }));
            
            setConnectedDevices(prevDevices => [...prevDevices, ...initialUsbDevices]);
          }
          
          // Check for media devices (which could include HDMI capture devices)
          if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
            const mediaDevices = await navigator.mediaDevices.enumerateDevices();
            const videoInputs = mediaDevices.filter(device => device.kind === 'videoinput');
            
            // First videoinput is likely webcam, any others might be capture cards
            const captureDevices = videoInputs.slice(1).map(device => ({
              id: device.deviceId,
              type: 'hdmi',
              name: device.label || 'External Video Device',
              allowed: true // Initially allow existing devices
            }));
            
            setConnectedDevices(prevDevices => [...prevDevices, ...captureDevices]);
          }
          
          // Log initial device state
          console.log('Initial device state recorded');
        } else {
          // Check for newly connected devices
          if (navigator.usb) {
            // Try to access any new USB devices
            try {
              // This will prompt for any new USB device
              const newDevice = await navigator.usb.requestDevice({ filters: [] }).catch(() => null);
              
              if (newDevice) {
                // Detect if this is a new device
                const isNewDevice = !connectedDevices.some(dev => 
                  dev.id === (newDevice.serialNumber || newDevice.deviceId)
                );
                
                if (isNewDevice) {
                  alert('Warning: New USB device detected during the interview. This activity will be logged.');
                  reportViolation('New USB device connected during interview.');
                  
                  // Add to our tracked devices but mark as not allowed
                  setConnectedDevices(prevDevices => [
                    ...prevDevices, 
                    {
                      id: newDevice.serialNumber || `usb-${Math.random().toString(36).substring(7)}`,
                      type: 'usb',
                      name: newDevice.productName || 'USB Device',
                      allowed: false // Mark as not allowed since connected during interview
                    }
                  ]);
                }
              }
            } catch (error) {
              console.log('No new USB device selected');
            }
          }
          
          // Re-check media devices to detect new HDMI inputs
          if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
            const currentMediaDevices = await navigator.mediaDevices.enumerateDevices();
            const currentVideoInputs = currentMediaDevices.filter(device => device.kind === 'videoinput');
            
            // Compare with initial state to detect new devices
            const knownVideoDeviceIds = connectedDevices
              .filter(dev => dev.type === 'hdmi')
              .map(dev => dev.id);
            
            // Check for new video inputs
            const newVideoInputs = currentVideoInputs.filter(device => 
              !knownVideoDeviceIds.includes(device.deviceId)
            );
            
            if (newVideoInputs.length > 0) {
              alert('Warning: New video input device detected during the interview. This activity will be logged.');
              
              // Add new devices to tracked list
              const newDevicesToAdd = newVideoInputs.map(device => ({
                id: device.deviceId,
                type: 'hdmi',
                name: device.label || 'External Video Device',
                allowed: false // Mark as not allowed
              }));
              
              setConnectedDevices(prevDevices => [...prevDevices, ...newDevicesToAdd]);
            }
          }
        }
      } catch (error) {
        console.error('Error monitoring devices:', error);
      }
    };
  
    // Function to request device monitoring permissions
    const requestDeviceMonitoringPermissions = async () => {
      try {
        // Request USB device access
        if (navigator.usb) {
          try {
            // This will prompt the user for USB permission
            await navigator.usb.requestDevice({ filters: [] }).catch(() => {
              console.log('USB permission dialog dismissed');
            });
            console.log('USB monitoring enabled');
          } catch (error) {
            console.log('USB API not fully supported or permission denied');
          }
        }
        
        // Try to get device permissions for HDMI capture devices via media devices
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
          await navigator.mediaDevices.enumerateDevices();
          console.log('Media devices enumerated for monitoring');
        }
        
        // Set device monitoring as active
        setDeviceMonitorActive(true);
        
        return true;
      } catch (error) {
        console.error('Error setting up device monitoring:', error);
        return false;
      }
    };

  

  // Function to enable all security features
  const enableSecurityFeatures = async () => {
    // 1. Enable fullscreen
    await enterFullScreen();
    
    // 2. Start camera and microphone
    await startMediaStreams();

    if (permissionsGranted) {
      await requestDeviceMonitoringPermissions();
    }
    
    // 3. Disable clipboard (done via event listeners)
    // 4. Disable right-click (done via event listeners)
    // 5. Disable tab switching (done via event listeners)
  };

  // Function to disable all security features
  const disableSecurityFeatures = () => {
    // 1. Exit fullscreen
    exitFullScreen();
    
    // 2. Stop camera and microphone
    stopMediaStreams();

    if (deviceCheckIntervalRef.current) {
      clearInterval(deviceCheckIntervalRef.current);
      deviceCheckIntervalRef.current = null;
    }
    setDeviceMonitorActive(false);
    
    // 4. Stop any active text-to-speech or speech-to-text
    stopSpeaking();
    stopSpeechRecognition();
    
    // Event listeners are cleaned up in their respective useEffect hooks
  };

  // Function to enter fullscreen mode
  const enterFullScreen = async () => {
    try {
      if (fullScreenRef.current && !document.fullscreenElement) {
        await fullScreenRef.current.requestFullscreen();
        setIsFullScreen(true);
      }
    } catch (error) {
      console.error('Error entering fullscreen:', error);
      alert('Failed to enter fullscreen mode. This is required for the interview.');
    }
  };

  const exitFullScreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen()
        .then(() => setIsFullScreen(false))
        .catch(error => console.error('Error exiting fullscreen:', error));
    }
  };

  // Function to start media streams (camera and microphone)
  const startMediaStreams = async () => {
    try {
      if (!mediaStreams) {
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: true, 
          audio: true 
        });
        
        setMediaStreams(stream);
        
        // Connect stream to video element
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
      }
    } catch (error) {
      console.error('Error starting media streams:', error);
      alert('Failed to start camera and microphone. These are required for the interview.');
    }
  };

  // Function to stop media streams
  const stopMediaStreams = () => {
    if (mediaStreams) {
      mediaStreams.getTracks().forEach(track => track.stop());
      setMediaStreams(null);
      
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    }
  };

  const handleRequestPermissions = async () => {
    try {
      // Request microphone permission
      const micPermission = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Request camera permission
      const cameraPermission = await navigator.mediaDevices.getUserMedia({ video: true });

      const devicePermissionsGranted = await requestDeviceMonitoringPermissions();
      
      // If we get here, permissions were granted
      setPermissionsGranted(true);
      setShowPermissionModal(false);
      
      // Store permission status
      localStorage.setItem('interviewPermissions', 'granted');
      
      // Close media streams to avoid keeping them open
      const micTracks = micPermission.getTracks();
      const cameraTracks = cameraPermission.getTracks();
      
      [...micTracks, ...cameraTracks].forEach(track => track.stop());
      
    } catch (error) {
      console.error('Permission denied:', error);
      handlePermissionDenied();
    }
  };

  const handlePermissionDenied = () => {
    alert('This interview requires camera and microphone permissions. Without these permissions, you cannot proceed with the test.');
    handleLogout();
  };

  const handleCancelPermissions = () => {
    handlePermissionDenied();
  };
  
  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!permissionsGranted) {
      setShowPermissionModal(true);
      return;
    }
    
    // Validate evaluation weights total 100%
    const totalWeight = evaluationWeights.technical + evaluationWeights.communication + evaluationWeights.confidence;
    if (totalWeight !== 100) {
      alert('Evaluation weights must total 100%. Please adjust the sliders.');
      return;
    }
    
    if(!resumeFile || !jobRole) {
      alert('Please select a resume file and job role');
      return;
    }
    const formData = new FormData();
    formData.append('resume', resumeFile);
    formData.append('jobRole', jobRole);
    formData.append('jobDescription', jobDescription);
    formData.append('focusAreas', focusAreas);
    formData.append('evaluationWeights', JSON.stringify({
      technical_weight: evaluationWeights.technical / 100,
      communication_weight: evaluationWeights.communication / 100,
      confidence_weight: evaluationWeights.confidence / 100
    }));
    try {
      const response = await fetch('http://127.0.0.1:5000/api/upload-resume', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      const data = await response.json();
      if(response.ok) {
        setInterviewId(data.interview_id);
        setQuestions(data.questions);
        setSection('interview');
        startInterviewTimer();
        startQuestionTimer(300);
      } else {
        alert('Error uploading resume: ' + data.error);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('An error occurred during resume upload');
    }
  };


  const handleSubmitAnswer = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    // Stop any active speech recognition before submitting
    if (isListening) {
      stopSpeechRecognition();
    }
    
    if(answerText.trim() === '') {
      alert('Please provide an answer');
      if (textToSpeechEnabled) {
        speakText('Please provide an answer');
      }
      setIsSubmitting(false);
      return;
    }
    
    const currentQuestion = isFollowupQuestion ? followupQuestion : questions[currentQuestionIndex];
    const questionId = isFollowupQuestion ? followupQuestion.questionId : (currentQuestion.id || currentQuestionIndex + 1);
    const timeSpent = questionStartTime ? Math.floor((Date.now() - questionStartTime) / 1000) : 0;
    
    try {
      const response = await fetch('http://127.0.0.1:5000/api/submit-answer-enhanced', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          interviewId: interviewId,
          questionId: questionId,
          answer: answerText,
          timeSpent: timeSpent
        })
      });
      
      const data = await response.json();
      
      if(response.ok) {
        setSubmittedAnswers(prev => [
          ...prev,
          { 
            question: currentQuestion.question || followupQuestion.question, 
            answer: answerText, 
            score: data.evaluation.overall_score,
            evaluation: data.evaluation,
            isFollowup: isFollowupQuestion
          }
        ]);
        
        setAnswerText('');
        
        // Check if there's a follow-up question
        if (data.followup && !isFollowupQuestion) {
          setFollowupQuestion({
            question: data.followup.question,
            questionId: data.followup.questionId,
            timeLimit: data.followup.timeLimit
          });
          setParentQuestionId(questionId);
          setIsFollowupQuestion(true);
          startQuestionTimer(data.followup.timeLimit);
          
          if (textToSpeechEnabled) {
            speakText('Follow-up question: ' + data.followup.question);
          }
        } else {
          // No follow-up or just finished follow-up
          setIsFollowupQuestion(false);
          setFollowupQuestion(null);
          setParentQuestionId(null);
          
          if(currentQuestionIndex + 1 < questions.length) {
            setCurrentQuestionIndex(currentQuestionIndex + 1);
            startQuestionTimer(300);
            
            if (textToSpeechEnabled) {
              speakText('Answer submitted successfully. Moving to next question.');
            }
          } else {
            stopAllTimers();
            if (textToSpeechEnabled) {
              speakText('All questions answered!');
            }
            finishInterview();
          }
        }
      } else {
        const errorMessage = 'Error submitting answer: ' + data.error;
        alert(errorMessage);
        if (textToSpeechEnabled) {
          speakText(errorMessage);
        }
      }
    } catch (error) {
      console.error('Submit answer error:', error);
      const errorMessage = 'An error occurred while submitting your answer';
      alert(errorMessage);
      if (textToSpeechEnabled) {
        speakText(errorMessage);
      }
    }
    setIsSubmitting(false);
  };
  
  
  const finishInterview = async () => {
  try {
    // Use the new complete-interview endpoint for comprehensive evaluation
    const response = await fetch('http://127.0.0.1:5000/api/complete-interview', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ interviewId })
    });
    const data = await response.json();
    if(response.ok) {
      // Navigate to results page instead of showing inline results
      navigate(`/interview-results/${interviewId}`);
    } else {
      alert('Error completing interview: ' + data.error);
    }
  } catch (error) {
    console.error('Finish interview error:', error);
    alert('An error occurred while completing the interview');
  }
};

  const fetchPersonalizedFeedback = async (interviewIdParam) => {
    setLoadingFeedback(true);
    try {
      const response = await fetch(`http://127.0.0.1:5000/api/personalized-feedback/${interviewIdParam}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      if (response.ok) {
        setPersonalizedFeedback(data);
      } else {
        console.error('Error fetching feedback:', data.error);
      }
    } catch (error) {
      console.error('Fetch feedback error:', error);
    } finally {
      setLoadingFeedback(false);
    }
  };
  
  // Multi-round interview functions
  const fetchRoundSuggestions = async () => {
    setLoadingRounds(true);
    try {
      const response = await fetch('http://127.0.0.1:5000/api/suggest-rounds', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          jobRole: jobRole,
          jobDescription: jobDescription
        })
      });
      const data = await response.json();
      if (response.ok) {
        setSuggestedRounds(data.suggested_rounds);
        setSection('round-selection');
      } else {
        alert('Error fetching round suggestions: ' + data.error);
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to fetch round suggestions');
    } finally {
      setLoadingRounds(false);
    }
  };

  const startMultiRoundInterview = async () => {
    if (selectedRounds.length === 0) {
      alert('Please select at least one round');
      return;
    }

    try {
      const response = await fetch('http://127.0.0.1:5000/api/start-multi-round-interview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          jobRole: jobRole,
          jobDescription: jobDescription,
          selectedRounds: selectedRounds
        })
      });
      const data = await response.json();
      if (response.ok) {
        setInterviewId(data.interview_id);
        setAllRounds(selectedRounds.map((r, idx) => ({
          ...r,
          id: data.round_ids[idx],
          status: 'pending'
        })));
        setIsMultiRound(true);
        if (data.round_ids.length > 0) {
          await startRound(data.round_ids[0]);
        }
      } else {
        alert('Error starting interview: ' + data.error);
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to start interview');
    }
  };

  const startRound = async (roundId) => {
    try {
      const response = await fetch(`http://127.0.0.1:5000/api/start-round/${roundId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      if (response.ok) {
        setCurrentRound({
          id: roundId,
          name: data.round_name,
          type: data.round_type
        });
        setQuestions(data.questions);
        setCurrentQuestionIndex(0);
        setAnswerText('');
        setSubmittedAnswers([]);
        setSection('interview');
        startInterviewTimer();
        startQuestionTimer(300);
      } else {
        alert('Error starting round: ' + data.error);
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to start round');
    }
  };

  const completeCurrentRound = async () => {
    if (!currentRound) return;

    try {
      const response = await fetch(`http://127.0.0.1:5000/api/complete-round/${currentRound.id}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      if (response.ok) {
        setAllRounds(prev => prev.map(r =>
          r.id === currentRound.id
            ? { ...r, status: 'completed', score: data.round_score }
            : r
        ));

        if (data.next_round) {
          alert(`Round completed! Score: ${data.round_score.toFixed(1)}/100\n\nStarting next round: ${data.next_round.name}`);
          await startRound(data.next_round.id);
        } else {
          stopAllTimers();
          setSection('results');
          setFinalScore(data.round_score);
        }
      } else {
        alert('Error completing round: ' + data.error);
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Failed to complete round');
    }
  };
  
  const toggleRoundSelection = (round) => {
    setSelectedRounds(prev => {
      const exists = prev.find(r => r.round_type === round.round_type);
      if (exists) {
        return prev.filter(r => r.round_type !== round.round_type);
      } else {
        return [...prev, round];
      }
    });
  };
  
  const handleNewInterview = () => {
    setSection('upload');
    setJobRole('');
    setResumeFile(null);
    setInterviewId(null);
    setQuestions([]);
    setCurrentQuestionIndex(0);
    setAnswerText('');
    setSubmittedAnswers([]);
    setFinalScore(null);
    setConnectedDevices([]); // Reset connected devices tracking
  };
  
  const handleLogout = () => {
    // Make sure to clean up security features before logging out
    disableSecurityFeatures();
    
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('interviewPermissions');
    window.location.href = '/login';
  };

  // Permission Modal Component
  const PermissionModal = () => (
    <div className="modal-overlay">
      <div className="modal-content">
        <h2>Permissions Required</h2>
        <p>This interview requires the following permissions to proceed:</p>
        <ul>
          {requiredPermissions.map((permission, index) => (
            <li key={index}>
              <strong>{permission.name}</strong>: {permission.description}
            </li>
          ))}
        </ul>
        <p>Without these permissions, you will not be able to take the test.</p>
        <div className="modal-buttons">
          <button className="btn btn-secondary" onClick={handleCancelPermissions}>Cancel</button>
          <button className="btn btn-primary" onClick={handleRequestPermissions}>Grant Permissions</button>
        </div>
      </div>
    </div>
  );


  // Device Status Component
  const DeviceStatusIndicator = () => {
    if (!deviceMonitorActive || section !== 'interview') return null;
    
    const unauthorizedDevices = connectedDevices.filter(device => !device.allowed);
    const hasUnauthorizedDevices = unauthorizedDevices.length > 0;
    
    return (
      <div className={`device-status ${hasUnauthorizedDevices ? 'warning' : 'secure'}`}>
        <div className="status-indicator">
          <span className={`status-dot ${hasUnauthorizedDevices ? 'red' : 'green'}`}></span>
          <span>{hasUnauthorizedDevices ? 'Unauthorized Device Detected' : 'Device Ports Secured'}</span>
        </div>
        {hasUnauthorizedDevices && (
          <div className="unauthorized-devices">
            <p>The following unauthorized devices were detected:</p>
            <ul>
              {unauthorizedDevices.map((device, index) => (
                <li key={index}>
                  {device.name} ({device.type.toUpperCase()})
                </li>
              ))}
            </ul>
            <p className="warning-text">
              This activity has been logged and may affect your interview results.
            </p>
          </div>
        )}
      </div>
    );
  };
  

 // Security Notice Component
 const SecurityNotice = () => (
  <div className="security-notice">
    <h4>Security Notice</h4>
    <p>This interview has the following security measures in place:</p>
    <ul>
      <li>Fullscreen mode is required</li>
      <li>Camera and microphone will be active</li>
      <li>Right-clicking is disabled</li>
      <li>Tab switching is disabled</li>
      <li>Copying and pasting is disabled</li>
      <li>USB and HDMI port monitoring is active</li>
      <li>New devices connected during interview will be flagged</li>
    </ul>
    <p>Attempting to bypass these measures may result in disqualification.</p>
  </div>
);
  
  return (
    <div className="dashboard-container" ref={fullScreenRef}>
      <Sidebar onLogout={handleLogout} />
      <div className="content">
        <div className="user-info">
          <span>Welcome, {JSON.parse(localStorage.getItem('user')).name}</span>
        </div>

        {/* Permission Modal */}
        {showPermissionModal && <PermissionModal />}
        
        {section === 'upload' && (
          <div className="upload-container">
            <h2>Start a New Interview</h2>
            <p>Upload your resume and select the job role you're interested in.</p>
            
            {/* New Role-Based Interview Button */}
            <div className="interview-options">
              <button 
                className="btn btn-role-based"
                onClick={() => navigate('/role-selection')}
                style={{
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: 'white',
                  padding: '1.5rem 2rem',
                  fontSize: '1.1rem',
                  fontWeight: '600',
                  border: 'none',
                  borderRadius: '12px',
                  cursor: 'pointer',
                  marginBottom: '2rem',
                  width: '100%',
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
                  transition: 'all 0.3s ease'
                }}
                onMouseOver={(e) => e.target.style.transform = 'translateY(-2px)'}
                onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
              >
                🎯 Start Role-Based AI Interview (Recommended)
              </button>
              
              <button 
                className="btn btn-multi-round"
                onClick={fetchRoundSuggestions}
                style={{
                  background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                  color: 'white',
                  padding: '1.5rem 2rem',
                  fontSize: '1.1rem',
                  fontWeight: '600',
                  border: 'none',
                  borderRadius: '12px',
                  cursor: 'pointer',
                  marginBottom: '2rem',
                  width: '100%',
                  boxShadow: '0 4px 12px rgba(245, 87, 108, 0.4)',
                  transition: 'all 0.3s ease'
                }}
                onMouseOver={(e) => e.target.style.transform = 'translateY(-2px)'}
                onMouseOut={(e) => e.target.style.transform = 'translateY(0)'}
                disabled={!jobRole || loadingRounds}
              >
                {loadingRounds ? '🔄 Loading Rounds...' : '🎭 Start Multi-Round Interview (HR + Technical + More)'}
              </button>
              
              <div style={{ textAlign: 'center', margin: '1rem 0', color: '#999' }}>OR</div>
            </div>
            
            <SecurityNotice />
            <form onSubmit={handleUploadSubmit}>
              <div className="form-group">
                <label>Job Role</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="Enter job role (e.g., Software Engineer, Data Analyst)"
                  value={jobRole}
                  onChange={(e) => setJobRole(e.target.value)}
                  required
                />
              </div>
              
              <div className="form-group">
                <label>Job Description (Optional)</label>
                <textarea
                  className="form-control"
                  placeholder="Enter job description, responsibilities, or requirements..."
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  rows="3"
                  style={{ resize: 'vertical' }}
                />
              </div>
              
              <div className="form-group">
                <label>Focus Areas (Optional)</label>
                <input
                  type="text"
                  className="form-control"
                  placeholder="e.g., algorithms, system design, behavioral questions"
                  value={focusAreas}
                  onChange={(e) => setFocusAreas(e.target.value)}
                />
                <small style={{ color: '#666', fontSize: '0.85rem' }}>
                  Specify topics or question types to emphasize (comma-separated)
                </small>
              </div>
              
              <div className="form-group">
                <label>Evaluation Focus</label>
                <div style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '8px' }}>
                  <div style={{ marginBottom: '0.8rem' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                      <span>Technical Knowledge: {evaluationWeights.technical}%</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={evaluationWeights.technical}
                      onChange={(e) => setEvaluationWeights({...evaluationWeights, technical: parseInt(e.target.value)})}
                      style={{ width: '100%' }}
                    />
                  </div>
                  
                  <div style={{ marginBottom: '0.8rem' }}>
                    <label style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                      <span>Communication & Grammar: {evaluationWeights.communication}%</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={evaluationWeights.communication}
                      onChange={(e) => setEvaluationWeights({...evaluationWeights, communication: parseInt(e.target.value)})}
                      style={{ width: '100%' }}
                    />
                  </div>
                  
                  <div>
                    <label style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                      <span>Confidence & Speech: {evaluationWeights.confidence}%</span>
                    </label>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={evaluationWeights.confidence}
                      onChange={(e) => setEvaluationWeights({...evaluationWeights, confidence: parseInt(e.target.value)})}
                      style={{ width: '100%' }}
                    />
                  </div>
                  
                  <div style={{ marginTop: '0.8rem', fontSize: '0.85rem', color: '#666' }}>
                    Total: {evaluationWeights.technical + evaluationWeights.communication + evaluationWeights.confidence}%
                    {(evaluationWeights.technical + evaluationWeights.communication + evaluationWeights.confidence) !== 100 && (
                      <span style={{ color: '#f59e0b', marginLeft: '0.5rem' }}>
                        ⚠️ Should total 100%
                      </span>
                    )}
                  </div>
                </div>
              </div>
              
              <div className="form-group">
              <label>Upload Resume (PDF)</label>
                <input 
                  type="file" 
                  className="form-control" 
                  accept=".pdf"
                  onChange={(e) => setResumeFile(e.target.files[0])}
                  required
                />
              </div>
              <button type="submit" className="btn btn-primary">Start Interview</button>
            </form>
          </div>
        )}
        
        {/* Round Selection Section */}
        {section === 'round-selection' && (
          <div className="round-selection-container" style={{ padding: '2rem', maxWidth: '900px', margin: '0 auto' }}>
            <h2 style={{ color: '#2c3e50', marginBottom: '1rem' }}>📋 Select Interview Rounds</h2>
            <p style={{ color: '#7f8c8d', marginBottom: '2rem' }}>Choose the rounds you'd like to take for your <strong>{jobRole}</strong> interview</p>
            
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '2rem' }}>
              {suggestedRounds.map(round => (
                <div 
                  key={round.round_type}
                  onClick={() => toggleRoundSelection(round)}
                  style={{
                    border: selectedRounds.find(r => r.round_type === round.round_type) ? '3px solid #667eea' : '2px solid #e0e0e0',
                    borderRadius: '12px',
                    padding: '1.5rem',
                    cursor: 'pointer',
                    background: selectedRounds.find(r => r.round_type === round.round_type) ? '#f0f4ff' : 'white',
                    transition: 'all 0.3s ease',
                    boxShadow: selectedRounds.find(r => r.round_type === round.round_type) ? '0 4px 12px rgba(102, 126, 234, 0.2)' : '0 2px 4px rgba(0,0,0,0.1)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'start', gap: '1rem' }}>
                    <input 
                      type="checkbox"
                      checked={selectedRounds.find(r => r.round_type === round.round_type) ? true : false}
                      onChange={() => {}}
                      style={{ marginTop: '0.25rem', width: '20px', height: '20px', cursor: 'pointer' }}
                    />
                    <div style={{ flex: 1 }}>
                      <h3 style={{ margin: '0 0 0.5rem 0', color: '#2c3e50' }}>{round.round_name}</h3>
                      <p style={{ margin: '0 0 1rem 0', color: '#555' }}>{round.description}</p>
                      <div style={{ display: 'flex', gap: '2rem', fontSize: '0.9rem', color: '#7f8c8d' }}>
                        <span>⏱️ {round.duration_minutes} minutes</span>
                        <span>❓ {round.question_count} questions</span>
                      </div>
                      {round.focus_areas && round.focus_areas.length > 0 && (
                        <div style={{ marginTop: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                          {round.focus_areas.map((area, idx) => (
                            <span key={idx} style={{ background: '#e8f4f8', color: '#2c7a9b', padding: '0.25rem 0.75rem', borderRadius: '12px', fontSize: '0.85rem' }}>
                              {area}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <div style={{ display: 'flex', gap: '1rem' }}>
              <button 
                onClick={() => setSection('upload')}
                style={{ padding: '1rem 2rem', background: '#e0e0e0', border: 'none', borderRadius: '8px', cursor: 'pointer', fontSize: '1rem' }}
              >
                ← Back
              </button>
              <button 
                onClick={startMultiRoundInterview}
                disabled={selectedRounds.length === 0}
                style={{
                  flex: 1,
                  padding: '1rem 2rem',
                  background: selectedRounds.length > 0 ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : '#ccc',
                  color: 'white',
                  border: 'none',
                  borderRadius: '8px',
                  cursor: selectedRounds.length > 0 ? 'pointer' : 'not-allowed',
                  fontSize: '1rem',
                  fontWeight: '600'
                }}
              >
                Start Interview ({selectedRounds.length} round{selectedRounds.length !== 1 ? 's' : ''} selected)
              </button>
            </div>
          </div>
        )}
        
        {section === 'interview' && (
          <div className="interview-container">
            <h2>Technical Interview</h2>
            <p>Answer the following questions to the best of your ability.</p>

            {/* Round Progress Tracker */}
            {isMultiRound && allRounds.length > 0 && (
              <div style={{ background: '#f8f9fa', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '2px solid #e0e0e0' }}>
                <h4 style={{ margin: '0 0 1rem 0', color: '#2c3e50' }}>Interview Progress</h4>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  {allRounds.map((round, idx) => (
                    <div key={round.id} style={{
                      padding: '0.5rem 1rem',
                      borderRadius: '20px',
                      background: round.status === 'completed' ? '#d4edda' : round.id === currentRound?.id ? '#fff3cd' : '#e9ecef',
                      border: `2px solid ${round.status === 'completed' ? '#28a745' : round.id === currentRound?.id ? '#ffc107' : '#dee2e6'}`,
                      fontSize: '0.9rem',
                      fontWeight: '500'
                    }}>
                      {idx + 1}. {round.round_name}
                      {round.status === 'completed' && ` ✓ ${round.score?.toFixed(0)}%`}
                      {round.id === currentRound?.id && ' (Current)'}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Current Round Header */}
            {isMultiRound && currentRound && (
              <div style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0 }}>{currentRound.name}</h3>
                <p style={{ margin: '0.5rem 0 0 0', opacity: 0.9, fontSize: '0.9rem' }}>
                  Round Type: {currentRound.type.toUpperCase()}
                </p>
              </div>
            )}

            {/* Timer Display */}
            <div style={{
              position: 'fixed',
              top: '20px',
              right: '20px',
              background: 'white',
              padding: '15px',
              borderRadius: '10px',
              boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
              zIndex: 1000
            }}>
              <div style={{ marginBottom: '10px' }}>
                <strong>Interview Time:</strong>
                <div style={{ 
                  fontSize: '24px', 
                  color: interviewTimeRemaining < 300 ? 'red' : '#333',
                  fontWeight: 'bold'
                }}>
                  {formatTime(interviewTimeRemaining)}
                </div>
              </div>
              <div>
                <strong>Question Time:</strong>
                <div style={{ 
                  fontSize: '20px', 
                  color: questionTimeRemaining < 60 ? 'red' : '#666',
                  fontWeight: 'bold'
                }}>
                  {formatTime(questionTimeRemaining)}
                </div>
              </div>
              {questionTimeRemaining < 60 && (
                <div style={{ color: 'red', fontSize: '12px', marginTop: '5px' }}>
                  ⚠️ Less than 1 minute remaining!
                </div>
              )}
            </div>
                
              {/* Accessibility Controls */}
              <AccessibilityControls />
              
              {/* Device status indicator */}
              <DeviceStatusIndicator />
            
            {/* Camera feed display */}
            <div className="camera-container">
              <video 
                ref={videoRef} 
                autoPlay 
                muted 
                className="camera-feed"
              ></video>
              <div className="recording-indicator">
                <span className="recording-dot"></span>
                <span>Recording</span>
              </div>
            </div>
            
            <div className="progress-bar-container">
              <div className="progress-bar" style={{ width: `${((currentQuestionIndex) / questions.length) * 100}%` }}></div>
            </div>        
            {/* Warning message if not in fullscreen */}
            {!isFullScreen && section === 'interview' && (
              <div className="warning-message">
                <p>Fullscreen mode is required. Please click the button below to enter fullscreen.</p>
                <button className="btn btn-warning" onClick={enterFullScreen}>Enter Fullscreen</button>
              </div>
            )}
            
            {currentQuestionIndex < questions.length ? (
              <div className="question-container">
                    {isFollowupQuestion && (
                      <div style={{
                        background: '#fff3cd',
                        padding: '10px',
                        borderRadius: '5px',
                        marginBottom: '10px',
                        border: '1px solid #ffc107'
                      }}>
                        <strong>📌 Follow-up Question</strong>
                        <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                          Time limit: {formatTime(questionTimeRemaining)}
                        </div>
                      </div>
                    )}
                    <h4>
                      {isFollowupQuestion 
                        ? `Follow-up: ${followupQuestion.question}`
                        : `Q${currentQuestionIndex + 1}: ${questions[currentQuestionIndex].question}`
                      }
                    </h4>
                     {/* Voice controls for accessibility */}
            {accessibilityEnabled && (
              <div className="voice-controls">
                {textToSpeechEnabled && (
                  <button 
                    className={`btn btn-voice ${isSpeaking ? 'speaking' : ''}`}
                    onClick={handleSpeakerClick}
                    aria-label={isSpeaking ? "Stop reading question" : "Read question aloud"}
                  >
                    {isSpeaking ? "Stop Reading" : "Read Question"} {isSpeaking && <span className="speaking-indicator">Speaking...</span>}
                  </button>
                )}
              </div>
            )}
            
            <label htmlFor="answer-input" className="sr-only">Your answer</label>
            <textarea 
              id="answer-input"
              className="form-control"
              rows="6"
              placeholder="Type your answer here... or use voice input if enabled"
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              onPaste={(e) => {
                e.preventDefault();
                alert('Pasting is not allowed during the interview.');
                return false;
              }}
              onCopy={(e) => {
                e.preventDefault();
                alert('Copying is not allowed during the interview.');
                return false;
              }}
              onCut={(e) => {
                e.preventDefault();
                alert('Cutting is not allowed during the interview.');
                return false;
              }}
              aria-labelledby="current-question"
            ></textarea>
            
            {/* Speech-to-text control */}
            {accessibilityEnabled && speechToTextEnabled && (
              <button 
                className={`btn btn-voice-input ${isListening ? 'listening' : ''}`}
                onClick={handleMicrophoneClick}
                aria-label={isListening ? "Stop voice input" : "Start voice input"}
              >
                {isListening ? "Stop Voice Input" : "Start Voice Input"} {isListening && <span className="listening-indicator">Listening...</span>}
              </button>
            )}
            
            <button className="btn btn-primary" onClick={handleSubmitAnswer}>Submit Answer</button>
          </div>
        ) : (
          <div>
            <h4>All questions answered!</h4>
          </div>
        )}
        
        <div className="submitted-answers">
      {submittedAnswers.map((item, index) => (
        <div key={index} className="answer-summary">
          <h5>Q{index + 1}: {item.question}</h5>
          <p><strong>Your Answer:</strong> {item.answer}</p>
          <p><strong>Score:</strong> {item.score}</p>
        </div>
      ))}
    </div>
  </div>
)}
        
        {section === 'results' && (
          <div className="results-container">
  <h2>Interview Results</h2>
  <div className="card-score">
    <div>Your Score</div>
    <div className="score-value">{finalScore !== null ? finalScore.toFixed(1) : 0}</div>
    <div>out of 100</div>
  </div>
  
  {/* Violations Summary Card */}
  <div className="violations-card">
    <h4>Security Violations</h4>
    <div className="violations-count">
      <div>Total Violations</div>
      <div className="violation-value">{violations}</div>
    </div>
    
    {violations > 0 && (
      <div className="violations-detail">
        <h5>Violation Details:</h5>
        <ul className="violations-list">
          {violationSummary.filter(v => v).map((violation, index) => (
            <li key={index}>{violation}</li>
          ))}
        </ul>
      </div>
    )}
    
    {violations === 0 && (
      <div className="no-violations">
        <p>Great job! No security violations were detected during your interview.</p>
      </div>
    )}
  </div>
  
  <div className="question-summary">
    <h4>Question Summary</h4>
    {submittedAnswers.map((item, index) => (
      <div key={index} className="answer-summary">
        <h5>Q{index + 1}: {item.question}</h5>
        <p><strong>Your Answer:</strong> {item.answer}</p>
        <p><strong>Score:</strong> {item.score}</p>
      </div>
    ))}
  </div>
  
  {/* Personalized Feedback & Learning Path */}
  {personalizedFeedback && (
    <div style={{ marginTop: '30px', padding: '20px', background: '#f8f9fa', borderRadius: '10px' }}>
      <h3 style={{ color: '#2c3e50', marginBottom: '20px' }}>📚 Your Personalized Learning Path</h3>
      
      <div style={{ marginBottom: '25px' }}>
        <h4 style={{ color: '#27ae60' }}>✅ Your Strengths</h4>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {personalizedFeedback.strengths?.map((strength, idx) => (
            <li key={idx} style={{ padding: '10px', marginBottom: '8px', background: '#d4edda', borderLeft: '4px solid #28a745', borderRadius: '4px' }}>{strength}</li>
          ))}
        </ul>
      </div>
      
      <div style={{ marginBottom: '25px' }}>
        <h4 style={{ color: '#e74c3c' }}>🎯 Areas for Improvement</h4>
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {personalizedFeedback.weaknesses?.map((weakness, idx) => (
            <li key={idx} style={{ padding: '10px', marginBottom: '8px', background: '#f8d7da', borderLeft: '4px solid #dc3545', borderRadius: '4px' }}>{weakness}</li>
          ))}
        </ul>
      </div>
      
      {personalizedFeedback.roadmap && (
        <div style={{ marginBottom: '25px' }}>
          <h4 style={{ color: '#3498db' }}>🗺️ Your Improvement Roadmap</h4>
          {personalizedFeedback.roadmap.immediate && (
            <div style={{ marginBottom: '20px' }}>
              <h5 style={{ color: '#e74c3c', background: '#fff3cd', padding: '8px 12px', borderRadius: '5px', display: 'inline-block' }}>🔥 Immediate (1-2 weeks)</h5>
              <ul style={{ marginTop: '10px' }}>{personalizedFeedback.roadmap.immediate.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
            </div>
          )}
          {personalizedFeedback.roadmap.short_term && (
            <div style={{ marginBottom: '20px' }}>
              <h5 style={{ color: '#f39c12', background: '#d1ecf1', padding: '8px 12px', borderRadius: '5px', display: 'inline-block' }}>📈 Short-term (1-3 months)</h5>
              <ul style={{ marginTop: '10px' }}>{personalizedFeedback.roadmap.short_term.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
            </div>
          )}
          {personalizedFeedback.roadmap.long_term && (
            <div style={{ marginBottom: '20px' }}>
              <h5 style={{ color: '#27ae60', background: '#d4edda', padding: '8px 12px', borderRadius: '5px', display: 'inline-block' }}>🚀 Long-term (3-6 months)</h5>
              <ul style={{ marginTop: '10px' }}>{personalizedFeedback.roadmap.long_term.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
            </div>
          )}
        </div>
      )}
      
      {personalizedFeedback.resources && personalizedFeedback.resources.length > 0 && (
        <div>
          <h4 style={{ color: '#8e44ad' }}>📖 Recommended Resources</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '15px' }}>
            {personalizedFeedback.resources.map((resource, idx) => (
              <div key={idx} style={{ background: 'white', padding: '15px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)', border: `2px solid ${resource.priority === 'high' ? '#e74c3c' : resource.priority === 'medium' ? '#f39c12' : '#95a5a6'}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <h5 style={{ margin: 0 }}>{resource.title}</h5>
                  <span style={{ fontSize: '11px', padding: '3px 8px', borderRadius: '12px', background: resource.priority === 'high' ? '#e74c3c' : resource.priority === 'medium' ? '#f39c12' : '#95a5a6', color: 'white' }}>{resource.priority?.toUpperCase()}</span>
                </div>
                <p style={{ fontSize: '12px', color: '#7f8c8d', margin: '5px 0' }}>{resource.type}</p>
                <p style={{ fontSize: '14px', marginBottom: '10px' }}>{resource.description}</p>
                {resource.url && resource.url !== 'N/A' && <a href={resource.url} target="_blank" rel="noopener noreferrer" style={{ color: '#3498db', textDecoration: 'none' }}>Learn More →</a>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )}
  
  {loadingFeedback && <div style={{ textAlign: 'center', padding: '20px', color: '#7f8c8d' }}><p>Generating your personalized learning path...</p></div>}
  
  <button className="btn btn-primary" onClick={handleNewInterview}>Start New Interview</button>
</div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;