
const API_URL = "https://test.inboxai.tech";

export interface ConnectedEmail {
  email: string;
  total_emails_processed: number;
  last_read: string;
  connected_since: string;
  run_status: string;
  expires_at: string;
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
  message_id: string;
  query: string;
  rag_id: string;
  response: string;
  response_time_ms: number;
  is_toxic: boolean;
}

export interface InferenceFeedbackRequest {
  responseId: string;
  feedback: 'yes' | 'no';
}
export interface RagSource {
  rag_id: string;
  name: string;
}

export interface ChatHistory {
  id: string;
  name: string;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  content: string;
  sender: 'user' | 'assistant';
  timestamp: string;
  feedbackStatus?: 'yes' | 'no';
  query?: string;
  response?: string;
  responseTimeMs?: number;
  ragId?: string;
}
export interface GetChatsResponse {
  chats: {
    chat_id: string;
    created_at: string;
    name: string;
  }[];
  total: number;
}
export interface GetMessagesResponse {
  chat_id: string;
  messages: {
    created_at: string;
    feedback: 'yes' | 'no' | null;
    message_id: string;
    query: string;
    rag_id?: string;
    response: string;
    response_time_ms: number;
    is_toxic: boolean;
  }[];
  total: number;
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
    const response = await fetch(`${API_URL}/api/refreshemails`, {
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

  async getInference(query: string, ragSourceId: string, chatId: string): Promise<ChatInferenceResponse> {
    const payload: any = {'query' : query, "rag_id":ragSourceId, "chat_id":chatId};
  
    const response = await fetch(`${API_URL}/api/getinference`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    
    if (!response.ok) {
      throw new Error('Failed to get inference');
    }
    
    return response.json();
  },

  async sendInferenceFeedback(message_id: string, feedback: 'yes' | 'no') {
    const response = await fetch(`${API_URL}/api/inferencefeedback`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message_id, feedback }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to send inference feedback');
    }
    
    return response.json();
  },
  
  async getRagSources(): Promise<RagSource[]> {
    const response = await fetch(`${API_URL}/api/ragsources`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get RAG sources');
    }
    
    const data = await response.json();
    
    return data.sources;
  },
  
  async getChats(): Promise<ChatHistory[]> {
    const response = await fetch(`${API_URL}/api/getchats`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get chat history');
    }
    
    const data: GetChatsResponse = await response.json();
    
    return data.chats.map(chat => ({
      id: chat.chat_id,
      name: chat.name,
      createdAt: chat.created_at
    }));
  },
  
  async getMessages(chatId: string): Promise<ChatMessage[]> {
    const response = await fetch(`${API_URL}/api/getmessages/${chatId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get chat messages');
    }
    const data: GetMessagesResponse = await response.json();

    const messages: ChatMessage[] = [];
    
    for (const msg of data.messages) {
      messages.push({
        id: `${msg.message_id}-user`,
        content: msg.query,
        sender: 'user',
        timestamp: msg.created_at,
        query: msg.query
      });
      
      messages.push({
        id: msg.message_id,
        content: msg.response,
        sender: 'assistant',
        timestamp: msg.created_at,
        feedbackStatus: msg.feedback,
        response: msg.response,
        responseTimeMs: msg.response_time_ms,
        ragId: msg.rag_id
      });
    }
    
    return messages;
  },
  
  async createChat(name?: string): Promise<{ chat_id: string; name: string }> {
    const response = await fetch(`${API_URL}/api/createchat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name }),
    });
    
    if (!response.ok) {
      throw new Error('Failed to create new chat');
    }
    
    return response.json();
  }
};