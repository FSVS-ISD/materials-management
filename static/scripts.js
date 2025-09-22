const users = [
  { username: "admin", role: "admin", page: "admin-login.html", label: "系統管理員" },
  { username: "dep-admin", role: "admin", page: "dep-admin.html", label: "部門管理員" },
  { username: "dep1", role: "user", page: "Department1-login.html", label: "商經科" },
  { username: "dep2", role: "user", page: "Department2-login.html", label: "會事科" },
  { username: "dep3", role: "user", page: "Department3-login.html", label: "國貿科" },
  { username: "dep4", role: "user", page: "Department4-login.html", label: "觀光科" },
  { username: "dep5", role: "user", page: "Department5-login.html", label: "資處科" },
  { username: "dep6", role: "user", page: "Department6-login.html", label: "機械科" },
  { username: "dep7", role: "user", page: "Department7-login.html", label: "電圖科" },
  { username: "dep8", role: "user", page: "Department8-login.html", label: "室設科" },
  { username: "dep9", role: "user", page: "Department9-login.html", label: "家設科" },
  { username: "dep1T", role: "query", page: "Department1-report-management.html", linkedUser: "dep1", label: "商經科(查詢)" },
  { username: "dep2T", role: "query", page: "Department2-report-management.html", linkedUser: "dep2", label: "會事科(查詢)" },
  { username: "dep3T", role: "query", page: "Department3-report-management.html", linkedUser: "dep3", label: "國貿科(查詢)" },
  { username: "dep4T", role: "query", page: "Department4-report-management.html", linkedUser: "dep4", label: "觀光科(查詢)" },
  { username: "dep5T", role: "query", page: "Department5-report-management.html", linkedUser: "dep5", label: "資處科(查詢)" },
  { username: "dep6T", role: "query", page: "Department6-report-management.html", linkedUser: "dep6", label: "機械科(查詢)" },
  { username: "dep7T", role: "query", page: "Department7-report-management.html", linkedUser: "dep7", label: "電圖科(查詢)" },
  { username: "dep8T", role: "query", page: "Department8-report-management.html", linkedUser: "dep8", label: "室設科(查詢)" },
  { username: "dep9T", role: "query", page: "Department9-report-management.html", linkedUser: "dep9", label: "家設科(查詢)" }
];

const userGrid = document.getElementById("userGrid");
const messageDiv = document.getElementById("message");
const adminMessage = document.getElementById("adminMessage");
const loginForm = document.getElementById("loginForm");
const adminSection = document.getElementById("adminSection");
const devModeNotice = document.getElementById("devModeNotice");

let devModeEnabled = false;
let currentUser = null;
let msgTimeout;

function showMessage(element, message, isSuccess) {
  clearTimeout(msgTimeout);
  element.textContent = message;
  element.className = "message " + (isSuccess ? "success" : "error");
  element.style.display = "block";
  msgTimeout = setTimeout(() => { element.style.display = "none"; }, 3000);
}

function renderUserCards(filter = "all") {
  userGrid.innerHTML = "";
  users.forEach(user => {
    if (filter !== "all" && user.role !== filter) return;
    const card = document.createElement("div");
    card.className = `user-card ${devModeEnabled ? "" : "disabled"}`;

    let iconClass = "fa-user";
    let avatarClass = "user";
    if (user.role === "admin") {
      iconClass = "fa-user-shield";
      avatarClass = "admin";
    } else if (user.role === "query") {
      iconClass = "fa-user-check";
      avatarClass = "query";
    }

    card.innerHTML = `
      <div class="avatar ${avatarClass}"><i class="fas ${iconClass}"></i></div>
      <h3>${user.label}</h3>
      <p>${user.username}</p>
    `;

    card.addEventListener("click", () => {
      if (!devModeEnabled) {
        showMessage(messageDiv, "請先啟用開發者模式 (****), 才能使用此功能", false);
        return;
      }
      if (user.role === "admin") {
        document.getElementById("username").value = user.username;
        document.getElementById("password").value = "";
        showMessage(messageDiv, `已填入帳號: ${user.username}`, true);
      } else {
        window.location.href = user.page;
      }
    });
    userGrid.appendChild(card);
  });
}

function enableDevMode() {
  devModeEnabled = true;
  devModeNotice.style.display = "block";
  renderUserCards();
}
function disableDevMode() {
  devModeEnabled = false;
  devModeNotice.style.display = "none";
  renderUserCards();
}

document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.key.toLowerCase() === "x") {
    e.preventDefault();
    devModeEnabled ? disableDevMode() : enableDevMode();
  }
});

document.getElementById("loginBtn").addEventListener("click", () => {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const found = users.find(u => u.username === username);
  if (!found) {
    showMessage(messageDiv, "用戶不存在", false);
    return;
  }
  currentUser = found;
  if (found.role === "admin") {
    loginForm.style.display = "none";
    adminSection.style.display = "block";
    showMessage(adminMessage, "管理員登入成功，請查看或修改用戶密碼", true);
  } else {
    window.location.href = found.page;
  }
});

document.getElementById("goAdminPageBtn").addEventListener("click", () => {
  if (currentUser) {
    window.location.href = currentUser.page;
  } else {
    alert("請先登入管理員帳號");
  }
});

document.getElementById("showAllBtn").onclick = () => {
  setActiveFilterBtn("showAllBtn");
  renderUserCards("all");
};
document.getElementById("showAdminBtn").onclick = () => {
  setActiveFilterBtn("showAdminBtn");
  renderUserCards("admin");
};
document.getElementById("showUserBtn").onclick = () => {
  setActiveFilterBtn("showUserBtn");
  renderUserCards("user");
};
document.getElementById("showQueryBtn").onclick = () => {
  setActiveFilterBtn("showQueryBtn");
  renderUserCards("query");
};

function setActiveFilterBtn(activeId) {
  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.classList.remove("active");
  });
  document.getElementById(activeId).classList.add("active");
}

renderUserCards();

// 瀏覽次數
(function() {
  const key = 'pageViewCount';
  let count = parseInt(localStorage.getItem(key)) || 0;
  count++;
  localStorage.setItem(key, count);
  document.getElementById('viewCount').textContent = `瀏覽次數: ${count} 人次`;
})();
