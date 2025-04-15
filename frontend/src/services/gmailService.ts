
const API_URL = "https://backend.inboxai.tech";

export interface ConnectedEmail {
  email: string;
  total_emails_processed: number;
  last_refresh: string;
  connected_since: string;
  current_run_status: string;
  expires_at: string;
  refresh_token: string;
}

export interface ConnectedEmailsResponse {
  accounts: ConnectedEmail[];
  total_accounts: number;
}
export interface FetchAndRefreshEmailRequest {
  emails: string[];
}

export interface ChatInferenceRequest {
  query: string;
}

export interface ChatInferenceResponse {
  id: string;
  answer: string;
}

export interface InferenceFeedbackRequest {
  responseId: string;
  feedback: 'yes' | 'no';
}

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
  async getConnectedAccounts(): Promise<ConnectedEmailsResponse> {
    const response = await fetch(`${API_URL}/api/getconnectedaccounts`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get connected accounts');
    }
    
    return response.json();
  },

  async fetchAndRefreshEmail(emails: string[]) {
    const response = await fetch(`${API_URL}/api/fetchandrefreshemail`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ emails }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to refresh emails');
    }
    
    return response.json();
  },

  async removeEmail(email: string) {
    const response = await fetch(`${API_URL}/api/removeemail`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to remove email');
    }
    
    return response.json();
  },

  async getInference(query: string): Promise<ChatInferenceResponse>  {
    const response = await fetch(`${API_URL}/api/getinference`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to get inference');
    }
    
    return response.json();
  },

  async sendInferenceFeedback(responseId: string, feedback: 'yes' | 'no') {
    const response = await fetch(`${API_URL}/api/inferencefeedback`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ responseId, feedback }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to send inference feedback');
    }
    
    return response.json();
  }
};
