// ==================== FINTECH FRONTEND CONTROLLER ====================

const API_BASE = window.location.origin; // Dynamically maps to https://localhost:8000 or production URL

// State Management
let currentUser = null;
let currentToken = localStorage.getItem("token") || null;

// DOM Elements
const authSection = document.getElementById("auth-section");
const dashboardSection = document.getElementById("dashboard-section");
const userPill = document.getElementById("user-pill");
const pillUsername = document.getElementById("pill-username");
const dashUsername = document.getElementById("dash-username");
const btnLogout = document.getElementById("btn-logout");

const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const formLogin = document.getElementById("form-login");
const formRegister = document.getElementById("form-register");
const authAlert = document.getElementById("auth-alert");

const ownedAccountsList = document.getElementById("owned-accounts-list");
const sharedAccountsList = document.getElementById("shared-accounts-list");

const formCreateAccount = document.getElementById("form-create-account");
const formTransfer = document.getElementById("form-transfer");
const formAddCoOwner = document.getElementById("form-add-co-owner");
const formEnqueue = document.getElementById("form-enqueue");
const consoleLogs = document.getElementById("console-logs");

// ==================== INITIALIZATION ====================
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    if (currentToken) {
        fetchUserProfile();
    } else {
        showAuthView();
    }
});

// ==================== EVENT LISTENERS ====================
function setupEventListeners() {
    // Auth Tab Toggles
    tabLogin.addEventListener("click", () => {
        tabLogin.classList.add("active");
        tabRegister.classList.remove("active");
        formLogin.classList.remove("hidden");
        formRegister.classList.add("hidden");
        authAlert.classList.add("hidden");
    });

    tabRegister.addEventListener("click", () => {
        tabRegister.classList.add("active");
        tabLogin.classList.remove("active");
        formRegister.classList.remove("hidden");
        formLogin.classList.add("hidden");
        authAlert.classList.add("hidden");
    });

    // Form Submissions
    formLogin.addEventListener("submit", handleLogin);
    formRegister.addEventListener("submit", handleRegister);
    formCreateAccount.addEventListener("submit", handleCreateAccount);
    formTransfer.addEventListener("submit", handleTransfer);
    formAddCoOwner.addEventListener("submit", handleAddCoOwner);
    formEnqueue.addEventListener("submit", handleEnqueueJob);

    // Logout
    btnLogout.addEventListener("click", handleLogout);
}

// ==================== VIEWS CONTROLLER ====================
function showAuthView() {
    authSection.classList.remove("hidden");
    dashboardSection.classList.add("hidden");
    userPill.classList.add("hidden");
}

function showDashboardView() {
    authSection.classList.add("hidden");
    dashboardSection.classList.remove("hidden");
    userPill.classList.remove("hidden");
}

function displayAuthAlert(message, type = "danger") {
    authAlert.textContent = message;
    authAlert.className = `alert alert-${type}`;
    authAlert.classList.remove("hidden");
}

// ==================== API HANDLERS ====================

// 1. LOGIN
async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;

    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    try {
        const response = await fetch(`${API_BASE}/token`, {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed");
        }

        currentToken = data.access_token;
        localStorage.setItem("token", currentToken);
        await fetchUserProfile();
    } catch (err) {
        displayAuthAlert(err.message, "danger");
    }
}

