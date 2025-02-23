
const API_URL = "https://backend.inboxai.tech";

export const gmailService = {
  async getGmailAuthLink() {
    const response = await fetch(`${API_URL}/api/getgmaillink`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get Gmail authorization link');
    }
    
    return response.json();
  },

  async saveGoogleToken(authUrl: string) {
    const response = await fetch(`${API_URL}/api/savegoogletoken`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        auth_url: authUrl,
      }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to save Google token');
    }
    
    return response.json();
  },
};
