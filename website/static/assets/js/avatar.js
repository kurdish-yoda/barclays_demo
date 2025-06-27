// Update DOM element selections to match index.html IDs
const mouthImage = document.getElementById('mouthImage');
const headContainer = document.getElementById('headContainer');
const eyesImage = document.getElementById('eyesImage');

// Initialize Azure Speech SDK, TTS, and other necessary variables
let synthesizer = null;
let audioContext = null;
let sourceNode = null;

// Add debug logging
const DEBUG = false;  // Toggle detailed logging
function debugLog(message, type = 'info') {
    if (!DEBUG) return;
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    switch(type) {
        case 'error':
            console.error(`[${timestamp}] ${message}`);
            break;
        case 'warn':
            console.warn(`[${timestamp}] ${message}`);
            break;
        default:
            console.log(`[${timestamp}] ${message}`);
    }
}

// Define TTS object and make global early to avoid race conditions
const TTS = {
    initialize: async function() {
        debugLog('TTS service initialized');
        return true; // Return true if initialized successfully
    },
    shutdown: async function() {
        debugLog('TTS service shut down');
        return true; // Return true if shut down successfully
    }
};

// Make TTS globally accessible early in the script
window.TTS = TTS;

const MAX_RETRIES = 3;

// Modified initializeTTS with retry mechanism
async function initializeTTSWithRetry(retries = MAX_RETRIES) {
    let attempt = 0;
    while (attempt < retries) {
        try {
            const result = await TTS.initialize();
            if (result) {
                debugLog('TTS service initialized on attempt ' + (attempt + 1));
                return true;
            }
        } catch (error) {
            debugLog(`TTS initialization attempt ${attempt + 1} failed: ${error}`, 'error');
        }
        attempt++;
    }
    alert('Failed to initialize avatar, please try again.');
    window.location.href = 'https://www.mindorah.com/myinterviews';
    return false;
}

// Function to initialize TTS
export async function initializeTTS() {
    return initializeTTSWithRetry();
}

// Add at the top with other declarations
const mouthShapeImages = [
    'background.png', 'eyes-closed.png', '0.png', '1.png', '2.png', '3.png', '4.png', '5.png', 
    '6.png', '7.png', '8.png', '9.png', '10.png', '11.png', '12.png', '13.png', 
    '14.png', '15.png', '16.png', '17.png', '18.png', '19.png', '20.png', '21.png', 'head.png'
];

const preloadedImages = {};
let mouthMovementTimeouts = [];

// Global flag to cancel pending timeouts
let cancelPendingTimeouts = false;

// Add the clearMouthMovementTimeouts function before it's used
function clearMouthMovementTimeouts() {
    mouthMovementTimeouts.forEach(timeoutId => clearTimeout(timeoutId));
    mouthMovementTimeouts = [];
    debugLog('All mouth movement timeouts cleared.');
}

// Function to play audio
async function playAudio(audioData) {
    if (!audioData) {
        debugLog("No audio data to play.", 'error');
        return;
    }

    try {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 24000
            });
            debugLog('AudioContext initialized');
        }

        debugLog(`Processing audio data of size: ${audioData.byteLength} bytes`);
        
        return new Promise((resolve, reject) => {
            audioContext.decodeAudioData(
                audioData,
                (buffer) => {
                    debugLog('Audio decoded successfully');
                    sourceNode = audioContext.createBufferSource();
                    sourceNode.buffer = buffer;
                    sourceNode.connect(audioContext.destination);
                    sourceNode.start(0);
                    window.is_avatar_streaming = true;
                    debugLog('Audio playback started');
                    
                    sourceNode.onended = function() {
                        debugLog('Audio playback completed');
                        cleanupSynthesizer();
                        resolve();
                    };
                },
                (error) => {
                    debugLog(`Error decoding audio: ${error}`, 'error');
                    cleanupSynthesizer();
                    reject(error);
                }
            );
        });
    } catch (error) {
        debugLog(`Playback error: ${error}`, 'error');
        cleanupSynthesizer();
        throw error;
    }
}
// Function to stop audio
function stopAudioPlayback() {
    debugLog('Stopping audio playback');
    if (sourceNode) {
        sourceNode.stop();
        debugLog('Source node stopped');
        window.is_avatar_streaming = false;
        sourceNode.disconnect();
        debugLog('Source node disconnected');
        sourceNode = null;
    }
    if (audioContext) {
        audioContext.close();
        debugLog('Audio context closed');
        audioContext = null;
    }
}

