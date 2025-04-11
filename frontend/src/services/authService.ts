
const API_URL = "https://backend.inboxai.tech";
interface AuthCredentials {
  username: string;
  password: string;
}

export const authService = {
  async register(credentials: AuthCredentials) {
    const response = await fetch(`${API_URL}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    });
    return response;
  },

  async login(credentials: AuthCredentials) {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
    });
    return response;
  },

  async logout() {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/auth/logout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    localStorage.removeItem('token');
    return response;
  },

  async validateToken() {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/auth/validate-token`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    return response;
  }
};
