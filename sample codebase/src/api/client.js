const API_BASE_URL = 'http://localhost:8000';

class ApiClient {
  async get(endpoint) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  async post(endpoint, data) {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  }

  // API methods
  async getMetrics() {
    return this.get('/metrics');
  }

  async getRecommendations(userId, nRecommendations = 10) {
    return this.get(`/recommendations/${userId}?n_recommendations=${nRecommendations}`);
  }

  async getDeadStockRisk() {
    return this.get('/dead_stock_risk');
  }

  async updateDiscounts() {
    return this.post('/update_discounts');
  }

  async healthCheck() {
    return this.get('/health');
  }
}

export default new ApiClient();