// Initialize mouth image to Neutral (hidden)
mouthImage.src = ''; // No initial src
mouthImage.style.opacity = '0';

// Cleanup function that matches original logic
function cleanupSynthesizer() {
    debugLog('Starting cleanup');
    if (synthesizer) {
        synthesizer.close();
        synthesizer = null;
        debugLog('Synthesizer cleaned up');
    }
    stopAudioPlayback();
    clearMouthMovementTimeouts();
    
    resetHeadPosition();
    
    const neutralImage = preloadedImages['0.png'];
    if (neutralImage) {
        mouthImage.src = neutralImage.src;
        mouthImage.style.opacity = '0';
        debugLog('Mouth animation reset to neutral');
    }
}

function useGlobalResponse() {
    const response = window.globalResponse;
    if (response) {
        // Create a new DOMParser instance
        const parser = new DOMParser();
        // Parse the response as HTML
        const doc = parser.parseFromString(response, 'text/html');
        // Extract text content from the document
        const textContent = doc.body.textContent || "";
        
        //console.log('Formatted Global Response:', textContent.trim());
        return textContent.trim();
    } else {
        debugLog('No global response set.', 'error');
        return null;
    }
}

function resetHeadPosition() {

    // First get the computed transform values
    const currentTransform = window.getComputedStyle(headContainer).transform;
    headContainer.style.transform = currentTransform;

    // Clear any existing animations
    headContainer.style.animation = 'none';

    // Force a reflow
    void headContainer.offsetWidth;

    // Add a transition for smooth movement
    headContainer.style.transition = 'transform 0.5s ease-out';

    // Request next frame to ensure the transition is applied
    requestAnimationFrame(() => {
        headContainer.style.transform = 'rotate(0deg) scale(1)';
    });

    // Remove the transition after it completes
    setTimeout(() => {
        headContainer.style.transition = '';
    }, 500);
}

// Update streamAvatar to match original stream_avatar logic
export async function streamAvatar() {
    try {
        const text = useGlobalResponse();
        
        if (!text) {
            alert('Please enter some text to speak.');
            return;
        }
        clearMouthMovementTimeouts();

        const response = await fetch('/api/speech/synthesize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text: text })
        });

        if (!response.ok) {
            throw new Error('Speech synthesis failed');
        }

        const data = await response.json();

        if (audioContext) {
            await audioContext.close();
            debugLog('AudioContext closed');
            audioContext = null;
        }

        const binaryString = window.atob(data.audio);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }

        const neutralImage = preloadedImages['0.png'];
        if (neutralImage) {
            mouthImage.src = neutralImage.src;
        } else {
            mouthImage.src = '';
        }
        mouthImage.style.opacity = '1';
        
        const animationPromise = new Promise(resolve => {
            setTimeout(() => {
                if (cancelPendingTimeouts) {
                    debugLog('Animation canceled before starting.');
                    resolve();
                } else {
                    playAnimation(data.animation);
                    resolve();
                }
            }, 1000);
        });

        await animationPromise;
        await playAudio(bytes.buffer);

        // Log the completion of the avatar streaming process
        debugLog('Avatar streaming completed');

    } catch (error) {
        debugLog('Error during speech synthesis: ' + error, 'error');
        alert('Error during speech synthesis. Please try again.');
        cleanupSynthesizer();
    }
}

// New function to reset the mouth image and animation state
function resetAvatarState() {
    const neutralImage = preloadedImages['0.png'];
    if (neutralImage) {
        mouthImage.src = neutralImage.src;
        mouthImage.style.opacity = '0';
    }
    debugLog('Animation sequence completed, mouth image reset to neutral');
    window.animated_avatar = false; // Animation ends
}

// Updated stopAvatarStream function
export function stopAvatarStream(cancelPendingTimeouts=true) {
    debugLog('Stopping avatar stream');
    cancelPendingTimeouts = cancelPendingTimeouts;
    //cleanupSynthesizer();
    resetAllStates();

    // Ensure mouth image and animation state are reset
    resetAvatarState();

    debugLog('Speech synthesis canceled. Mouth image and head animation reset.');
}

