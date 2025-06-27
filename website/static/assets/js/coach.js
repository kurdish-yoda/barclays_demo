import * as actions from "./actions.js";
import { initializeConfig, getConfig } from "./config.js";

document.addEventListener("DOMContentLoaded", async function () {
  try {
    // Ensure the config is initialized before using it
    await initializeConfig(actions.elements);

    // Load the interview interface
    await actions.loadInterview();

    const config = getConfig();

    // Consolidate repeated listener logic in a function
    const addChatListener = async () => {
      try {
        // If microphone is listening, ensure it's stopped and duration is recorded
        if (window.STT && window.STT.isListening && window.STT.isListening()) {
          await window.STT.stopListening();
          console.log("Microphone stopped from chat listener");
        }

        await actions.sendAndGetResponse(actions.elements.chatInput.value);
      } catch (error) {
        console.error("Error in chat listener:", error);
      }
    };
    // Add event listeners
    actions.elements.sendButton.addEventListener("click", async () => {
      await addChatListener();
      actions.elements.sendButton.blur();
      actions.elements.chatInput.focus();
    });

    actions.elements.playStopButton.addEventListener("click", () => {
      setTimeout(() => {
        if (actions.state.isTyping) {
          actions.toggleMedia("stop");
        } else {
          actions.toggleMedia("start");
        }
        actions.elements.playStopButton.blur();
        actions.elements.chatInput.focus();
      }, 200); // Adding a delay of 100ms
    });

    actions.elements.microphoneButton.addEventListener("click", async () => {
      try {
        // Capture the mobile state once
        const isMobile = window.matchMedia("(max-width: 768px)").matches;

        if (isMobile) {
          // Mobile-specific code to prevent focus
          if (document.activeElement) document.activeElement.blur();
          event.preventDefault();
        }

        if (!window.STT.isInitialized()) {
          actions.stopTyping();
          // Disable button and show loading state
          actions.elementLoading(actions.elements.microphoneButton, true);
          actions.disableElement(actions.elements.microphoneButton, true);

          const initResult = await actions.initializeSTT();

          // Reset button state
          actions.elementLoading(actions.elements.microphoneButton, false);
          actions.disableElement(actions.elements.microphoneButton, false);

          if (!initResult) {
            return;
          }
        }

        // Toggle microphone
        if (window.STT.isListening()) {
          actions.toggleMicrophone("stop");
        } else {
          actions.toggleMicrophone("record");
        }

        // Always blur the microphone button
        actions.elements.microphoneButton.blur();

        // Only focus input on desktop
        if (!isMobile) {
          actions.elements.chatInput.focus();
        }
      } catch (error) {
        console.error("Error in microphone button handler:", error);
        actions.elementLoading(actions.elements.microphoneButton, false);
        actions.disableElement(actions.elements.microphoneButton, false);
      }
    });

    actions.elements.chatInput.addEventListener("keydown", async (e) => {
      if ((e.keyCode === 13 || e.which === 13) && !e.isComposing) {
        e.preventDefault();
        e.stopPropagation();

        // Force focus back to chat input if it's lost
        actions.elements.chatInput.focus();

        // Blur (unfocus) any other active elements
        if (document.activeElement !== actions.elements.chatInput) {
          document.activeElement.blur();
        }

        await addChatListener();
      }
    });
  } catch (error) {
    console.error("Setup failed:", error);
    // Provide user-friendly error message or fallback UI updates here if necessary
    actions.elements.spinner.style.display = "none";
    actions.elements.contentLoaded.innerHTML = `<div class="error-message">Failed to initialize: ${error.message}</div>`;
    return;
  }
});
