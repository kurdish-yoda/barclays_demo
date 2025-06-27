function showOverlay() {
  console.log("Fetching overlay data..."); // Debug log

  fetch("/server/get_overlay_data", {
    method: "GET",
    credentials: "include",
    headers: {
      Accept: "application/json",
    },
  })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      const overlay = document.createElement("div");
      overlay.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            z-index: 9999;
            font-size: 12px;
            max-width: 400px;
            white-space: pre-line;
            line-height: 1.2;
        `;

      // Format each entry on a single line
      const content = Object.entries(data)
        .map(([key, value]) => `${key}: ${value}`)
        .join("\n");

      overlay.textContent = content;

      const closeBtn = document.createElement("button");
      closeBtn.textContent = "×";
      closeBtn.style.cssText = `
            position: absolute;
            top: 5px;
            right: 5px;
            background: none;
            border: none;
            color: white;
            cursor: pointer;
            font-size: 16px;
            padding: 2px 6px;
            line-height: 1;
        `;
      closeBtn.onclick = () => overlay.remove();

      overlay.appendChild(closeBtn);
      document.body.appendChild(overlay);
    })
    .catch((error) => {
      console.error("Error details:", error);
      alert("Failed to fetch overlay data. Check console for details.");
    });
}
