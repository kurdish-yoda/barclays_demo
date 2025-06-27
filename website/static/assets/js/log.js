class Logger {
  static LogLevels = {
    NONE: 0,
    ERROR: 1,
    WARN: 2,
    INFO: 3,
    DEBUG: 4,
    ALL: 5,
  };

  constructor(options = {}) {
    this.enabled = options.enabled !== false;
    this.history = [];
    this.maxHistory = options.maxHistory || 100;
    this.context = options.context || "app";
    this.consoleOutput = options.consoleOutput !== false;
    this.logLevel = options.logLevel || Logger.LogLevels.ALL;
  }

  setLogLevel(level) {
    this.logLevel = level;
  }

  log(message, level = "info", data = null) {
    if (!this.enabled) return;

    // Add level checking
    const levelValue = Logger.LogLevels[level.toUpperCase()];
    if (levelValue > this.logLevel) return;

    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      context: this.context,
      message,
      data,
    };

    // Store log in history
    this.history.unshift(logEntry);
    if (this.history.length > this.maxHistory) {
      this.history.pop();
    }

    // Console output
    if (this.consoleOutput) {
      const styles = {
        error:
          "background: #f44336; color: white; padding: 2px 4px; border-radius: 2px;",
        warn: "background: #ff9800; color: white; padding: 2px 4px; border-radius: 2px;",
        info: "background: #2196f3; color: white; padding: 2px 4px; border-radius: 2px;",
        debug: "color: #9e9e9e;",
      };

      console.log(
        `%c ${level.toUpperCase()} `,
        styles[level],
        `[${this.context}] ${message}`,
        data ? data : "",
      );
    }

    return logEntry;
  }

  info(message, data = null) {
    return this.log(message, "info", data);
  }

  warn(message, data = null) {
    return this.log(message, "warn", data);
  }

  error(message, data = null) {
    return this.log(message, "error", data);
  }

  debug(message, data = null) {
    return this.log(message, "debug", data);
  }

  clear() {
    this.history = [];
  }

  export() {
    return {
      context: this.context,
      logs: this.history,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      url: window.location.href,
    };
  }

  // Helper to download logs as a JSON file
  download() {
    const data = JSON.stringify(this.export(), null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `logs-${this.context}-${new Date().toISOString()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
}

// Create a global logger instance
const globalLogger = new Logger();

export const LogLevels = Logger.LogLevels;
// Export a factory function to create logger instances
export function createLogger(options = {}) {
  return new Logger(options);
}

// Export the global logger instance
export const logger = globalLogger;

// Also add to window for console access
window.logger = globalLogger;
window.LogLevels = Logger.LogLevels;
