/**
 * Relink AI - Frontend API Client
 */
const API_BASE = window.location.origin;

export const API = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/api/health`);
    return res.json();
  },

  async getStats() {
    const res = await fetch(`${API_BASE}/api/claims/stats/summary`);
    return res.json();
  },

  async getAiStatus() {
    const res = await fetch(`${API_BASE}/api/ai/status`);
    return res.json();
  },

  async updateApiKey(apiKey) {
    const formData = new FormData();
    formData.append("api_key", apiKey);
    const res = await fetch(`${API_BASE}/api/ai/config`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to update Gemini API key");
    }
    return res.json();
  },

  async getItems({ type = null, category = null, status = null, search = null } = {}) {
    const params = new URLSearchParams();
    if (type) params.append("type", type);
    if (category) params.append("category", category);
    if (status) params.append("status", status);
    if (search) params.append("search", search);

    const res = await fetch(`${API_BASE}/api/items?${params.toString()}`);
    return res.json();
  },

  async getItem(id) {
    const res = await fetch(`${API_BASE}/api/items/${id}`);
    if (!res.ok) throw new Error("Item not found");
    return res.json();
  },

  async createLostItem(formData) {
    const res = await fetch(`${API_BASE}/api/items/lost`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to submit lost item");
    }
    return res.json();
  },

  async createFoundItem(formData) {
    const res = await fetch(`${API_BASE}/api/items/found`, {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to submit found item");
    }
    return res.json();
  },

  async getMatches(minScore = 0.40) {
    const res = await fetch(`${API_BASE}/api/matches?min_score=${minScore}`);
    return res.json();
  },

  async recalculateMatches() {
    const res = await fetch(`${API_BASE}/api/matches/recalculate`, {
      method: "POST"
    });
    return res.json();
  },


  async generateClaimQuestions(lostDesc, foundDesc, category) {
    const formData = new FormData();
    formData.append("lost_description", lostDesc);
    formData.append("found_description", foundDesc);
    formData.append("category", category);
    const res = await fetch(`${API_BASE}/api/ai/generate-claim-questions`, {
      method: "POST",
      body: formData
    });
    return res.json();
  },

  async submitClaim(claimData) {
    const res = await fetch(`${API_BASE}/api/claims`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(claimData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to submit claim");
    }
    return res.json();
  },

  async approveClaim(claimId) {
    const res = await fetch(`${API_BASE}/api/claims/${claimId}/approve`, {
      method: "PATCH"
    });
    return res.json();
  },

  async rejectClaim(claimId) {
    const res = await fetch(`${API_BASE}/api/claims/${claimId}/reject`, {
      method: "PATCH"
    });
    return res.json();
  },

  async getClaims() {
    const res = await fetch(`${API_BASE}/api/claims`);
    return res.json();
  },

  async getClaimsForMatch(matchId) {
    const res = await fetch(`${API_BASE}/api/claims/match/${matchId}`);
    return res.json();
  }
};
