
// Check Auth first
const token = localStorage.getItem('access_token');
if (!token) {
    window.location.href = '/static/login.html';
}

const API_BASE = '/auth';

// Helper for Fetch
async function apiCall(endpoint, options = {}) {
    options.headers = options.headers || {};
    options.headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(endpoint, options);
    if (res.status === 401) {
        window.location.href = '/static/login.html';
        return;
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'API Error');
    return data;
}

// Elements
const tableBody = document.getElementById('userTableBody');
const userModal = document.getElementById('userModal');
const userForm = document.getElementById('userForm');
const modalTitle = document.getElementById('modalTitle');
const resetPwdModal = document.getElementById('resetPwdModal');
const resetPwdForm = document.getElementById('resetPwdForm');

// State
let isEditing = false;
let users = [];

// Init
document.addEventListener('DOMContentLoaded', loadUsers);

// Load Users
async function loadUsers() {
    try {
        users = await apiCall(`${API_BASE}/users`);
        renderTable();
    } catch (err) {
        alert("Failed to load users: " + err.message);
    }
}

// Render Table
function renderTable() {
    tableBody.innerHTML = '';
    users.forEach(user => {
        const tr = document.createElement('tr');
        const roleBadge = user.role === 'admin' ? '<span style="color:var(--primary-color)">Admin</span>' : 'User';
        const statusBadge = user.is_active ?
            '<span class="status-badge status-active">Active</span>' :
            '<span class="status-badge status-inactive">Inactive</span>';

        tr.innerHTML = `
            <td>#${user.id}</td>
            <td>
                <div style="display:flex; align-items:center; gap:8px;">
                    <div class="avatar" style="width:24px;height:24px;font-size:10px;">${user.username[0].toUpperCase()}</div>
                    ${user.username}
                </div>
            </td>
            <td>${roleBadge}</td>
            <td>${user.email || '<span style="color:var(--text-dim)">-</span>'}</td>
            <td>${statusBadge}</td>
            <td>
                <button class="action-btn" onclick="openEdit(${user.id})">Edit</button>
                <button class="action-btn" onclick="openResetPwd(${user.id})">Reset Pwd</button>
                ${user.username !== 'admin' ? `<button class="action-btn btn-danger" onclick="deleteUser(${user.id})">Delete</button>` : ''}
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

// Open Modal for Add
document.getElementById('btnAddNew').addEventListener('click', () => {
    isEditing = false;
    modalTitle.textContent = "Add New User";
    userForm.reset();
    userForm.querySelector('[name=username]').disabled = false;
    userForm.querySelector('[name=password]').required = true;
    // Unhide password note for edit only, but for add we need pw
    document.getElementById('passwordGroup').style.display = 'block';

    userModal.style.display = 'flex';
});

// Open Modal for Edit
window.openEdit = (id) => {
    const user = users.find(u => u.id === id);
    if (!user) return;

    isEditing = true;
    modalTitle.textContent = "Edit User";
    userForm.id.value = user.id;
    userForm.username.value = user.username;
    userForm.username.disabled = true; // Cannot change username
    userForm.email.value = user.email || '';
    userForm.role.value = user.role;
    userForm.is_active.checked = user.is_active;
    userForm.password.value = '';
    userForm.password.required = false; // Optional in edit

    // Admin cannot deactivate themselves (simple client check)
    // if (user.username === 'admin') ...

    userModal.style.display = 'flex';
};

// Handle User Form Submit
userForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(userForm);
    const data = Object.fromEntries(formData.entries());

    // Checkbox handling
    data.is_active = userForm.is_active.checked;

    try {
        if (isEditing) {
            // Update
            const userId = data.id;
            // Password is NOT updated here normally for REST, but let's see schemas.
            // Our Schema UserUpdate doesn't have password. Reset Pwd is separate.
            // So we ignore password field here for Edit.
            const updatePayload = {
                email: data.email || null,
                role: data.role,
                is_active: data.is_active
            };

            await apiCall(`${API_BASE}/users/${userId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(updatePayload)
            });
        } else {
            // Create
            if (!data.password) throw new Error("Password is required for new user");
            await apiCall(`${API_BASE}/users`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        closeModal();
        loadUsers();
    } catch (err) {
        alert(err.message);
    }
});

// Delete User
window.deleteUser = async (id) => {
    if (!confirm("Are you sure you want to delete this user? This cannot be undone.")) return;
    try {
        await apiCall(`${API_BASE}/users/${id}`, { method: 'DELETE' });
        loadUsers();
    } catch (err) {
        alert(err.message);
    }
};

// Reset Password
window.openResetPwd = (id) => {
    resetPwdForm.user_id.value = id;
    resetPwdForm.new_password.value = '';
    resetPwdModal.style.display = 'flex';
};

resetPwdForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userId = resetPwdForm.user_id.value;
    const newPass = resetPwdForm.new_password.value;

    try {
        await apiCall(`${API_BASE}/users/${userId}/reset_password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPass })
        });
        alert("Password reset successfully");
        resetPwdModal.style.display = 'none';
    } catch (err) {
        alert(err.message);
    }
});

function closeModal() {
    userModal.style.display = 'none';
}
window.closeModal = closeModal;