// Make functions available globally as in original
window.stream_avatar = streamAvatar;
window.is_avatar_streaming = false;

// Add the startBlinking function
function startBlinking() {
    const minBlinkInterval = 2000; // Minimum time between blinks (in ms)
    const maxBlinkInterval = 6000; // Maximum time between blinks (in ms)
    const blinkDuration = 300;     // Duration of the blink (in ms)
    let blinkTimeout;

    function blink() {
        // Close eyes
        eyesImage.style.opacity = '1';

        // Open eyes after blinkDuration
        setTimeout(function() {
            eyesImage.style.opacity = '0';
        }, blinkDuration);

        // Schedule the next blink
        const nextBlink = Math.floor(Math.random() * (maxBlinkInterval - minBlinkInterval + 1)) + minBlinkInterval;
        blinkTimeout = setTimeout(blink, nextBlink);
    }

    // Start the blinking loop
    blink();
}

// Function to preload images with cache-busting
function forceReloadImages() {
    return new Promise((resolve, reject) => {
        const timestamp = new Date().getTime();
        let loadedImages = 0; // Counter for loaded images
        const totalImages = mouthShapeImages.length; // Total number of images to load

        // Clear existing preloaded images
        Object.keys(preloadedImages).forEach(key => {
            delete preloadedImages[key];
        });

        // Create a hidden container to "use" preloaded images
        let preloadContainer = document.getElementById('preloadContainer');
        if (!preloadContainer) {
            preloadContainer = document.createElement('div');
            preloadContainer.id = 'preloadContainer';
            preloadContainer.style.display = 'none';
            document.body.appendChild(preloadContainer);
        }

        // Clear existing children in the hidden container
        while (preloadContainer.firstChild) {
            preloadContainer.removeChild(preloadContainer.firstChild);
        }

        debugLog('Initiating image reload');

        // Helper function to load individual images
        const loadImage = (imageName) => {
            return new Promise((resolveImage) => {
                const img = new Image();
                img.crossOrigin = "anonymous"; // Add cross-origin handling
                
                // Create blob URL to prevent request cancellation
                fetch(`${avatarImageURL}${imageName}?t=${timestamp}`)
                    .then(response => response.blob())
                    .then(blob => {
                        const blobUrl = URL.createObjectURL(blob);
                        img.src = blobUrl;
                        
                        img.onload = () => {
                            preloadedImages[imageName] = img;
                            // Store the blob URL for cleanup
                            img.blobUrl = blobUrl;
                            loadedImages++;
                            resolveImage();
                        };
                    })
                    .catch(error => {
                        debugLog(`Failed to fetch image: ${imageName}`, 'error');
                        loadedImages++;
                        resolveImage();
                    });
            });
        };

        // Add cleanup function
        const cleanup = () => {
            Object.values(preloadedImages).forEach(img => {
                if (img.blobUrl) {
                    URL.revokeObjectURL(img.blobUrl);
                }
            });
        };

        // Load all images in parallel
        Promise.all(mouthShapeImages.map(imageName => loadImage(imageName)))
            .then(() => {
                debugLog(`Loaded ${loadedImages}/${totalImages} images for avatar`); // Log loaded images
                resolve(); // Resolve the main promise
            })
            .catch((error) => {
                debugLog(`Image reload error: ${error}`, 'error');
                reject(error); // Reject the main promise on error
            });
    });
}

// Function to reset all states and resources
function resetAllStates() {
    stopAudioPlayback();
    cleanupSynthesizer();
    clearMouthMovementTimeouts();
    sourceNode = null;
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    window.is_avatar_streaming = false;

    const neutralImage = preloadedImages['0.png'];
    if (neutralImage) {
        mouthImage.src = neutralImage.src;
    } else {
        mouthImage.src = '';
    }
    mouthImage.style.opacity = '0';
    resetHeadPosition();
}

// Add this line at the top with other global variables
let avatarImageURL = '';

// Declare global variable to track animation state
window.animated_avatar = false;

