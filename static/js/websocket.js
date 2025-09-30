/**
 * WebSocket client for real-time email notifications
 */
class EmailWebSocket {
  constructor(userId) {
    this.userId = userId;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000; // Start with 1 second
    this.isConnected = false;

    this.connect();
  }

  connect() {
    try {
      // Use the hostname from the template or fallback to current hostname
      const hostname = window.hostname || window.location.hostname;
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";

      // Use WebSocket through Nginx proxy on port 443 (HTTPS)
      const wsUrl = `${protocol}//${hostname}/ws/email-notifications/${this.userId}`;

      console.log("🔗 [WebSocket] Starting connection process...");
      console.log("🔗 [WebSocket] Hostname:", hostname);
      console.log("🔗 [WebSocket] Protocol:", protocol);
      console.log("🔗 [WebSocket] User ID:", this.userId);
      console.log("🔗 [WebSocket] Full URL:", wsUrl);
      console.log("🔗 [WebSocket] Current location:", window.location.href);
      console.log("🔗 [WebSocket] User agent:", navigator.userAgent);

      // Close existing connection if any
      if (this.ws && this.ws.readyState !== WebSocket.CLOSED) {
        this.ws.close();
      }

      this.ws = new WebSocket(wsUrl);
      console.log("🔗 [WebSocket] WebSocket object created:", this.ws);

      this.ws.onopen = (event) => {
        console.log("✅ [WebSocket] Connection opened successfully!");
        console.log("✅ [WebSocket] Event details:", {
          type: event.type,
          target: event.target,
          currentTarget: event.currentTarget,
          timeStamp: event.timeStamp,
          isTrusted: event.isTrusted,
        });
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.showConnectionStatus("connected");
      };

      this.ws.onmessage = (event) => {
        console.log("📨 [WebSocket] Message received:", {
          data: event.data,
          type: event.type,
          origin: event.origin,
          timeStamp: event.timeStamp,
        });
        try {
          const data = JSON.parse(event.data);
          console.log("📨 [WebSocket] Parsed message data:", data);
          this.handleMessage(data);
        } catch (error) {
          console.error("❌ [WebSocket] Error parsing message:", {
            error: error,
            message: error.message,
            stack: error.stack,
            rawData: event.data,
          });
        }
      };

      this.ws.onclose = (event) => {
        console.log("🔌 [WebSocket] Connection closed:", {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          type: event.type,
          timeStamp: event.timeStamp,
        });

        // Log specific close codes
        const closeCodeMessages = {
          1000: "Normal closure",
          1001: "Going away",
          1002: "Protocol error",
          1003: "Unsupported data",
          1004: "Reserved",
          1005: "No status received",
          1006: "Abnormal closure",
          1007: "Invalid frame payload data",
          1008: "Policy violation",
          1009: "Message too big",
          1010: "Mandatory extension",
          1011: "Internal error",
          1012: "Service restart",
          1013: "Try again later",
          1014: "Bad gateway",
          1015: "TLS handshake",
        };

        console.log(
          "🔌 [WebSocket] Close code meaning:",
          closeCodeMessages[event.code] || "Unknown code"
        );

        this.isConnected = false;
        this.showConnectionStatus("disconnected");

        // Attempt to reconnect if not a normal closure
        if (
          event.code !== 1000 &&
          this.reconnectAttempts < this.maxReconnectAttempts
        ) {
          console.log("🔄 [WebSocket] Will attempt to reconnect...");
          this.scheduleReconnect();
        } else {
          console.log("🔄 [WebSocket] No more reconnection attempts");
        }
      };

      this.ws.onerror = (error) => {
        console.error("❌ [WebSocket] Error occurred:", {
          error: error,
          type: error.type,
          target: error.target,
          currentTarget: error.currentTarget,
          timeStamp: error.timeStamp,
          isTrusted: error.isTrusted,
        });

        // Log WebSocket state
        console.error("❌ [WebSocket] WebSocket state:", {
          readyState: this.ws.readyState,
          url: this.ws.url,
          protocol: this.ws.protocol,
          extensions: this.ws.extensions,
          bufferedAmount: this.ws.bufferedAmount,
        });

        this.showConnectionStatus("error");
      };
    } catch (error) {
      console.error("❌ [WebSocket] Error creating WebSocket connection:", {
        error: error,
        message: error.message,
        stack: error.stack,
        name: error.name,
      });
    }
  }

  scheduleReconnect() {
    this.reconnectAttempts++;
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000
    ); // Cap at 30 seconds