// 2. REGISTER
async function handleRegister(e) {
    e.preventDefault();
    const name = document.getElementById("register-name").value;
    const email = document.getElementById("register-email").value;
    const password = document.getElementById("register-password").value;

    // Determine Shard dynamically for registration: we can register users in any shard by appending shard_key
    // Let's use a random shard_key (1 or 2) to demonstrate physical partitioning on registration
    const shardKey = email.length % 2 === 1 ? 1 : 2;

    try {
        const response = await fetch(`${API_BASE}/users?shard_key=${shardKey}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Registration failed");
        }

        displayAuthAlert("Identity created! Please log in above.", "success");
        formRegister.reset();
        tabLogin.click(); // Switch to login tab
    } catch (err) {
        displayAuthAlert(err.message, "danger");
    }
}

// 3. FETCH PROFILE & RELATIONS
async function fetchUserProfile() {
    // We can fetch profile from Shard 1 or Shard 2. 
    // To make sure we find the user, let's try Shard 1 first, and if not found, search Shard 2.
    // Or we can let the backend handle this (which is what we did dynamically by letting them supply credentials).
    // In our backend, the shard_key parameter tells the session local which engine to bind.
    // Since we don't know the user's ID before fetching, we can iterate through the shard keys in fetch.
    let user = null;
    
    for (let key of [1, 2]) {
        try {
            const response = await fetch(`${API_BASE}/users/me?shard_key=${key}`, {
                headers: { "Authorization": `Bearer ${currentToken}` }
            });
            if (response.ok) {
                user = await response.json();
                user.shardKey = key; // Save which shard they were found on
                break;
            }
        } catch (err) {
            console.error(`Error searching Shard ${key}:`, err);
        }
    }

    if (!user) {
        handleLogout();
        return;
    }

    currentUser = user;
    pillUsername.textContent = user.name;
    dashUsername.textContent = user.name;
    
    // Update Shard UI Indicator
    const shardIndicator = document.querySelector(".shard-indicator span strong");
    shardIndicator.textContent = `Node ${user.shardKey} (${user.shardKey % 2 === 1 ? 'backend' : 'backend_shard2'})`;

    renderAccounts();
    showDashboardView();
}

// 4. LOGOUT
function handleLogout() {
    currentUser = null;
    currentToken = null;
    localStorage.removeItem("token");
    formLogin.reset();
    formRegister.reset();
    showAuthView();
}

// 5. RENDER ACCOUNTS
function renderAccounts() {
    ownedAccountsList.innerHTML = "";
    sharedAccountsList.innerHTML = "";

    // Render Owned Accounts
    if (currentUser.accounts && currentUser.accounts.length > 0) {
        currentUser.accounts.forEach(acc => {
            ownedAccountsList.appendChild(createAccountCard(acc));
        });
    } else {
        ownedAccountsList.innerHTML = `<div class="empty-state">No accounts owned. Click "Open Account" to create one.</div>`;
    }

    // Render Co-owned Accounts
    if (currentUser.shared_accounts && currentUser.shared_accounts.length > 0) {
        currentUser.shared_accounts.forEach(acc => {
            sharedAccountsList.appendChild(createAccountCard(acc, true));
        });
    } else {
        sharedAccountsList.innerHTML = `<div class="empty-state">No joint accounts linked.</div>`;
    }
}

function createAccountCard(acc, isShared = false) {
    const card = document.createElement("div");
    card.className = "glass-card account-card";
    
    // Build co-owners text
    let coOwnersHTML = "";
    if (acc.co_owners && acc.co_owners.length > 0) {
        coOwnersHTML = `
            <div class="acc-co-owners">
                <span class="co-owner-label">Co-owners:</span>
                <div class="co-owner-pills">
                    ${acc.co_owners.map(owner => `
                        <span class="co-owner-pill" title="${owner.email}">
                            <i class="fa-solid fa-user-circle"></i> ID ${owner.id} (${owner.name})
                        </span>
                    `).join('')}
                </div>
            </div>
        `;
    }

    card.innerHTML = `
        <div class="acc-card-header">
            <span class="acc-type">${acc.account_type}</span>
            <span class="acc-id">ID: ${acc.id} ${isShared ? '(Joint)' : ''}</span>
        </div>
        <div class="acc-num">Acc #: ${acc.account_number}</div>
        <div class="acc-bal">$${parseFloat(acc.balance).toFixed(2)}</div>
        ${coOwnersHTML}
    `;
    return card;
}

// 6. CREATE ACCOUNT
async function handleCreateAccount(e) {
    e.preventDefault();
    const accountType = document.getElementById("new-account-type").value;
    const balance = document.getElementById("new-account-balance").value;
    
    // We must pass the correct shard_key so it is written to the same shard the user belongs to!
    const shardKey = currentUser.shardKey;

    try {
        const response = await fetch(`${API_BASE}/users/${currentUser.id}/accounts?shard_key=${shardKey}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${currentToken}`
            },
            body: JSON.stringify({
                account_type: accountType,
                balance: parseFloat(balance),
                account_number: `ACC-LV-${Math.floor(1000 + Math.random() * 9000)}` // Random account number
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Account creation failed");
        }

        formCreateAccount.reset();
        await fetchUserProfile(); // Reload profile to update accounts list
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

// 7. TRANSFER FUNDS (PESSIMISTIC LOCKING)
async function handleTransfer(e) {
    e.preventDefault();
    const senderId = document.getElementById("transfer-sender").value;
    const receiverId = document.getElementById("transfer-receiver").value;
    const amount = document.getElementById("transfer-amount").value;

    // Since our transfer updates both tables, we route to the shard of the sender account
    // For simplicity, we match the shard of the current user
    const shardKey = currentUser.shardKey;

    try {
        const response = await fetch(`${API_BASE}/transfers?shard_key=${shardKey}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${currentToken}`
            },
            body: JSON.stringify({
                sender_account_id: parseInt(senderId),
                receiver_account_id: parseInt(receiverId),
                amount: parseFloat(amount)
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Secure transfer failed");
        }

        alert(`Success: ${data.message}!\nNew Balance: $${data.sender_new_balance.toFixed(2)}`);
        formTransfer.reset();
        await fetchUserProfile(); // Reload dashboard
    } catch (err) {
        alert(`Lock/Transfer Error: ${err.message}`);
    }
}

// 8. ADD CO-OWNER (MANY-TO-MANY LINK)
async function handleAddCoOwner(e) {
    e.preventDefault();
    const accountId = document.getElementById("share-account-id").value;
    const userId = document.getElementById("share-user-id").value;
    
    const shardKey = currentUser.shardKey;

    try {
        const response = await fetch(`${API_BASE}/accounts/${accountId}/add_co_owner/${userId}?shard_key=${shardKey}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${currentToken}`
            }
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Failed to add co-owner");
        }

        alert("Joint access granted successfully!");
        formAddCoOwner.reset();
        await fetchUserProfile(); // Reload accounts list
    } catch (err) {
        alert(`Sharing Error: ${err.message}`);
    }
}

// 9. ENQUEUE BG REPORT JOB (DECOUPLED LOG PROCESSING)
function handleEnqueueJob(e) {
    e.preventDefault();
    const email = document.getElementById("enqueue-email").value;
    
    // Append log line locally that it was enqueued
    logConsole("[MAIN] API Route /test/enqueue hit. Packaging job payload...", "info");
    
    fetch(`${API_BASE}/test/enqueue?email=${email}`, { method: "POST" })
        .then(response => response.json())
        .then(data => {
            logConsole(`[MAIN] Server Response: Job enqueued successfully. Queue ticket written.`, "success");
            
            // Mock-listen to the child OS process logging (using same timeouts as models.py sleep)
            setTimeout(() => {
                logConsole(`[WORKER] Received Job: send welcome email for ${email}`, "info");
                logConsole(`[WORKER] Simulating heavy background processing (takes 4 seconds)...`);
            }, 1000);

            setTimeout(() => {
                logConsole(`[WORKER] SUCCESS: Finished Job: send welcome email for ${email}`, "success");
            }, 5000);
        })
        .catch(err => {
            logConsole(`[ERROR] Failed to enqueue job: ${err.message}`, "danger");
        });

    formEnqueue.reset();
}

// Log Console Helper
function logConsole(text, type = "") {
    const line = document.createElement("div");
    line.className = "log-line";
    if (type === "success") line.classList.add("log-line-success");
    if (type === "info") line.classList.add("log-line-info");
    if (type === "danger") line.style.color = "#ef4444";
    
    const timestamp = new Date().toLocaleTimeString();
    line.textContent = `[${timestamp}] ${text}`;
    
    consoleLogs.appendChild(line);
    consoleLogs.scrollTop = consoleLogs.scrollHeight; // Auto-scroll
}
