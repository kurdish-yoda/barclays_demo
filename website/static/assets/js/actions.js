import { initializeConfig, config } from "./config.js";
import { streamAvatar, stopAvatarStream, initializeTTS } from "./avatar.js";

// Centralized common DOM elements grouping
export const elements = {
  chatInput: document.getElementById("chat_input"),
  coachChat: document.getElementById("coach_chat"),
  typedOutput: document.getElementById("typed-output"),
  sendButton: document.getElementById("sendButton"),
  playStopButton: document.getElementById("play_stop_button"),
  mainContent: document.getElementById("page-content"),
  loadingScreen: document.getElementById("loading-screen"),
  spinner: document.getElementById("spinner"),
  main_content: document.getElementById("page-content"),
  interviewServe: document.getElementById("interviewServe"),
  contentLoaded: document.getElementById("content_loaded"),
  microphoneButton: document.getElementById("microphone_button"),
  timerContainer: document.getElementById("timer_container"),
  goBackButton: document.getElementById("goBack"),
  answerLabel: document.getElementById("answerLabel"),
};

export let state = {
  loading_phase: false,
  isTyping: false,
  isEnd: false,
};

// the typed instance
let typed;
// SVG Definitions for Play/Stop Icons
const playIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" style="font-size: 24px;"><path fill="currentColor" d="M21.409 9.353a2.998 2.998 0 0 1 0 5.294L8.597 21.614C6.534 22.737 4 21.277 4 18.968V5.033c0-2.31 2.534-3.769 4.597-2.648z"/></svg>`;

const stopIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" style="font-size: 24px;"><path fill="currentColor" d="M8 0a8 8 0 1 0 0 16A8 8 0 0 0 8 0m0 14.5a6.5 6.5 0 1 1 0-13a6.5 6.5 0 0 1 0 13M5 5h6v6H5z"/></svg>`;

export async function initializeSTT() {
  window.STT.configure({
    microphoneButton: elements.microphoneButton,
    chatInput: elements.chatInput,
    timerDisplay: document.getElementById("timer_display"),
    timerContainer: elements.timerContainer,
  });

  const permissionResult = await window.STT.requestMicrophonePermission();
  if (!permissionResult.success) {
    console.log("Microphone permission denied - continuing without STT");
    return false;
  }

  const initResult = await window.STT.initialize();

  if (!initResult) {
    throw new Error("Failed to initialize speech service");
  } else {
    console.log("STT initialized successfully");
  }

  return true;
}

// Simplified and Scoped Configurations
export async function configureInterview() {
  await initializeConfig({
    microphoneButton: elements.microphoneButton,
    timerContainer: elements.timerContainer,
  });

  try {
    await initializeSTT();

    // Initialize TTS and handle its initialization
    if (typeof window.TTS !== "undefined" && window.TTS.initialize) {
      const ttsResult = await initializeTTS();
      if (!ttsResult) {
        throw new Error("Failed to initialize TTS service");
      } else {
        console.log("TTS initialized successfully");
      }
    } else {
      throw new Error(
        "TTS service is not available. Check if the TTS library is included and properly loaded.",
      );
    }
  } catch (error) {
    console.error("Error configuring interview:", error);
    // Only re-throw if it's not a permission denial
    if (!error.message.includes("permission denied")) {
      throw error;
    }
  }
}