// Update the DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', async () => {
    resetAllStates();

    try {
        const response = await fetch('/candidate/get_avatar');
        if (response.ok) {
            const data = await response.json();
            debugLog('Session avatar: ' + data.avatar);
            window.sessionAvatar = data.avatar;   // Set it as a global variable
            avatarImageURL = `/static/assets/images/${sessionAvatar}/`;  // Update the base URL with the avatar

            // Always reload images
            await forceReloadImages();

            // Set the src of the images using preloaded images
            document.getElementById('backgroundImage').src = preloadedImages['background.png'].src;
            document.getElementById('headImage').src = preloadedImages['head.png'].src;
            document.getElementById('eyesImage').src = preloadedImages['eyes-closed.png'].src;

            startBlinking();
        } else {
            debugLog('Failed to fetch session avatar: ' + response.statusText, 'error');
        }
    } catch (error) {
        debugLog('Error fetching session avatar: ' + error, 'error');
        alert('Failed to initialize avatar, please try again.');
        window.location.href = 'https://www.mindorah.com/myinterviews';
    }
});


function playAnimation(animationData) {
    debugLog('Starting animation sequence');
    debugLog(`Total frames: ${animationData.frames.length}`);
    window.animated_avatar = true;  // Animation starts

    if (!animationData || !animationData.frames || !Array.isArray(animationData.frames)) {
        debugLog('Invalid animation data received', 'error');
        window.animated_avatar = false; // Animation did not start due to error
        return;
    }

    let frames = animationData.frames;
    let totalDuration = animationData.total_duration || 0;

    let subtleHeadMovement_time = totalDuration;

    if (subtleHeadMovement_time > 10000) {
        subtleHeadMovement_time = 10000;
    }

    headContainer.style.animation = `subtleHeadMovement ${subtleHeadMovement_time}ms infinite`;
    
    const frameTimeouts = frames.map(frame => setTimeout(() => {
        if (cancelPendingTimeouts) {
            debugLog('Animation canceled during execution.');
            return;
        }
        const preloadedImage = preloadedImages[frame.image];
        if (preloadedImage) {
            mouthImage.src = preloadedImage.src;
            mouthImage.style.opacity = '1';
        }
    }, frame.timestamp));

    mouthMovementTimeouts.push(...frameTimeouts);

    debugLog(`Scheduled ${frames.length} frame updates for animation`);
    debugLog(`Cancel Pending Timeouts: ${cancelPendingTimeouts}`);

    const resetTimeoutId = setTimeout(() => {
        debugLog(`Timeout: ${totalDuration} reached`);
        if (!cancelPendingTimeouts) {
            debugLog('Animation sequence completed normally.');
            resetAvatarState();
        }
    }, totalDuration);

    mouthMovementTimeouts.push(resetTimeoutId);
}

// Add this function to your existing code
function analyzeCurrentVisemes() {
    const stats = {
        preloadedImages: {
            total: Object.keys(preloadedImages).length,
            list: Object.keys(preloadedImages)
        },
        currentMouth: mouthImage.src,
        lastAnimation: window.lastAnimationData || null,
        isStreaming: window.is_avatar_streaming,
    };

    console.group('Avatar Viseme Analysis');
    
    // Extract timestamp from current mouth image URL
    const timestampMatch = stats.currentMouth.match(/[?&]t=(\d+)/);
    const imageTimestamp = timestampMatch ? new Date(parseInt(timestampMatch[1])) : null;

    console.log('Current Status:', {
        'Avatar Streaming': stats.isStreaming,
        'Loaded Images': stats.preloadedImages.total,
        'Current Mouth Image': stats.currentMouth.split('/').pop(),
        'Image Timestamp': imageTimestamp ? imageTimestamp.toLocaleString() : 'No timestamp found'
    });

    // Analyze blob URLs
    const blobUrls = Object.values(preloadedImages)
        .filter(img => img.blobUrl)
        .map(img => img.blobUrl);

    console.log('Blob Statistics:', {
        'Total Blob URLs': blobUrls.length,
        'Memory Usage': 'Not available (browser restriction)'
    });

    console.groupEnd();
}

// Make it globally available
window.analyzeCurrentVisemes = analyzeCurrentVisemes;

window.streamAvatar = streamAvatar;
window.is_avatar_streaming = false;
window.stopAvatarStream = stopAvatarStream;
window.initializeTTS = initializeTTS;
