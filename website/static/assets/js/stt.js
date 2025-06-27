import { getConfig, config } from "./config.js";
import { createLogger, LogLevels } from "./log.js";
import { voiceIcon, microphoneIcon } from "./icons.js";
import { elements } from "./actions.js";

const MAX_RETRIES = 3;

class SpeechToTextService {
  constructor() {
    // Core configuration
    this.sdk = window.SpeechSDK;
    this.speechConfig = null;
    this.audioConfig = null;
    this.recognizer = null;

    // Create a logger for the speech service
    this.logger = createLogger({
      context: "speech-service",
      maxHistory: 200,
      logLevel: LogLevels.ERROR,
    });

    // State management
    this.isInitialized = false;
    this.isListening = false;

    // UI elements
    this.microphoneButton = null;
    this.chatInput = null;
    this.timerDisplay = null;
    this.timerContainer = null;

    // Timer management
    this.timerInterval = null; // Initialize to null
    this.microphoneTimeoutId = null; // Initialize to null

    this.recordingStartTime = null;
    this.recordingTimeout = null;
    this.MAX_RECORDING_TIME = 120000; // 2 minutes in milliseconds
  }

  async configure({
    microphoneButton,
    chatInput,
    timerDisplay,
    timerContainer,
  }) {
    this.microphoneButton = microphoneButton;
    this.chatInput = chatInput;
    this.timerDisplay = timerDisplay;
    this.timerContainer = timerContainer;

    // Ensure the configuration is loaded
    if (!config) {
      config = await getConfig();
    }
  }

  async updateMicrophoneButton(isListening) {
    //if (!this.microphoneButton) return;
    //console.log("Updating microphone button");
    try {
      //console.log("Microphone button is auto");
      if (isListening) {
        //console.log("Microphone button is listening");
        this.microphoneButton.classList.replace("btn-dark", "btn-recording");
      } else {
        //console.log("Microphone button is not listening");
        this.microphoneButton.classList.replace("btn-recording", "btn-dark");
      }
    } catch (error) {
      console.error("Error updating microphone button:", error);
      // Disable button if we can't verify configuration
      this.microphoneButton.classList.add("thn-disabled");
      this.microphoneButton.disabled = true;
    }
  }

  async initialize() {
    this.logger.info("Initializing speech service", {
      isListening: this.isListening,
    });
    if (this.isInitialized) return true;

    try {
      // Get the existing audio stream from our previous permission request
      if (!this.microphoneStream) {
        console.error(
          "No microphone stream available - permissions may not have been granted",
        );
        return false;
      }

      const region = await this._fetchSecret("SPEECH-LOCATION");
      const apiKey = await this._fetchSecret("KEY1-SPEECH");
      this.speechConfig = this.sdk.SpeechConfig.fromSubscription(
        apiKey,
        region,
      );
      this.speechConfig.speechRecognitionLanguage = "en-US";
      this.speechConfig.setProperty(
        this.sdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
        "200",
      );

      // Use the existing stream instead of requesting a new one
      this.audioConfig = this.sdk.AudioConfig.fromStreamInput(
        this.microphoneStream,
      );
      this.recognizer = new this.sdk.SpeechRecognizer(
        this.speechConfig,
        this.audioConfig,
      );

      this.setupRecognitionHandlers();
      await this.startRecognizerSession();

      this.isInitialized = true;
      this.isListening = false;
      return true;
    } catch (error) {
      console.error("Initialization failed:", error);
      return false;
    }
  }

  // Set up event handlers for speech recognition
  setupRecognitionHandlers() {
    // This fires DURING speech detection (real-time)
    this.recognizer.recognizing = (s, e) => {
      if (!this.isListening && e.result.text) {
        this.logger.warn("Speech being detected while not in listening mode", {
          text: e.result.text,
          partial: true,
        });
      }
    };

    // This fires AFTER speech is complete (what you already have)
    this.recognizer.recognized = (s, e) => {
      if (!this.isListening && e.result.text) {
        this.logger.warn("Speech detected while not in listening mode", {
          text: e.result.text,
        });
      }
      // Only process recognition results if we're in listening mode
      if (
        this.isListening &&
        e.result.reason === this.sdk.ResultReason.RecognizedSpeech
      ) {
        if (this.chatInput) {
          if (
            this.chatInput.value.trim() === "Your answer (max 800 characters)."
          ) {
            this.chatInput.value = "";
          }
          this.chatInput.value += e.result.text + " ";
        }
      }
    };
  }

