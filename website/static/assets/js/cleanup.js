import { getConfig } from "./config.js";
import { elementLoading, elements, stopTyping } from "./actions.js";
import { stopAvatarStream } from "./avatar.js";
const { goBackButton } = elements;

// Function to handle navigation after cleanup
const navigateAfterCleanup = async (destination) => {
  try {
    console.log("Cleanup completed successfully");
    window.location.href = destination;
  } catch (error) {
    console.error("Cleanup failed:", error);
    // Proceed with navigation even if cleanup fails
    window.location.href = destination;
  }
};

// variable to store the cleanup promise
let cleanupPromise = null;

// Function to initiate the cleanup process
export const initiateCleanup = async () => {
  if (cleanupPromise) return cleanupPromise;

  // Clear image caches (unchanged)
  if (window.preloadedImages) {
    Object.keys(window.preloadedImages).forEach((key) => {
      if (window.preloadedImages[key].img) {
        window.preloadedImages[key].img.src = "";
        delete window.preloadedImages[key];
      }
    });
  }

  // Force reload of image cache on next visit
  sessionStorage.setItem("lastImageCacheTime", "0");

  stopAvatarStream();
  stopTyping();

  // Use fetch with keepalive AND sendBeacon as fallback
  const cleanupEndpoints = [
    "/candidate/cleanup_session",
    "/api/speech/cleanup",
  ];

  const cleanupPromises = cleanupEndpoints.map((endpoint) => {
    // Try sendBeacon first for reliability during page transitions
    if (navigator.sendBeacon) {
      const beaconSuccess = navigator.sendBeacon(endpoint, JSON.stringify({}));
      if (beaconSuccess)
        return Promise.resolve({ json: () => ({ success: true }) });
    }

    // Fall back to fetch with keepalive
    return fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({}),
    });
  });

  cleanupPromise = Promise.all(cleanupPromises)
    .then((responses) =>
      Promise.all(responses.map((r) => (r.json ? r.json() : r))),
    )
    .catch((error) => {
      console.error("Error during cleanup:", error);
      throw error;
    });

  return cleanupPromise;
};

const handleBackButton = async (event) => {
  // Prevent default history pop behavior
  event.preventDefault();

  // Run cleanup before navigation
  try {
    await initiateCleanup();
    console.log("Cleanup completed before back navigation");
  } catch (error) {
    console.error("Cleanup failed during back navigation:", error);
  }

  // Redirect to the specified URL
  window.location.href = "https://www.mindorah.com";
};
// Ensure the page uses pushState to create an initial history entry
if (window.history && window.history.pushState) {
  window.history.pushState({}, ""); // Push a new state

  // Add popstate event listener to handle the back button
  window.addEventListener("popstate", (event) => {
    handleBackButton(event);
  });
}

const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

