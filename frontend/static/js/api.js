/**
 * SmartFeeder EMS - Authentication API Service
 * Handles communication with the backend authentication endpoints.
 * Never stores plaintext credentials or secret tokens on the frontend.
 */
(function(window) {
  'use strict';

  const AuthApi = {
    /**
     * Authenticates user against backend API.
     * @param {string} username 
     * @param {string} password 
     * @returns {Promise<{success: boolean, message?: string, error?: string, redirect?: string}>}
     */
    async login(username, password) {
      try {
        const response = await fetch('/api/auth/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({
            username: username,
            password: password
          })
        });

        let data = {};
        try {
          data = await response.json();
        } catch (jsonErr) {
          return {
            success: false,
            error: 'Invalid response from authentication server.'
          };
        }

        if (!response.ok) {
          return {
            success: false,
            error: data.error || 'Invalid username or password.'
          };
        }

        return data;
      } catch (networkError) {
        return {
          success: false,
          error: 'Unable to connect to the authentication service. Please try again.'
        };
      }
    },

    /**
     * Terminates the current authenticated session.
     * @returns {Promise<{success: boolean}>}
     */
    async logout() {
      try {
        const response = await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Accept': 'application/json'
          }
        });
        return await response.json();
      } catch (err) {
        return { success: false, error: 'Network error during logout.' };
      }
    },

    /**
     * Retrieves current session information.
     */
    async getMe() {
      try {
        const response = await fetch('/api/auth/me', {
          headers: { 'Accept': 'application/json' }
        });
        return await response.json();
      } catch (err) {
        return { success: false, error: 'Unable to fetch session status.' };
      }
    }
  };

  const DashboardApi = {
    /**
     * Fetches live Home Dashboard telemetry.
     */
    async getHomeLive() {
      const response = await fetch('/api/dashboard/live', {
        headers: { 'Accept': 'application/json' }
      });
      return await response.json();
    },

    /**
     * Fetches live BUS-1 Detailed Dashboard telemetry.
     */
    async getBus1Live() {
      const response = await fetch('/api/bus/1/live', {
        headers: { 'Accept': 'application/json' }
      });
      return await response.json();
    },

    /**
     * Fetches live BUS-2 Detailed Dashboard telemetry.
     */
    async getBus2Live() {
      const response = await fetch('/api/bus/2/live', {
        headers: { 'Accept': 'application/json' }
      });
      return await response.json();
    }
  };

  window.AuthApi = AuthApi;
  window.DashboardApi = DashboardApi;
})(window);