  /// Start the WebSocket session
  async startRecognizerSession(retryCount = 3) {
    //console.log('🎤 Starting recognizer session...');

    if (!this.recognizer) {
      console.error("❌ Recognizer not initialized");
      throw new Error("Recognizer not initialized");
    }

    let currentTry = 1;
    const timeout = 10000;

    while (currentTry <= retryCount) {
      try {
        await new Promise((resolve, reject) => {
          const timeoutId = setTimeout(() => {
            reject(new Error("Recognition timeout"));
          }, timeout);

          // Just create and verify the recognizer without starting recognition
          if (this.recognizer) {
            clearTimeout(timeoutId);
            resolve();
          } else {
            clearTimeout(timeoutId);
            reject(new Error("Failed to create recognizer"));
          }
        });
        return;
      } catch (error) {
        console.warn(`⚠️ Attempt ${currentTry} failed:`, error);

        if (currentTry === retryCount) {
          console.error("❌ All attempts failed");
          // Redirect to fallback URL after all attempts fail
          sessionStorage.setItem("intentionalExit", "true");
          window.location.href = "https://www.mindorah.com/myinterviews";
          throw error;
        }

        // Wait before retry
        const delay = Math.min(1000 * Math.pow(2, currentTry - 1), 5000);
        //console.log(`⏳ Waiting ${delay/1000}s before retry...`);
        await new Promise((resolve) => setTimeout(resolve, delay));

        currentTry++;
      }
    }
  }

  // Add these helper methods to your class:
  async releaseAudioResources() {
    //console.log('🎤 Releasing audio resources...');
    try {
      const streams = await navigator.mediaDevices.enumerateDevices();
      streams.forEach((device) => {
        if (device.kind === "audioinput") {
          //console.log(`Found audio device: ${device.label}`);
        }
      });

      // Get all media streams
      const audioStreams = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      audioStreams.getTracks().forEach((track) => {
        track.stop();
        //console.log('Stopped audio track:', track.label);
      });
    } catch (e) {
      console.warn("Warning during audio cleanup:", e);
    }
  }

  async verifyAudioInput(timeoutMs = 2000) {
    //console.log('🎯 Verifying audio input...');
    return new Promise((resolve) => {
      let audioDetected = false;

      const onRecognizing = (event) => {
        if (event?.result?.text) {
          audioDetected = true;
          //console.log('🎤 Audio input verified');
        }
      };

      // Add temporary listener
      this.recognizer.recognizing = onRecognizing;

      // Resolve after timeout
      setTimeout(() => {
        this.recognizer.recognizing = undefined;
        resolve(audioDetected);
        //console.log(`Audio detection result: ${audioDetected ? '✅' : '❌'}`);
      }, timeoutMs);
    });
  }
  // Start active listening
  async startListening() {
    if (!this.isInitialized) {
      await this.initialize();
    }

    this.logger.info("Starting active listening", {
      isInitialized: this.isInitialized,
      microphoneStream: !!this.microphoneStream,
    });

    // Remove any existing animations first
    elements.chatInput.classList.remove("textArea-recording");
    this.microphoneButton.classList.remove("btn-dark");
    this.microphoneButton.classList.add("btn-recording");

    // Force a reflow
    void elements.chatInput.offsetHeight;

    requestAnimationFrame(() => {
      elements.chatInput.classList.add("textArea-recording");
      elements.chatInput.placeholder = "Listening, please talk...";
      elements.chatInput.style.setProperty(
        "--placeholder-color",
        "rgb(255 0 0)",
      );
    });

    this.microphoneButton.innerHTML = voiceIcon;

    const paths = {
      up: "M2 7v10M7 3v18M12 7v10M17 3v18M22 7v10",
      down: "M2 3v18M7 7v10M12 3v18M17 7v10M22 3v18",
    };

    this.voiceAnimationInterval = setInterval(() => {
      const path = document.querySelector(".voice-path");
      if (path) {
        path.setAttribute(
          "d",
          path.getAttribute("d") === paths.up ? paths.down : paths.up,
        );
      }
    }, 1000);

    this.isListening = true;
    this.recordingStartTime = Date.now();

    // Set timeout to stop after MAX_RECORDING_TIME
    if (this.recordingTimeout) {
      clearTimeout(this.recordingTimeout);
    }

    this.recordingTimeout = setTimeout(() => {
      console.log(
        `Recording automatically stopped after ${
          this.MAX_RECORDING_TIME / 1000
        } seconds`,
      );
      this.stopListening();
    }, this.MAX_RECORDING_TIME);

    await new Promise((resolve, reject) => {
      this.recognizer.startContinuousRecognitionAsync(
        () => {
          this.updateMicrophoneButton(true);
          this.logger.info("Recognition started successfully", {
            isListening: true,
          });
          resolve();
        },
        (err) => {
          console.error("Failed to start recognition:", err);
          reject(err);
        },
      );
    });
  }