document.addEventListener("DOMContentLoaded", () => {
  // Track page navigation type
  const navType = performance.getEntriesByType("navigation")[0]?.type || "";
  const pageAccessedByReload = navType === "reload";

  // Set up page visibility handling for mobile
  if (isMobile) {
    // Create a more reliable mobile back/navigation handler
    const reliableMobileNavigation = async (destination) => {
      // Prevent multiple redirects
      if (sessionStorage.getItem("redirectingNow") === "true") {
        return;
      }
      sessionStorage.setItem("redirectingNow", "true");
      sessionStorage.setItem("intentionalExit", "true"); // Add this line to retain existing functionality

      try {
        if (goBackButton) {
          elementLoading(goBackButton, true);
        }

        // Set a safety timeout to ensure navigation happens
        const navigationTimeout = setTimeout(() => {
          window.location.href = destination;
        }, 3000);

        try {
          await initiateCleanup();
          clearTimeout(navigationTimeout);
          window.location.href = destination;
        } catch (error) {
          console.error("Mobile cleanup failed:", error);
          // Navigation will still occur via the timeout
        }
      } catch (error) {
        // Fallback if something goes wrong
        window.location.href = destination;
      } finally {
        // Clear flag if navigation somehow doesn't happen
        setTimeout(() => {
          sessionStorage.removeItem("redirectingNow");
        }, 5000);
      }
    };

    // Override the goBackButton event for mobile
    if (goBackButton) {
      goBackButton.addEventListener(
        "click",
        (event) => {
          event.preventDefault();

          const config = getConfig();
          const destination =
            config.run === 99
              ? "https://www.mindorah.com"
              : "https://www.mindorah.com";

          reliableMobileNavigation(destination);
        },
        { capture: true },
      ); // Use capture to ensure this runs first
    }

    // Handle back gestures more aggressively
    document.addEventListener(
      "touchend",
      (event) => {
        const touch = event.changedTouches[0];

        // Detect edge swipes common for back gesture
        if (
          touch &&
          (touch.pageX < 30 || touch.pageX > window.innerWidth - 30)
        ) {
          // Prevent default to try to block the native back
          event.preventDefault();

          // Force cleanup and navigation
          reliableMobileNavigation("https://www.mindorah.com");
        }
      },
      { passive: false },
    ); // passive: false allows preventDefault

    // Replace popstate handler for mobile
    window.addEventListener("popstate", (event) => {
      reliableMobileNavigation("https://www.mindorah.com");
    });

    // Enhanced visibility change handler
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "hidden") {
        // Store state so we can redirect on next visibility
        sessionStorage.setItem("shouldRedirect", "true");

        // Still try to clean up
        initiateCleanup().catch((err) =>
          console.error("Visibility cleanup failed:", err),
        );
      } else if (
        document.visibilityState === "visible" &&
        sessionStorage.getItem("shouldRedirect")
      ) {
        // We're back and should redirect
        sessionStorage.removeItem("shouldRedirect");
        window.location.href = "https://www.mindorah.com";
      }
    });
  }
  if (!isMobile && goBackButton) {
    goBackButton.addEventListener("click", async (event) => {
      event.preventDefault();
      sessionStorage.setItem("intentionalExit", "true");

      elementLoading(goBackButton, true);

      const config = getConfig();
      const destination =
        config.run === 99
          ? "https://www.mindorah.com"
          : "https://www.mindorah.com";

      try {
        await initiateCleanup();
        window.location.href = destination;
      } catch (error) {
        console.error("Desktop cleanup failed:", error);
        window.location.href = destination;
      }
    });
  }

  // Handle keyboard refresh consistently across platforms
  document.addEventListener("keydown", (e) => {
    if (e.key === "F5" || (e.ctrlKey && e.key === "r")) {
      e.preventDefault();
      initiateCleanup().finally(() => {
        window.location.href = "https://www.mindorah.com";
      });
    }
  });

  // Modify beforeunload to work better across platforms
  window.addEventListener("beforeunload", (e) => {
    if (sessionStorage.getItem("intentionalExit")) {
      sessionStorage.removeItem("intentionalExit");
      return;
    }

    // On mobile, we need to be more aggressive with cleanup
    if (isMobile) {
      // Don't show dialog on mobile - they don't work well
      initiateCleanup();

      // On mobile browsers, mark for redirect if they come back
      sessionStorage.setItem("shouldRedirect", "true");
    } else {
      // Desktop can show dialog
      initiateCleanup();
      e.returnValue = "";
      return e.returnValue;
    }
  });

  // Mobile-specific: handle redirect on reload
  if (sessionStorage.getItem("shouldRedirect") && pageAccessedByReload) {
    sessionStorage.removeItem("shouldRedirect");
    if (!window.location.href.includes("google.com")) {
      window.location.href = "https://www.mindorah.com";
    }
  }

  // Mobile-specific: handle back attempt persistence
  if (sessionStorage.getItem("mobileBackAttempt")) {
    sessionStorage.removeItem("mobileBackAttempt");
    window.location.href = "https://www.mindorah.com";
  }
});
