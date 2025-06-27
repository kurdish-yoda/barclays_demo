import threading

# Global stop event
stop_event = threading.Event()

def stop_api_event():
    stop_event.set()

def reset_api_event():
    stop_event.clear()

def is_stop_event_set():
    return stop_event.is_set()