// Correct way to handle promise resolution using async/await
export async function loadInterview() {
  elements.spinner.style.display = "block";
  elements.contentLoaded.style.display = "none";

  try {
    // Initialize and handle the interview configuration
    await configureInterview();

    // Fetch the response from sendChat
    const response = await sendChat("<-START->");

    // Process the response
    await handleResponse(response, true);

    // Setup for the interview continue button
    elements.spinner.style.display = "none";
    elements.contentLoaded.style.display = "block";
    togglePlayStopButton("stop");
    return new Promise((resolve) => {
      interviewServe.addEventListener("click", async function clickHandler() {
        interviewServe.removeEventListener("click", clickHandler);
        interviewServe.disabled = true;
        interviewServe.classList.add("thn-disabled");

        // Execute all UI changes immediately
        elementLoading(interviewServe, false);
        elements.interviewServe.disabled = false;
        elements.mainContent.style.display = "block";
        elements.loadingScreen.classList.add("fade-out-thn");
        elements.loadingScreen.style.display = "none";
        elements.interviewServe.style.display = "none";

        // Display text and start avatar streaming
        displayTypedHTML(response.response);
        streamAvatar();

        resolve();
      });
    });
  } catch (error) {
    console.error("Setup failed:", error);
    // Handle setup failure - show error message and redirect
    alert("Failed to load try again");
    sessionStorage.setItem("intentionalExit", "true");
    window.location.href = "https://www.mindorah.com/myinterviews";
    return Promise.reject(error);
  }
}

export function disableElement(element, bool) {
  if (!element) {
    console.error("Element is null or undefined");
    return;
  }

  element.disabled = bool;

  const className =
    element === elements.chatInput ? "thn-disabled-chatInput" : "thn-disabled";

  if (bool) {
    element.classList.add(className);
  } else {
    element.classList.remove(className);
  }

  // Log element details and final classes for debugging
  //console.log(`Element (id: ${element.id}, class: ${element.className}) is now ${bool ? 'disabled' : 'enabled'}`);
}

// Function to toggle element's loading state class
export function elementLoading(element, bool) {
  bool
    ? element.classList.add("thn-loading")
    : element.classList.remove("thn-loading");
}

// Function to toggle microphone state and button class
export function toggleMicrophone(state) {
  if (state === "record") {
    // Add mobile device check before starting recording
    if (window.matchMedia("(max-width: 768px)").matches) {
      // On mobile, ensure no input fields are focused
      if (document.activeElement) document.activeElement.blur();
    }

    setTimeout(() => {
      recognizer(true);
      stopTyping();
      stopAvatarStream(false);
    }, 100);
  } else if (state === "stop") {
    recognizer(false);
  } else {
    console.error('Invalid state for microphone. Use "record" or "stop".');
  }
}
export function showElement(element, bool) {
  if (bool) {
    element.style.display = "block";
  } else {
    element.style.display = "none";
  }
}

export function typeOutput(bool) {
  if (bool && !state.isTyping) {
    startTyping();
  } else if (!bool && state.isTyping) {
    stopTyping();
  } else {
    console.error("error in trying to type/stop type...");
    return;
  }
}

// Unified Chat UI Toggle
export function toggleChatUI(bool) {
  const elementsToAddClass = [
    elements.chatInput,
    elements.coachChat,
    elements.sendButton,
    elements.playStopButton,
    elements.microphoneButton,
  ];
  elementsToAddClass.forEach((element) => disableElement(element, bool));
  elementLoading(elements.sendButton, bool);
}

export function recognizer(listeningState) {
  //console.log(`listeningState: ${listeningState}... isListening ${window.STT.isListening()}... isEnd ${state.isEnd}`)
  if (
    listeningState === true &&
    window.STT.isListening() === false &&
    state.isEnd === false
  ) {
    if (window.STT.isInitialized()) {
      window.STT.startListening();
    }
  } else if (
    listeningState === false &&
    window.STT.isListening() === true &&
    state.isEnd === false
  ) {
    if (window.STT.isInitialized()) {
      window.STT.stopListening();
    }
    if (config?.timedInterview) {
      window.STT.stopTimer();
    }
  } else {
    return;
  }
}

export function togglePlayStopButton(state) {
  if (state === "play") {
    play_stop_button.innerHTML = playIcon;
    stopTyping();
  } else if (state === "stop") {
    play_stop_button.innerHTML = stopIcon;
  } else {
    console.error('Invalid state for playStopSwitch. Use "play" or "stop".');
    return;
  }
}