  async stopListening() {
    if (!this.isListening) return;

    elements.chatInput.classList.remove("textArea-recording");
    this.microphoneButton.classList.remove("btn-recording");
    this.microphoneButton.classList.add("btn-dark");
    elements.chatInput.placeholder = "Your question (max 800 characters).";
    elements.chatInput.style.removeProperty("--placeholder-color");
    this.microphoneButton.innerHTML = microphoneIcon;

    if (this.voiceAnimationInterval) {
      clearInterval(this.voiceAnimationInterval);
      this.voiceAnimationInterval = null;
    }

    const finalRecognitionPromise = new Promise((resolve) => {
      let hasRecognized = false; // Flag to track if we got results
      const originalRecognizedHandler = this.recognizer.recognized;

      this.recognizer.recognized = (s, e) => {
        this.logger.info("Processing final recognition", {
          text: e.result.text,
        });

        if (e.result.text && this.chatInput) {
          if (
            this.chatInput.value.trim() === "Your answer (max 800 characters)."
          ) {
            this.chatInput.value = "";
          }
          this.chatInput.value += e.result.text + " ";
          hasRecognized = true; // Set flag when we get results
        }

        this.recognizer.recognized = originalRecognizedHandler;
        resolve(); // Resolve immediately after processing
      };

      // Only timeout if we haven't received any recognition
      setTimeout(() => {
        if (!hasRecognized) {
          this.logger.warn("Recognition timeout - no final results");
          this.recognizer.recognized = originalRecognizedHandler;
          resolve();
        }
      }, 3000);
    });

    // Stop capturing new audio but keep processing existing audio
    await new Promise((resolve, reject) => {
      this.recognizer.stopContinuousRecognitionAsync(
        () => {
          this.logger.info("Stopped audio capture");
          resolve();
        },
        (err) => reject(err),
      );
    });

    // Wait for final recognition to complete
    await finalRecognitionPromise;

    this.isListening = false;
    this.updateMicrophoneButton(false);

    if (this.recordingTimeout) {
      clearTimeout(this.recordingTimeout);
      this.recordingTimeout = null;
    }

    // Handle duration recording
    if (this.recordingStartTime) {
      const duration = Math.ceil((Date.now() - this.recordingStartTime) / 1000);
      this.recordingStartTime = null;

      try {
        await fetch("/candidate/record_usage", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ recording_seconds: duration }),
          credentials: "same-origin",
        });
      } catch (error) {
        console.error("Error reporting recording duration:", error);
      }
    }
  }

  // Start the timer for listening duration (now only controls timer)
  async startTimer(durationMs) {
    // Do nothing if timer is already running
    if (this.isTimerRunning() || state.isEnd) {
      return;
    }

    this.cleanupTimers();
    const startTime = Date.now();

    // Set timeout to stop listening after duration
    this.microphoneTimeoutId = setTimeout(() => {
      if (this.isListening) {
        this.stopListening();
      }
      this.updateMicrophoneButton(false);
    }, durationMs);

    // Update timer display every second
    this.timerInterval = setInterval(() => {
      const elapsedMs = Date.now() - startTime;
      const remainingMs = Math.max(0, durationMs - elapsedMs);
      if (this.timerDisplay) {
        const remainingSeconds = Math.ceil(remainingMs / 1000);
        this.timerDisplay.textContent = `${remainingSeconds}s`;
      }
      if (remainingMs <= 0) {
        this.cleanupTimers();
      }
    }, 1000);
  }

  // Stop the timer for listening duration
  stopTimer() {
    this.cleanupTimers();
  }

  // Clean up all timers
  cleanupTimers() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }

    if (this.microphoneTimeoutId) {
      clearTimeout(this.microphoneTimeoutId);
      this.microphoneTimeoutId = null;
    }

    if (this.timerDisplay) {
      this.timerDisplay.textContent = "";
    }
  }

  /**
   * Fetch a secret from the server.
   * @param {string} key - Key for the secret.
   * @returns {Promise<string>} - The secret value.
   * @throws {Error} - Throws an error if all retry attempts fail or if too many retries have been made.
   */
  async _fetchSecret(key) {
    if (!key || typeof key !== "string") {
      throw new Error("Invalid key parameter");
    }

    let attempt = 0;

    while (attempt < MAX_RETRIES) {
      try {
        const response = await fetch(`/secrets/${encodeURIComponent(key)}`, {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
        });

        if (!response.ok) {
          if (response.status === 429) {
            // HTTP status code for too many requests
            alert("You have retried too many times. Please try again later.");
            window.location.href = "https://www.mindorah.com/myinterviews";
            throw new Error("Too many retry attempts.");
          } else {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
        }

        const data = await response.json();
        if (!data || !data.value) {
          throw new Error("Invalid response format");
        }

        return data.value;
      } catch (error) {
        console.error(`Attempt ${attempt + 1} failed: ${error.message}`);
        attempt++;
      }
    }

    // If all attempts fail
    alert(
      "Failed to fetch the secret after multiple attempts. Please try again later.",
    );
    window.location.href = "https://www.mindorah.com/myinterviews";
    throw new Error("Exceeded maximum retry attempts");
  }

  async checkMicrophonePermission() {
    try {
      // First try to query the permission status
      const permissions = await navigator.permissions.query({
        name: "microphone",
      });

      return {
        success: permissions.state === "granted",
        state: permissions.state,
      };
    } catch (error) {
      console.error("Error checking microphone permission:", error);
      return {
        success: false,
        state: "prompt", // Default to prompt if we can't check
      };
    }
  }

  // Request microphone permissions and handle the response
  async requestMicrophonePermission() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return {
          success: false,
          error: "Browser does not support audio input",
        };
      }

      // Request microphone access
      this.microphoneStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: false,
      });

      return {
        success: true,
        error: null,
      };
    } catch (error) {
      if (
        error.name === "NotAllowedError" ||
        error.name === "PermissionDeniedError"
      ) {
        return {
          success: false,
          error: "Microphone permission was denied",
        };
      }

      return {
        success: false,
        error: error.message || "Unknown error occurred",
      };
    }
  }

  // Properly close down the WebSocket connection and cleanup
  async shutdown() {
    try {
      if (this.recognizer) {
        await new Promise((resolve, reject) => {
          this.recognizer.stopContinuousRecognitionAsync(
            () => {
              // Stop the recognition session
              this.recognizer.close();
              resolve();
            },
            (err) => {
              console.error("Failed to stop recognition:", err);
              reject(err);
            },
          );
        });
      }

      // Release audio resources
      await this.releaseAudioResources();

      // Additional step to stop any ongoing media streams
      await this.stopUserMedia();

      // Clean up resources
      this.isInitialized = false;
      this.isListening = false;
      this.cleanupTimers();
      this.recognizer = null;
      this.audioConfig = null;
      this.speechConfig = null;

      //console.log("Speech service shut down");
      return true;
    } catch (error) {
      console.error("Shutdown failed:", error);
      return false;
    }
  }

  // Helper method to stop all user media streams
  async stopUserMedia() {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });
      mediaStream.getTracks().forEach((track) => track.stop());
    } catch (error) {
      console.error("Error stopping user media:", error);
    }
  }

  /**
   * Check if the timer is currently running.
   * @returns {boolean} - True if the timer is running, otherwise false.
   */
  isTimerRunning() {
    return this.timerInterval !== null || this.microphoneTimeoutId !== null;
  }
}

// Create and export a single instance with configuration
const speechService = new SpeechToTextService();

// Export public API with configuration method
window.STT = {
  initialize: () => speechService.initialize(),
  startListening: (duration) => speechService.startListening(duration),
  stopListening: () => speechService.stopListening(),
  stopTimer: () => speechService.stopTimer(),
  startTimer: (duration) => speechService.startTimer(duration),
  shutdown: () => speechService.shutdown(),
  requestMicrophonePermission: () =>
    speechService.requestMicrophonePermission(),
  checkMicrophonePermission: () => speechService.checkMicrophonePermission(),
  configure: (config) => speechService.configure(config),
  isListening: () => speechService.isListening,
  isInitialized: () => speechService.isInitialized,
  updateMicrophoneButton: () => speechService.updateMicrophoneButton,
};
