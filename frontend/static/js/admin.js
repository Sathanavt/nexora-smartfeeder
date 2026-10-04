/**
 * SmartFeeder EMS — Admin Control Page Controller
 * Handles user management, credential changes, modals, and notifications.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // DOM Elements
  const usersTableBody = document.getElementById('usersTableBody');
  const userCountBadge = document.getElementById('userCountBadge');
  const alertBanner = document.getElementById('adminAlertBanner');
  const alertMsg = document.getElementById('adminAlertMsg');
  const closeAlertBtn = document.getElementById('closeAlertBtn');

  // Modals
  const addUserModal = document.getElementById('addUserModal');
  const editUserModal = document.getElementById('editUserModal');
  const resetPasswordModal = document.getElementById('resetPasswordModal');

  // Forms
  const addUserForm = document.getElementById('addUserForm');
  const editUserForm = document.getElementById('editUserForm');
  const resetPasswordForm = document.getElementById('resetPasswordForm');
  const adminPasswordForm = document.getElementById('adminPasswordForm');

  // Modal open buttons
  const openAddUserModalBtn = document.getElementById('openAddUserModalBtn');

  // Modal close triggers
  document.querySelectorAll('[data-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-close');
      const targetModal = document.getElementById(modalId);
      if (targetModal) targetModal.style.display = 'none';
    });
  });

  // Close modals when clicking backdrop
  [addUserModal, editUserModal, resetPasswordModal].forEach(modal => {
    modal?.addEventListener('click', (e) => {
      if (e.target === modal) modal.style.display = 'none';
    });
  });

  // ==========================================================
  // Notifications
  // ==========================================================
  function showAlert(message, type = 'success') {
    if (!alertBanner || !alertMsg) return;
    alertMsg.textContent = message;
    alertBanner.className = `admin-alert-banner ${type}`;
    alertBanner.style.display = 'flex';
    // Auto-scroll to alert if needed
    alertBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  closeAlertBtn?.addEventListener('click', () => {
    if (alertBanner) alertBanner.style.display = 'none';
  });

  // ==========================================================
  // Fetch and Render Users
  // ==========================================================
  async function loadUsers() {
    try {
      const res = await fetch('/api/admin/users', {
        headers: { 'Accept': 'application/json' }
      });

      if (!res.ok) {
        if (res.status === 403 || res.status === 401) {
          window.location.href = '/';
          return;
        }
        throw new Error('Failed to load user list.');
      }

      const data = await res.json();
      if (!data.success || !data.users) {
        throw new Error(data.error || 'Unable to retrieve users.');
      }

      renderUsersTable(data.users);
      if (userCountBadge) {
        userCountBadge.textContent = `${data.users.length} Authorized Account${data.users.length === 1 ? '' : 's'}`;
      }

    } catch (err) {
      if (usersTableBody) {
        usersTableBody.innerHTML = `<tr><td colspan="4" class="td-loading" style="color: var(--error-text);">${err.message}</td></tr>`;
      }
    }
  }

  function renderUsersTable(users) {
    if (!usersTableBody) return;
    if (users.length === 0) {
      usersTableBody.innerHTML = '<tr><td colspan="4" class="td-loading">No users found.</td></tr>';
      return;
    }

    usersTableBody.innerHTML = '';
    users.forEach(u => {
      const tr = document.createElement('tr');

      const isStatusActive = (u.status || 'ACTIVE').toUpperCase() === 'ACTIVE';
      const role = (u.role || 'USER').toUpperCase();

      tr.innerHTML = `
        <td class="td-username">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          <span>${escapeHtml(u.username)}</span>
        </td>
        <td>
          <span class="role-badge ${role === 'ADMIN' ? 'role-admin' : 'role-user'}">${role}</span>
        </td>
        <td>
          <span class="status-pill ${isStatusActive ? 'active' : 'disabled'}">
            <span class="status-dot"></span>
            <span>${isStatusActive ? 'Active' : 'Disabled'}</span>
          </span>
        </td>
        <td>
          <div class="action-btn-group">
            <button class="btn-action-small btn-edit" data-id="${u.id}" data-username="${escapeHtml(u.username)}" data-role="${role}" data-status="${u.status}">Edit</button>
            <button class="btn-action-small btn-password" data-id="${u.id}" data-username="${escapeHtml(u.username)}">Password</button>
            <button class="btn-action-small ${isStatusActive ? 'btn-toggle-disable' : 'btn-toggle-enable'}" data-id="${u.id}" data-action="${isStatusActive ? 'disable' : 'enable'}">${isStatusActive ? 'Disable' : 'Enable'}</button>
            <button class="btn-action-small btn-delete" data-id="${u.id}" data-username="${escapeHtml(u.username)}">Delete</button>
          </div>
        </td>
      `;

      usersTableBody.appendChild(tr);
    });

    bindTableActionEvents();
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, m => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  // ==========================================================
  // Table Row Actions (Edit, Password, Toggle Status, Delete)
  // ==========================================================
  function bindTableActionEvents() {
    // Edit buttons
    document.querySelectorAll('.btn-edit').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const username = btn.getAttribute('data-username');
        const role = btn.getAttribute('data-role');
        const status = btn.getAttribute('data-status');

        document.getElementById('editUserId').value = id;
        document.getElementById('editUsername').value = username;
        document.getElementById('editUserRole').value = role;
        document.getElementById('editUserStatus').value = status;

        if (editUserModal) editUserModal.style.display = 'flex';
      });
    });

    // Password reset buttons
    document.querySelectorAll('.btn-password').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.getAttribute('data-id');
        const username = btn.getAttribute('data-username');

        document.getElementById('resetUserId').value = id;
        document.getElementById('resetTargetUsername').textContent = username;
        document.getElementById('resetNewPassword').value = '';
        document.getElementById('resetConfirmPassword').value = '';

        if (resetPasswordModal) resetPasswordModal.style.display = 'flex';
      });
    });

    // Enable/Disable buttons
    document.querySelectorAll('.btn-toggle-disable, .btn-toggle-enable').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        const action = btn.getAttribute('data-action');
        const newStatus = action === 'disable' ? 'DISABLED' : 'ACTIVE';

        try {
          btn.disabled = true;
          const res = await fetch(`/api/admin/users/${id}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ status: newStatus })
          });

          const data = await res.json();
          if (!res.ok || !data.success) {
            throw new Error(data.error || 'Failed to update account status.');
          }

          showAlert(data.message, 'success');
          loadUsers();
        } catch (err) {
          showAlert(err.message, 'error');
        } finally {
          btn.disabled = false;
        }
      });
    });

    // Delete buttons
    document.querySelectorAll('.btn-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        const username = btn.getAttribute('data-username');

        if (!confirm(`Are you sure you want to permanently remove user "${username}"?`)) {
          return;
        }

        try {
          btn.disabled = true;
          const res = await fetch(`/api/admin/users/${id}`, {
            method: 'DELETE',
            headers: { 'Accept': 'application/json' }
          });

          const data = await res.json();
          if (!res.ok || !data.success) {
            throw new Error(data.error || 'Failed to remove user.');
          }

          showAlert(data.message, 'success');
          loadUsers();
        } catch (err) {
          showAlert(err.message, 'error');
        } finally {
          btn.disabled = false;
        }
      });
    });
  }

  // ==========================================================
  // Form Submissions
  // ==========================================================

  // 1. Add User
  openAddUserModalBtn?.addEventListener('click', () => {
    addUserForm.reset();
    if (addUserModal) addUserModal.style.display = 'flex';
  });

  addUserForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('newUsername').value.trim();
    const password = document.getElementById('newUserPassword').value;
    const confirmPassword = document.getElementById('newUserConfirmPassword').value;
    const role = document.getElementById('newUserRole').value;
    const status = document.getElementById('newUserStatus').value;

    if (password !== confirmPassword) {
      showAlert('Password confirmation does not match.', 'error');
      return;
    }

    const saveBtn = document.getElementById('saveNewUserBtn');
    try {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Creating...';

      const res = await fetch('/api/admin/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({
          username, password, confirm_password: confirmPassword, role, status
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Unable to create user.');
      }

      if (addUserModal) addUserModal.style.display = 'none';
      showAlert(data.message || 'User created successfully.', 'success');
      loadUsers();
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Create Account';
    }
  });

  // 2. Edit User
  editUserForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('editUserId').value;
    const username = document.getElementById('editUsername').value.trim();
    const role = document.getElementById('editUserRole').value;
    const status = document.getElementById('editUserStatus').value;

    const saveBtn = document.getElementById('saveEditUserBtn');
    try {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Saving...';

      const res = await fetch(`/api/admin/users/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ username, role, status })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Unable to update user.');
      }

      if (editUserModal) editUserModal.style.display = 'none';
      showAlert(data.message || 'User details updated successfully.', 'success');
      loadUsers();
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Changes';
    }
  });

  // 3. Reset Password
  resetPasswordForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('resetUserId').value;
    const newPassword = document.getElementById('resetNewPassword').value;
    const confirmPassword = document.getElementById('resetConfirmPassword').value;

    if (newPassword !== confirmPassword) {
      showAlert('Password confirmation does not match.', 'error');
      return;
    }

    const saveBtn = document.getElementById('saveResetPasswordBtn');
    try {
      saveBtn.disabled = true;
      saveBtn.textContent = 'Updating...';

      const res = await fetch(`/api/admin/users/${id}/password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ new_password: newPassword, confirm_password: confirmPassword })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Unable to reset password.');
      }

      if (resetPasswordModal) resetPasswordModal.style.display = 'none';
      showAlert(data.message || 'Password updated successfully.', 'success');
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Reset Password';
    }
  });

  // 4. Admin Self-Management Password Change
  adminPasswordForm?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const currentPassword = document.getElementById('currentAdminPassword').value;
    const newPassword = document.getElementById('newAdminPassword').value;
    const confirmPassword = document.getElementById('confirmAdminPassword').value;

    if (newPassword !== confirmPassword) {
      showAlert('New password confirmation does not match.', 'error');
      return;
    }

    const submitBtn = document.getElementById('submitAdminPasswordBtn');
    try {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Verifying & Updating...';

      const res = await fetch('/api/admin/account/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
          confirm_password: confirmPassword
        })
      });

      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || 'Unable to change admin password.');
      }

      adminPasswordForm.reset();
      showAlert(data.message || 'Admin password changed successfully.', 'success');
    } catch (err) {
      showAlert(err.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Change Password';
    }
  });

  // Initial load
  loadUsers();
});
