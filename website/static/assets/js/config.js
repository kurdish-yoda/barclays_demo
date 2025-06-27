export class InterviewConfig {
  static instance = null;

  static CONFIGS = {
    coach_config: {
      timed_interview: false,
      time_limit: 0,
      auto_submit: false,
      auto_microphone: false,
      name: "Coach",
    },
  };

  // constructor is a special method used to initialize a new instance of a class.
  // we parse the session data and set the config
  constructor(sessionData) {
    // this is a singleton pattern, so we check if an instance already exists
    if (InterviewConfig.instance) {
      return InterviewConfig.instance;
    }

    // this is the run number from the session data
    this.run = sessionData.run;

    // using the run number, this sets the config
    this.config = InterviewConfig.CONFIGS["coach_config"];

    // this sets the rest of the session data
    this.sessionData = sessionData;

    // this sets the instance to this new config
    InterviewConfig.instance = this;
  }

  // Initialize the instance with the appropriate config
  static async initialize(elements) {
    // Check if we've already initialized the singleton pattern before fetching data
    if (!InterviewConfig.instance) {
      try {
        console.log("Fetching session data");
        const response = await fetch("/candidate/get_session_data");
        const sessionData = await response.json();
        const config = new InterviewConfig(sessionData);
        if (elements) {
          config.applyConfigurations(elements);
        }
      } catch (error) {
        console.error("Error initializing config:", error);
        throw error;
      }
    } else if (elements) {
      // If already initialized, apply configurations to the UI elements
      InterviewConfig.instance.applyConfigurations(elements);
    }
    return InterviewConfig.instance;
  }

  // Check if the instance exists (will throw if not initialized).
  static getInstance() {
    if (!InterviewConfig.instance) {
      throw new Error(
        "Config not initialized. Call InterviewConfig.initialize() first",
      );
    }
    return InterviewConfig.instance;
  }

  // Getters
  // without this you would have to call config.config.timed_interview for example
  get timedInterview() {
    return this.config.timed_interview;
  }
  get timeLimit() {
    return this.config.time_limit;
  }
  get autoSubmit() {
    return this.config.auto_submit;
  }
  get autoMicrophone() {
    return this.config.auto_microphone;
  }
  get name() {
    return this.config.name;
  }

  // Apply all configurations to the UI, here can add additional configurations
  applyConfigurations(elements) {
    this.applyMicrophoneConfiguration(elements);
    this.applyTimerConfiguration(elements);
    return this; // Allow method chaining
  }

  applyMicrophoneConfiguration(elements) {
    const { microphoneButton } = elements;
    if (this.autoMicrophone) {
      //console.log('Microphone button not enabled');
      microphoneButton.classList.add("thn-disabled");
      microphoneButton.disabled = true;
    } else {
      //console.log('Microphone button is enabled');
      microphoneButton.classList.remove("thn-disabled");
      microphoneButton.disabled = false;
    }
    return this; // Allow method chaining
  }

  applyTimerConfiguration(elements) {
    const { timerContainer } = elements;

    if (this.timedInterview === false && timerContainer) {
      timerContainer.style.display = "none";
    }
    return this; // Allow method chaining
  }

  // Returns the config and session data if needed.
  getAllSettings() {
    return {
      ...this.config,
      sessionData: this.sessionData,
    };
  }
}

// Initialize the configuration when the script is loaded
let config = null;
let initializationPromise = null;

// Export the initialized configuration promise and the config
export const initializeConfig = (elements) => {
  if (!initializationPromise) {
    initializationPromise = InterviewConfig.initialize(elements).then((c) => {
      config = c;
      return c;
    });
  }
  return initializationPromise;
};

export const getConfig = () => {
  if (!config) {
    throw new Error("Config not initialized. Call initializeConfig() first");
  }
  return config;
};

export { config };
