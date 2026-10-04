/**
 * SmartFeeder EMS - Login Page Controller
 * Handles client-side validation, UI state, eye icon toggling, and authentication requests.
 */
document.addEventListener('DOMContentLoaded', () => {
  'use strict';

  // DOM Elements
  const form = document.getElementById('loginForm');
  const usernameInput = document.getElementById('usernameInput');
  const passwordInput = document.getElementById('passwordInput');
  const togglePasswordBtn = document.getElementById('togglePasswordBtn');
  const eyeIconOpen = document.getElementById('eyeIconOpen');
  const eyeIconClosed = document.getElementById('eyeIconClosed');
  const submitBtn = document.getElementById('loginSubmitBtn');
  const submitBtnText = document.getElementById('loginBtnText');
  const authAlert = document.getElementById('authAlert');
  const authAlertMsg = document.getElementById('authAlertMsg');
  const groupUsername = document.getElementById('groupUsername');
  const groupPassword = document.getElementById('groupPassword');

  let isSubmitting = false;

  // Focus username on initial page load
  if (usernameInput) {
    usernameInput.focus();
  }

  // ==========================================================
  // Alert & Error Message Helpers
  // ==========================================================
  function showError(messages) {
    if (!authAlert || !authAlertMsg) return;
    
    // Normalize string or array of strings
    const text = Array.isArray(messages) ? messages.join('\n') : String(messages);
    authAlertMsg.textContent = text;
    authAlert.classList.add('visible');
  }

  function hideError() {
    if (!authAlert || !authAlertMsg) return;
    authAlert.classList.remove('visible');
    authAlertMsg.textContent = '';
    groupUsername?.classList.remove('has-error');
    groupPassword?.classList.remove('has-error');
  }

  // Clear errors when the user begins modifying inputs
  usernameInput?.addEventListener('input', () => {
    groupUsername?.classList.remove('has-error');
    if (authAlert.classList.contains('visible')) {
      hideError();
    }
  });

  passwordInput?.addEventListener('input', () => {
    groupPassword?.classList.remove('has-error');
    if (authAlert.classList.contains('visible')) {
      hideError();
    }
  });

  // ==========================================================
  // Show / Hide Password Toggle
  // ==========================================================
  if (togglePasswordBtn && passwordInput) {
    togglePasswordBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const isCurrentlyPassword = passwordInput.getAttribute('type') === 'password';

      if (isCurrentlyPassword) {
        passwordInput.setAttribute('type', 'text');
        togglePasswordBtn.setAttribute('aria-label', 'Hide password');
        if (eyeIconOpen) eyeIconOpen.style.display = 'none';
        if (eyeIconClosed) eyeIconClosed.style.display = 'block';
      } else {
        passwordInput.setAttribute('type', 'password');
        togglePasswordBtn.setAttribute('aria-label', 'Show password');
        if (eyeIconOpen) eyeIconOpen.style.display = 'block';
        if (eyeIconClosed) eyeIconClosed.style.display = 'none';
      }
      passwordInput.focus();
    });
  }

  // ==========================================================
  // Client-Side Validation
  // ==========================================================
  function validateForm(username, password) {
    const errors = [];

    if (!username || username.trim() === '') {
      errors.push('Username is required.');
      groupUsername?.classList.add('has-error');
    }

    if (!password || password.trim() === '') {
      errors.push('Password is required.');
      groupPassword?.classList.add('has-error');
    }

    return errors;
  }

  // ==========================================================
  // Form Submission & Authentication Handling
  // ==========================================================
  async function handleSubmit(event) {
    if (event) {
      event.preventDefault();
    }

    // Prevent duplicate simultaneous submissions
    if (isSubmitting) {
      return;
    }

    hideError();

    const username = usernameInput ? usernameInput.value : '';
    const password = passwordInput ? passwordInput.value : '';

    // Frontend validation
    const validationErrors = validateForm(username, password);
    if (validationErrors.length > 0) {
      showError(validationErrors);
      // Focus the first invalid input
      if (!username || username.trim() === '') {
        usernameInput?.focus();
      } else if (!password || password.trim() === '') {
        passwordInput?.focus();
      }
      return;
    }

    // Set processing state
    isSubmitting = true;
    submitBtn.disabled = true;
    submitBtn.classList.add('is-loading');
    submitBtnText.textContent = 'Authenticating...';

    try {
      const result = await window.AuthApi.login(username.trim(), password);

      if (result.success) {
        submitBtnText.textContent = 'Authenticated';
        // Redirect to protected home route
        const targetUrl = result.redirect || '/';
        window.location.href = targetUrl;
      } else {
        showError(result.error || 'Invalid username or password.');
        // Reset button state
        isSubmitting = false;
        submitBtn.disabled = false;
        submitBtn.classList.remove('is-loading');
        submitBtnText.textContent = 'LOGIN';
        passwordInput?.focus();
      }
    } catch (err) {
      showError('Unable to connect to the authentication service. Please try again.');
      isSubmitting = false;
      submitBtn.disabled = false;
      submitBtn.classList.remove('is-loading');
      submitBtnText.textContent = 'LOGIN';
    }
  }

  // Bind submit event
  form?.addEventListener('submit', handleSubmit);

  // Keyboard accessibility: Enter key on inputs submits form
  [usernameInput, passwordInput].forEach((input) => {
    input?.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSubmit(e);
      }
    });
  });
});