    console.log("🔄 [WebSocket] Scheduling reconnection:", {
      attempt: this.reconnectAttempts,
      maxAttempts: this.maxReconnectAttempts,
      delay: delay,
      isConnected: this.isConnected,
      readyState: this.ws ? this.ws.readyState : "No WebSocket object",
    });

    setTimeout(() => {
      console.log("🔄 [WebSocket] Reconnection timeout triggered:", {
        isConnected: this.isConnected,
        readyState: this.ws ? this.ws.readyState : "No WebSocket object",
      });

      if (
        !this.isConnected &&
        this.reconnectAttempts <= this.maxReconnectAttempts
      ) {
        console.log("🔄 [WebSocket] Starting reconnection...");
        this.connect();
      } else if (this.reconnectAttempts > this.maxReconnectAttempts) {
        console.log(
          "🔄 [WebSocket] Max reconnection attempts reached, giving up"
        );
        this.showConnectionStatus("error");
      } else {
        console.log("🔄 [WebSocket] Already connected, skipping reconnection");
      }
    }, delay);
  }

  handleMessage(data) {
    console.log("📨 WebSocket message received:", data);

    switch (data.type) {
      case "new_email":
        this.handleNewEmail(data.data);
        break;
      case "email_update":
        this.handleEmailUpdate(data.data);
        break;
      case "system_message":
        this.handleSystemMessage(data.data);
        break;
      default:
        console.log("📨 Unknown message type:", data.type);
    }
  }

  handleNewEmail(emailData) {
    console.log("📧 New email received:", emailData);

    // Show notification
    this.showEmailNotification(emailData);

    // Update inbox if we're on the inbox page
    if (
      window.location.pathname.includes("/owa/inbox") ||
      window.location.pathname.includes("/owa/")
    ) {
      this.addEmailToInbox(emailData);
    }

    // Update unread count
    this.updateUnreadCount();
  }

  handleEmailUpdate(updateData) {
    console.log("📧 Email update received:", updateData);

    // Update email in inbox if we're on the inbox page
    if (
      window.location.pathname.includes("/owa/inbox") ||
      window.location.pathname.includes("/owa/")
    ) {
      this.updateEmailInInbox(updateData);
    }
  }

  handleSystemMessage(messageData) {
    console.log("📢 System message:", messageData);
    this.showSystemNotification(messageData);
  }

  showEmailNotification(emailData) {
    // Create notification element
    const notification = document.createElement("div");
    notification.className = "email-notification";
    notification.innerHTML = `
            <div class="notification-content">
                <div class="notification-header">
                    <i class="fas fa-envelope"></i>
                    <strong>New Email</strong>
                    <button class="close-notification" onclick="this.parentElement.parentElement.remove()">×</button>
                </div>
                <div class="notification-body">
                    <div class="email-sender">From: ${emailData.sender}</div>
                    <div class="email-subject">${emailData.subject}</div>
                    <div class="email-preview">${emailData.preview}</div>
                </div>
                <div class="notification-actions">
                    <button class="btn btn-sm btn-primary" onclick="viewEmail(${emailData.id}); this.parentElement.parentElement.remove();">
                        View Email
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="this.parentElement.parentElement.remove();">
                        Dismiss
                    </button>
                </div>
            </div>
        `;

    // Add to page
    document.body.appendChild(notification);

    // Auto-remove after 10 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 10000);
  }

  addEmailToInbox(emailData) {
    // Check if we're on the inbox page
    const emailList = document.getElementById("emailList");
    if (!emailList) return;

    // Create new email item
    const emailItem = document.createElement("div");
    emailItem.className = "email-item unread";
    emailItem.setAttribute("data-email-id", emailData.id);
    emailItem.onclick = () => viewEmail(emailData.id);

    emailItem.innerHTML = `
            <div class="email-row">
                <div class="email-cell" data-column="checkbox">
                    <input class="form-check-input email-checkbox" type="checkbox" onclick="event.stopPropagation()" data-email-id="${
                      emailData.id
                    }">
                </div>
                <div class="email-cell" data-column="status">
                    <i class="fas fa-envelope text-primary"></i>
                </div>
                <div class="email-cell" data-column="sender">
                    <strong class="email-sender">${emailData.sender}</strong>
                </div>
                <div class="email-cell" data-column="subject">
                    <div class="email-subject">${emailData.subject}</div>
                    <div class="email-preview">${emailData.preview}</div>
                </div>
                <div class="email-cell" data-column="time">
                    <div class="email-time">${new Date(
                      emailData.created_at
                    ).toLocaleString()}</div>
                    <span class="badge bg-primary">New</span>
                    <div class="mt-2">
                        <button class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation(); deleteEmail(${
                          emailData.id
                        })" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

    // Insert at the top of the email list
    const firstEmail = emailList.querySelector(".email-item");
    if (firstEmail) {
      emailList.insertBefore(emailItem, firstEmail);
    } else {
      emailList.appendChild(emailItem);
    }

    // Add highlight effect
    emailItem.style.animation = "highlight 2s ease-in-out";
  }

  updateEmailInInbox(updateData) {
    const emailItem = document.querySelector(
      `[data-email-id="${updateData.email_id}"]`
    );
    if (!emailItem) return;

    if (updateData.action === "mark_as_read") {
      emailItem.classList.remove("unread");
      const statusIcon = emailItem.querySelector(".fa-envelope");
      if (statusIcon) {
        statusIcon.className = "fas fa-envelope-open text-muted";
      }
    }
  }

  updateUnreadCount() {
    // Update unread count in navigation if it exists
    const unreadCount = document.querySelector(".unread-count");
    if (unreadCount) {
      const currentCount = parseInt(unreadCount.textContent) || 0;
      unreadCount.textContent = currentCount + 1;
    }
  }

  showSystemNotification(messageData) {
    // Create system notification
    const notification = document.createElement("div");
    notification.className = "system-notification";
    notification.innerHTML = `
            <div class="alert alert-${
              messageData.level || "info"
            } alert-dismissible fade show" role="alert">
                <i class="fas fa-info-circle"></i>
                ${messageData.message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

    // Add to top of page
    const container =
      document.querySelector(".container-fluid") || document.body;
    container.insertBefore(notification, container.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.remove();
      }
    }, 5000);
  }

  showConnectionStatus(status) {
    // Update connection status indicator if it exists
    const statusIndicator = document.getElementById("connection-status");
    if (statusIndicator) {
      statusIndicator.className = `connection-status ${status}`;
      statusIndicator.innerHTML = `
                <i class="fas fa-${
                  status === "connected" ? "wifi" : "wifi-slash"
                }"></i>
                ${status === "connected" ? "Connected" : "Disconnected"}
            `;

      // Add click handler for manual reconnection
      if (status !== "connected") {
        statusIndicator.style.cursor = "pointer";
        statusIndicator.title = "Click to reconnect";
        statusIndicator.onclick = () => {
          console.log("🔄 [WebSocket] Manual reconnection clicked");
          this.reconnect();
        };
      } else {
        statusIndicator.style.cursor = "default";
        statusIndicator.title = "WebSocket connected";
        statusIndicator.onclick = null;
      }
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close(1000, "User disconnected");
    }
  }

  // Manual reconnection method
  reconnect() {
    console.log("🔄 [WebSocket] Manual reconnection requested");
    this.reconnectAttempts = 0;
    this.isConnected = false;
    this.connect();
  }
}