export const setplayStopCounter = (value) => {
  _playStopCounter = value;
};

let _playStopCounter = 0;

export async function toggleMedia(state) {
  if (state === "start") {
    togglePlayStopButton("stop");
    toggleMicrophone("stop");

    // Wait until the current animation is complete if it's running
    while (window.animated_avatar) {
      await new Promise((resolve) => setTimeout(resolve, 100)); // Check every 100ms
      disableElement(elements.playStopButton, true); // Disable the button until avatar streaming starts
      disableElement(elements.microphoneButton, true);
      disableElement(elements.sendButton, true);
    }
    disableElement(elements.playStopButton, false); // Disable the button until avatar streaming starts
    disableElement(elements.microphoneButton, false);
    disableElement(elements.sendButton, false);

    _playStopCounter++;
    if (_playStopCounter === 3) {
      disableElement(elements.playStopButton, true);
    }

    // Start a new avatar stream
    streamAvatar();
    typeOutput(true);

    // ...avatar start
  } else if (state === "stop") {
    typeOutput(false);
    stopAvatarStream();
    // ... stop avatar stream

    togglePlayStopButton("play");
  } else {
    console.error(
      "State was not specified correctly, please specify whether to `stop` or `start media.`",
    );
    return;
  }
}

export function displayTypedHTML(htmlContent, typeSpeed = 40) {
  togglePlayStopButton("stop");

  const element = elements.typedOutput;
  if (!element) {
    console.error("Element with ID typed-output not found.");
    return;
  }

  const maxLength = 8000;

  // Helper to count only visible text
  function getVisibleTextLength(html) {
    const temp = document.createElement("div");
    temp.innerHTML = html;
    return temp.textContent.length;
  }

  console.log("Original length:", htmlContent.length);
  let safeContent = window.DOMPurify.sanitize(htmlContent, {
    ALLOWED_TAGS: ["b", "i", "em", "strong", "p", "span"],
    ALLOWED_ATTR: ["style"],
    ALLOW_ARIA_ATTR: false,
    ALLOWED_URI_REGEXP:
      /^(?:(?:https?|mailto):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,

    // Adding hook to allow specific style values
    ADD_ATTR: ["style"],
    CUSTOM_ATTR: ["*", "style"],
    SAFE_FOR_TEMPLATES: true,
    CUSTOM_ELEMENT_HANDLING: {
      tagNameCheck: /^span$/,
      attributeNameCheck: /^style$/,
      attributeValueCheck: {
        style: new RegExp(/^font-weight\s*:\s*bold;?$/i),
      },
    },
  });
  console.log("Sanitized length:", safeContent.length);
  console.log("Sanitized content:", safeContent);

  let safeTesting = window.DOMPurify.sanitize(htmlContent, {}); // No restrictions
  console.log("Unrestricted sanitize length:", safeTesting.length);
  // Truncate the safeContent if it exceeds the maxLength
  if (getVisibleTextLength(safeContent) > maxLength) {
    console.error(
      "MAX content length reached on interviewer answer in text box",
    );
    const temp = document.createElement("div");
    temp.innerHTML = safeContent;
    const visibleText = temp.textContent;
    const truncatedText = visibleText.substring(0, maxLength);
    temp.textContent = truncatedText;
    safeContent = temp.innerHTML;
  }

  const startTypingHandler = () => {
    if (typed) typed.destroy();
    typed = new Typed("#typed-output", {
      strings: [safeContent],
      typeSpeed: typeSpeed,
      showCursor: false,
      cursorChar: "|",
      contentType: "html",
      onComplete: () => {
        state.isTyping = false;

        // Function to execute the original onComplete logic after typing is done
        const completeHandler = () => {
          setTimeout(() => {
            togglePlayStopButton("play");
            if (config?.timedInterview) {
              toggleMicrophone("record");
            }
          }, 100); // Add a 100ms delay before executing the handler
        };

        // Polling function to wait until is_avatar_streaming is false
        const waitForAvatarStreaming = () => {
          if (!window.is_avatar_streaming) {
            completeHandler();
          } else {
            setTimeout(waitForAvatarStreaming, 100); // Check again after 100ms
          }
        };
        waitForAvatarStreaming(); // Start polling
      },
    });
    state.isTyping = true;
    toggleChatUI(false);

    // clear the page before displaying new content
    elements.chatInput.value = "";
    elements.typedOutput.textContent = "";
    elements.chatInput.focus();
  };

  const waitForAvatarToStream = () => {
    if (window.is_avatar_streaming) {
      startTypingHandler();
    } else {
      setTimeout(waitForAvatarToStream, 100); // Check again after 100ms
    }
  };

  toggleChatUI(true);
  waitForAvatarToStream(); // Start polling
}

export function stopTyping() {
  if (state.isTyping) {
    typed.destroy(); // Stop the typing animation
    document.getElementById("typed-output").innerHTML = typed.strings[0]; // Display the full content
    state.isTyping = false;
    togglePlayStopButton("play");
  }
}

export function startTyping() {
  if (typed) {
    // Clear the content and restart the typing animation
    const element = elements.typedOutput;
    togglePlayStopButton("stop");
    if (element) {
      element.innerHTML = ""; // Clear the current content

      typed.destroy(); // Ensure any previous instance is destroyed

      const startTypingHandler = () => {
        // Reinitialize Typed.js with the same content and settings
        typed = new Typed("#typed-output", {
          strings: [typed.strings[0]], // Use the existing content
          typeSpeed: 40,
          showCursor: false,
          cursorChar: "|",
          contentType: "html", // Ensure content type is HTML
          onComplete: () => {
            // Function to execute the original onComplete logic after typing is done
            const completeHandler = () => {
              togglePlayStopButton("play");
              if (config?.timedInterview) {
                toggleMicrophone("record");
              }
              state.isTyping = false;
            };

            // Polling function to wait until is_avatar_streaming is false
            const waitForAvatarStreaming = () => {
              if (!window.is_avatar_streaming) {
                completeHandler();
              } else {
                setTimeout(waitForAvatarStreaming, 100); // Check again after 100ms
              }
            };

            waitForAvatarStreaming(); // Start polling
          },
        });
        state.isTyping = true;

        disableElement(elements.microphoneButton, false);
        disableElement(elements.sendButton, false);
        if (_playStopCounter !== 3) {
          disableElement(elements.playStopButton, false);
        }
      };

      const waitForAvatarToStream = () => {
        if (window.is_avatar_streaming && window.is_avatar_streaming) {
          startTypingHandler();
        } else {
          setTimeout(waitForAvatarToStream, 100); // Check again after 100ms
        }
      };

      disableElement(elements.playStopButton, true); // Disable the button until avatar streaming starts
      disableElement(elements.microphoneButton, true);
      disableElement(elements.sendButton, true);
      waitForAvatarToStream(); // Start polling
    }
  }
}

async function runEndSequence() {
  state.isEnd = true;

  elements.typedOutput.textContent = "";
  if (config?.timedInterview) {
    window.STT.stopTimer();
  }

  const chatForm = document.getElementById("chatForm");

  // Hide the chat form and other UI elements
  if (chatForm) chatForm.style.display = "none";
  if (elements.sendButton) elements.sendButton.style.display = "none";
  if (elements.answerLabel) elements.answerLabel.style.display = "none";
  if (elements.microphoneButton)
    elements.microphoneButton.style.display = "none";
  if (elements.timerContainer) elements.timerContainer.style.display = "none";
  if (elements.progressBar) {
    elements.progressBar.classList.replace("bg-black-900", "bg-success-500");
    elements.progressBar.style.width = "100%";
  }

  // Polling function to wait for avatar to start streaming
  const pollForAvatarStart = () => {
    return new Promise((resolve) => {
      const interval = setInterval(() => {
        if (window.is_avatar_streaming) {
          clearInterval(interval);
          resolve();
        }
      }, 100); // Check every 100ms
    });
  };

  // Polling function to wait for avatar to stop streaming
  const pollForAvatarStop = () => {
    return new Promise((resolve) => {
      const interval = setInterval(() => {
        if (!window.is_avatar_streaming) {
          clearInterval(interval);
          resolve();
        }
      }, 100); // Check every 100ms
    });
  };

  // Wait for the avatar to start streaming
  await pollForAvatarStart();

  // Wait for the avatar to stop streaming
  await pollForAvatarStop();

  // Shutdown STT service
  try {
    await window.STT.shutdown();
  } catch (error) {
    console.error("Failed to shut down STT service:", error);
  }

  // Shutdown TTS service
  try {
    await window.TTS.shutdown();
    console.log("TTS service shut down successfully at interview end");
  } catch (error) {
    console.error("Failed to shut down TTS service:", error);
  }

  // Show the go-back button after the avatar has stopped streaming
  if (elements.goBackButton) {
    elements.goBackButton.style.visibility = "visible";
  }
}

function sanitizeInput(input) {
  const temp = document.createElement("div");
  temp.innerText = input;
  return temp.innerHTML;
}

export async function sendChat(userInputValue) {
  if (typeof userInputValue !== "string" || !userInputValue.trim()) {
    return Promise.reject("Invalid input provided");
  }

  let sanitizedInput = sanitizeInput(userInputValue);

  // First explicitly stop the microphone if it's listening
  // and wait for it to complete
  if (window.STT.isListening()) {
    try {
      await window.STT.stopListening(); // Wait for this to complete
      console.log("Microphone stopped before sending chat");
    } catch (error) {
      console.error("Error stopping microphone:", error);
    }
  }

  stopAvatarStream();
  toggleMicrophone("stop");
  stopTyping();
  toggleChatUI(true);
  elementLoading(sendButton, true);

  return new Promise((resolve, reject) => {
    if (!userInputValue.trim()) {
      return reject("Input is empty");
    }
    if (window.STT.isListening()) {
      window.STT.stopListening();
    }
    const formData = new FormData();
    formData.append("chat", sanitizedInput);

    fetch("/candidate/interface", {
      method: "POST",
      body: formData,
    })
      .then((response) => {
        if (!response.ok) throw new Error("Network response was not ok");
        toggleChatUI(false);
        elementLoading(sendButton, false);
        return response.json();
      })
      .then((data) => {
        _playStopCounter = 0;
        resolve(data); // Resolve with response data
      })
      .catch((error) => {
        console.error("Network error occurred:", error);
        reject("Network error");
      });
  });
}

export async function handleResponse(response, is_intro = false) {
  try {
    // Set the response globally on the window object, for the streamAvatar function to use
    window.globalResponse = response.response;

    // if its not the intro, stream the avatar. on intro the logic is basically the same but a bit different
    if (!is_intro) {
      streamAvatar();
    }
    setplayStopCounter(0);
    state.question_loaded_first_time = true;
    if (response.response && response.response.includes("ENDEND")) {
      runEndSequence();
    }

    displayTypedHTML(response.response);
  } catch (error) {
    console.error("Error handling response:", error);
  }
}

//function to bunflr up sendChat and handleResponse for ease of use.
export async function sendAndGetResponse(input) {
  try {
    stopAvatarStream();
    stopTyping();

    // If microphone is listening, ensure it's stopped and duration is recorded
    if (window.STT && window.STT.isListening && window.STT.isListening()) {
      await window.STT.stopListening();
    }

    const avatar_response = await sendChat(input);
    handleResponse(avatar_response);
  } catch (error) {
    console.error("Error sending chat:", error);
  }
}
