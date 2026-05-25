document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const signupAccountForm = document.getElementById("signup-account-form");
  const loginForm = document.getElementById("login-form");
  const logoutButton = document.getElementById("logout-button");
  const authStatus = document.getElementById("auth-status");
  const messageDiv = document.getElementById("message");

  let currentUser = null;

  function getToken() {
    return localStorage.getItem("authToken");
  }

  function setToken(token) {
    if (token) {
      localStorage.setItem("authToken", token);
      return;
    }
    localStorage.removeItem("authToken");
  }

  function showMessage(text, type = "info") {
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.classList.remove("hidden");
    setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  async function apiFetch(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    const token = getToken();

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    return fetch(url, {
      ...options,
      headers,
    });
  }

  function canManageAnyRegistration() {
    if (!currentUser) {
      return false;
    }
    return currentUser.role === "admin" || currentUser.role === "club_representative";
  }

  function refreshAuthUI() {
    const loggedIn = Boolean(currentUser);
    if (loggedIn) {
      authStatus.textContent = `Logged in as ${currentUser.email} (${currentUser.role})`;
    } else {
      authStatus.textContent = "Not logged in.";
    }

    signupForm.querySelector("button[type='submit']").disabled = !loggedIn;
  }

  async function loadCurrentUser() {
    const token = getToken();
    if (!token) {
      currentUser = null;
      refreshAuthUI();
      return;
    }

    try {
      const response = await apiFetch("/me");
      if (!response.ok) {
        setToken(null);
        currentUser = null;
        refreshAuthUI();
        return;
      }

      currentUser = await response.json();
      refreshAuthUI();
    } catch (error) {
      console.error("Error loading current user:", error);
      currentUser = null;
      refreshAuthUI();
    }
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;

        // Create participants HTML with delete icons instead of bullet points
        const participantsHTML =
          details.participants.length > 0
            ? `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${details.participants
                  .map(
                    (email) =>
                      `<li><span class="participant-email">${email}</span>${
                        canManageAnyRegistration() || (currentUser && currentUser.email === email)
                          ? `<button class="delete-btn" data-activity="${name}" data-email="${email}">❌</button>`
                          : ""
                      }</li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No participants yet</em></p>`;

        activityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Schedule:</strong> ${details.schedule}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">
            ${participantsHTML}
          </div>
        `;

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.target;
    const activity = button.getAttribute("data-activity");
    const email = button.getAttribute("data-email");

    if (!currentUser) {
      showMessage("Please log in first.", "error");
      return;
    }

    try {
      const response = await apiFetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  // Handle account creation
  signupAccountForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      email: document.getElementById("signup-email").value,
      password: document.getElementById("signup-password").value,
      role: document.getElementById("signup-role").value,
    };

    try {
      const response = await fetch("/auth/signup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      if (!response.ok) {
        showMessage(result.detail || "Failed to create account.", "error");
        return;
      }

      showMessage("Account created. You can now log in.", "success");
      signupAccountForm.reset();
    } catch (error) {
      showMessage("Failed to create account. Please try again.", "error");
      console.error("Error creating account:", error);
    }
  });

  // Handle login
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      email: document.getElementById("login-email").value,
      password: document.getElementById("login-password").value,
    };

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      if (!response.ok) {
        showMessage(result.detail || "Failed to log in.", "error");
        return;
      }

      setToken(result.token);
      await loadCurrentUser();
      await fetchActivities();
      showMessage("Logged in successfully.", "success");
      loginForm.reset();
    } catch (error) {
      showMessage("Failed to log in. Please try again.", "error");
      console.error("Error logging in:", error);
    }
  });

  // Handle logout
  logoutButton.addEventListener("click", async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch (error) {
      console.error("Error during logout:", error);
    }

    setToken(null);
    currentUser = null;
    refreshAuthUI();
    fetchActivities();
    showMessage("Logged out.", "info");
  });

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const activity = document.getElementById("activity").value;

    if (!currentUser) {
      showMessage("Please log in before signing up.", "error");
      return;
    }

    try {
      const response = await apiFetch(
        `/activities/${encodeURIComponent(activity)}/signup`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  // Initialize app
  loadCurrentUser().then(() => {
    fetchActivities();
  });
});