// Initialize WebSocket when page loads
document.addEventListener("DOMContentLoaded", function () {
  // Get user ID from the page (you'll need to add this to your templates)
  const userId = window.userId || 1; // Default to 1 if not set

  if (userId) {
    window.emailWebSocket = new EmailWebSocket(userId);
  }
});

// Add CSS for notifications
const notificationCSS = `
<style>
.email-notification {
    position: fixed;
    top: 20px;
    right: 20px;
    width: 350px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 1000;
    animation: slideIn 0.3s ease-out;
}

.notification-content {
    padding: 15px;
}

.notification-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    font-weight: bold;
    color: #007bff;
}

.close-notification {
    background: none;
    border: none;
    font-size: 18px;
    cursor: pointer;
    color: #999;
}

.notification-body {
    margin-bottom: 10px;
}

.email-sender {
    font-size: 12px;
    color: #666;
    margin-bottom: 5px;
}

.email-subject {
    font-weight: bold;
    margin-bottom: 5px;
}

.email-preview {
    font-size: 12px;
    color: #666;
    max-height: 40px;
    overflow: hidden;
}

.notification-actions {
    display: flex;
    gap: 10px;
}

.connection-status {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 12px;
    z-index: 1000;
}

.connection-status.connected {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.connection-status.disconnected {
    background: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
}

.connection-status.error {
    background: #fff3cd;
    color: #856404;
    border: 1px solid #ffeaa7;
}

@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

@keyframes highlight {
    0% { background-color: #fff3cd; }
    50% { background-color: #ffeaa7; }
    100% { background-color: transparent; }
}
</style>
`;

// Add CSS to page
document.head.insertAdjacentHTML("beforeend", notificationCSS);
