const el = (id) => document.getElementById(id);
const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/controller_view";

function connect() {
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (e) => {
        try {
            const msg = JSON.parse(e.data);
            const now = Date.now() / 1000;

            // Update status indicators
            const camAlive = now - msg.camera_ts < 1.5;
            const ctrlAlive = now - msg.controller_ts < 1.5;

            el("camStatus").textContent = camAlive ? "Online" : "Offline";
            el("camStatus").style.color = camAlive ? "green" : "red";

            el("ctrlStatus").textContent = ctrlAlive ? "Connected" : "No Signal";
            el("ctrlStatus").style.color = ctrlAlive ? "green" : "red";

            // 1. Try to get data from controller (laptop -> server)
            let controlData = null;
            if (msg.controller) {
                try {
                    controlData = typeof msg.controller === "string" 
                        ? JSON.parse(msg.controller) 
                        : msg.controller;
                } catch (e) {
                    console.log("Failed to parse controller data:", e);
                }
            }

            // 2. If no controller data, try robot data (rpi -> server)
            if (!controlData && msg.robot) {
                try {
                    controlData = typeof msg.robot === "string" 
                        ? JSON.parse(msg.robot) 
                        : msg.robot;
                } catch (e) {
                    console.log("Failed to parse robot data:", e);
                }
            }

            // 3. Update display with whatever data we have
            if (controlData) {
                el("steering").textContent = controlData.steering !== undefined ? controlData.steering : 0;
                el("throttle").textContent = controlData.throttle !== undefined ? controlData.throttle : 0;
                
                // Distance can come from either source
                const distance = controlData.ultra_front || controlData.distance_front || controlData.d_front || "-";
                el("d_front").textContent = distance;

                // Mode handling
                const mode = controlData.mode || (controlData.tombol ? 
                    (controlData.tombol[4] === 1 ? "mundur" : 
                        controlData.tombol[5] === 1 ? "maju" : "maju") 
                    : "maju");
                
                el("mode").textContent = mode.toUpperCase();
                el("mode").className = "value " + (mode === "maju" ? "mode-fwd" : "mode-rev");
            }

        } catch (error) {
            console.error("WebSocket message error:", error);
        }
    };

    ws.onclose = () => {
        console.log("WebSocket disconnected, reconnecting...");
        setTimeout(connect, 2000);
    };

    ws.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}

// Start connection
connect();

// Auto-reload video feed on error
const video = el("video");
video.onerror = function() {
    console.log("Video feed error, reloading...");
    setTimeout(() => {
        video.src = "/video_feed?t=" + new Date().getTime();
    }, 2000);
};

// Periodically refresh video feed to prevent stalling
setInterval(() => {
    if (video.src) {
        video.src = video.src.split('?')[0] + '?t=' + new Date().getTime();
    }
}, 30000); // Refresh every 30 seconds