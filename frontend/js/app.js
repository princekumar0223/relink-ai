import { API } from "./api.js";
import { UI } from "./ui.js";

// Global App State
const state = {
  currentTab: "matches",
  items: [],
  matches: [],
  claims: [],
  stats: null,
  activeMatch: null,
  lostFiles: [],
  foundFiles: []
};

// Global Handler for Inspect Button
window.relinkOpenInspect = function(matchId) {
  const m = state.matches.find(x => x.id === matchId);
  if (m) {
    openInspectModal(m);
  } else {
    API.getMatches().then(list => {
      const found = list.find(x => x.id === matchId);
      if (found) openInspectModal(found);
    }).catch(err => {
      console.error(err);
      UI.showToast("Could not open match: " + err.message, "error");
    });
  }
};

// Initialize Application
document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  setupModals();
  setupForms();
  setupGeolocationDetectors();
  setupApiKeyManager();
  setupRewardManager();
  setupNotificationsManager();
  
  await refreshAll();
  
  // Set up periodic stats refresh (every 30 seconds)
  setInterval(refreshStatsOnly, 30000);
});

async function refreshAll() {
  await Promise.all([
    loadStats(),
    loadMatches(),
    loadItems(),
    loadClaims()
  ]);
}

async function refreshStatsOnly() {
  try {
    const stats = await API.getStats();
    state.stats = stats;
    updateStatsUI(stats);
  } catch (e) {
    console.warn("Stats refresh failed", e);
  }
}

function updateStatsUI(stats) {
  document.getElementById("stat-lost").textContent = stats.total_lost;
  document.getElementById("stat-found").textContent = stats.total_found;
  document.getElementById("stat-matches").textContent = stats.active_matches;
  document.getElementById("stat-reunited").textContent = stats.reunited_items;

  const rewardEl = document.getElementById("stat-rewards");
  if (rewardEl) {
    rewardEl.textContent = `₹${stats.total_reward_amount || 0}`;
  }

  const notifBadge = document.getElementById("nav-notifications-badge");
  if (notifBadge) {
    notifBadge.textContent = stats.total_notifications || 0;
  }

  // Pending claims badge
  const pendingPill = document.getElementById("nav-pending-claims-badge");
  if (pendingPill) {
    if (stats.pending_claims > 0) {
      pendingPill.textContent = stats.pending_claims;
      pendingPill.classList.remove("hidden");
    } else {
      pendingPill.classList.add("hidden");
    }
  }

  const aiBadge = document.getElementById("ai-status-badge");
  if (stats.gemini_ai_active) {
    aiBadge.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
      <span class="text-emerald-400 font-semibold text-xs">Gemini 3.8 Flash Online</span>
    `;
    aiBadge.className = "px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center gap-2 cursor-pointer";
  } else {
    aiBadge.innerHTML = `
      <span class="w-2 h-2 rounded-full bg-amber-400"></span>
      <span class="text-amber-400 font-semibold text-xs">Local Engine Active</span>
    `;
    aiBadge.className = "px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center gap-2 cursor-pointer";
  }
}

async function loadStats() {
  try {
    const stats = await API.getStats();
    state.stats = stats;
    updateStatsUI(stats);
  } catch (err) {
    console.error("Failed to load stats", err);
  }
}

async function loadMatches() {
  const container = document.getElementById("matches-grid");
  const emptyState = document.getElementById("matches-empty");
  try {
    const matches = await API.getMatches(0.40);
    state.matches = matches;
    container.innerHTML = "";

    if (!matches || matches.length === 0) {
      emptyState.classList.remove("hidden");
    } else {
      emptyState.classList.add("hidden");
      matches.forEach(m => {
        const card = UI.renderMatchCard(m, openInspectModal);
        container.appendChild(card);
      });
    }
  } catch (err) {
    console.error("Failed to load matches", err);
    UI.showToast("Could not load matches: " + err.message, "error");
  }
}

async function loadItems() {
  const container = document.getElementById("items-grid");
  try {
    const categoryFilter = document.getElementById("filter-category").value;
    const typeFilter = document.getElementById("filter-type").value;
    const searchFilter = document.getElementById("filter-search").value;

    const items = await API.getItems({
      category: categoryFilter,
      type: typeFilter,
      search: searchFilter
    });
    state.items = items;
    container.innerHTML = "";

    if (items.length === 0) {
      container.innerHTML = `
        <div class="col-span-full py-16 text-center glass-panel rounded-2xl p-8 border border-slate-800">
          <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-slate-900 flex items-center justify-center text-2xl">
            📦
          </div>
          <p class="text-sm font-semibold text-slate-300 mb-1">No items registered yet</p>
          <p class="text-xs text-slate-500">Items submitted will appear here for easy browsing and searching.</p>
        </div>
      `;
    } else {
      items.forEach(item => {
        const card = UI.renderItemCard(item, (selected) => {
          UI.showToast(`Selected "${selected.title}" (${selected.type})`, "info");
        });
        container.appendChild(card);
      });
    }
  } catch (err) {
    console.error("Failed to load items", err);
  }
}

async function loadClaims() {
  const container = document.getElementById("claims-container");
  const emptyState = document.getElementById("claims-empty");
  const countBadge = document.getElementById("claims-count-badge");
  if (!container) return;

  try {
    const claims = await API.getClaims();
    state.claims = claims;
    container.innerHTML = "";

    const pendingClaims = claims.filter(c => c.status === "pending");
    countBadge.textContent = `${pendingClaims.length} Pending / ${claims.length} Total`;

    if (!claims || claims.length === 0) {
      emptyState.classList.remove("hidden");
    } else {
      emptyState.classList.add("hidden");
      claims.forEach(claim => {
        const card = renderClaimCard(claim);
        container.appendChild(card);
      });
    }
  } catch (err) {
    console.error("Failed to load claims", err);
  }
}

function renderClaimCard(claim) {
  const card = document.createElement("div");
  card.className = "glass-panel rounded-2xl p-6 border transition-all duration-300 relative overflow-hidden " +
    (claim.status === 'approved' ? 'border-emerald-500/40 bg-emerald-950/20' : 
     (claim.status === 'rejected' ? 'border-rose-500/30 bg-rose-950/20' : 'border-purple-500/40 hover:border-purple-500/60'));

  const statusBadges = {
    pending: '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5"><span class="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span> Pending Founder Review</span>',
    approved: '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">✓ Verification Approved & Reunited</span>',
    rejected: '<span class="px-2.5 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">✕ Claim Rejected</span>'
  };

  const answersFormatted = claim.secret_verification_answer
    ? claim.secret_verification_answer.split("|").map((ans, idx) => `
        <div class="p-3 bg-purple-950/40 rounded-xl border border-purple-800/40 text-xs">
          <span class="font-bold text-purple-300 block mb-1">Challenge Answer #${idx + 1}:</span>
          <span class="text-slate-100">${ans.trim()}</span>
        </div>
      `).join("")
    : `<div class="text-xs text-slate-400 italic">No challenge answers recorded.</div>`;

  card.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4 pb-3 border-b border-slate-800">
      <div class="flex items-center gap-3">
        <span class="text-2xl">🛡️</span>
        <div>
          <h4 class="font-bold text-base text-white">Ownership Claim for Match #${claim.match_id}</h4>
          <p class="text-xs text-slate-400">Claimant: <strong class="text-slate-200">${claim.claimant_name}</strong> • ${claim.created_at}</p>
        </div>
      </div>
      <div>
        ${statusBadges[claim.status] || statusBadges.pending}
      </div>
    </div>

    <!-- Connected Items Banner -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
      <div class="p-3.5 bg-slate-900/80 rounded-xl border border-red-500/20">
        <span class="text-[10px] font-bold text-red-400 uppercase tracking-wider block mb-1">Lost Report</span>
        <h5 class="font-bold text-sm text-white">${claim.lost_title}</h5>
        <p class="text-xs text-slate-300 line-clamp-2 mt-1">${claim.lost_desc}</p>
      </div>

      <div class="p-3.5 bg-slate-900/80 rounded-xl border border-emerald-500/20">
        <span class="text-[10px] font-bold text-emerald-400 uppercase tracking-wider block mb-1">Found Report</span>
        <h5 class="font-bold text-sm text-white">${claim.found_title}</h5>
        <div class="mt-1 flex items-center justify-between text-xs text-emerald-300 font-semibold">
          <span>🏢 Safe Custody Location:</span>
          <span>${claim.custody_location || 'Campus Security Desk'}</span>
        </div>
      </div>
    </div>

    <!-- Owner Verification Answers Comparison Box -->
    <div class="p-4 bg-slate-950/70 rounded-xl border border-slate-800 mb-4 space-y-3">
      <h5 class="text-xs font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
        <span>🔍 Owner's Verification Answers (Compare with Found Item Details)</span>
      </h5>
      <div class="space-y-2">
        ${answersFormatted}
      </div>

      ${claim.proof_details ? `
        <div class="p-3 bg-slate-900/70 rounded-xl border border-slate-800 text-xs">
          <span class="font-bold text-slate-300 block mb-1">Additional Secret Proof Provided by Owner:</span>
          <span class="text-slate-200">${claim.proof_details}</span>
        </div>
      ` : ''}
    </div>

    <!-- Contact & Action Toolbar -->
    <div class="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-slate-800">
      <div class="text-xs text-slate-400 space-y-0.5">
        <div>👤 <strong>Owner Contact:</strong> <span class="text-slate-200">${claim.claimant_name}</span> (<span class="text-purple-300">${claim.claimant_contact}</span>)</div>
        <div>🏢 <strong>Custodian:</strong> <span class="text-slate-200">${claim.founder_name || 'Campus Security'}</span> (${claim.custody_location || 'Security Office'})</div>
      </div>

      ${claim.status === 'pending' ? `
        <div class="flex items-center gap-2.5">
          <button class="btn-reject-claim px-4 py-2 bg-slate-800 hover:bg-rose-900/40 text-rose-300 border border-slate-700 hover:border-rose-500/40 font-semibold text-xs rounded-xl transition-all">
            ✕ Reject Claim
          </button>
          <button class="btn-approve-claim px-5 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-emerald-600/30 flex items-center gap-1.5 transition-all">
            <span>✓ Approve & Release Item</span>
          </button>
        </div>
      ` : (claim.status === 'approved' ? `
        <div class="flex flex-wrap items-center gap-2.5">
          <span class="text-xs font-semibold text-emerald-400">🎉 Item Reunited!</span>
          ${claim.reward_amount && claim.reward_amount > 0 ? `
            <div class="flex items-center gap-2">
              <span class="px-3 py-1.5 rounded-xl bg-amber-950/60 border border-amber-500/40 text-amber-300 font-bold text-xs flex items-center gap-1.5 shadow">
                <span>🎁 Reward Paid: ₹${claim.reward_amount}</span>
              </span>
              ${claim.reward_note ? `<span class="text-xs text-slate-300 italic">"${claim.reward_note}"</span>` : ''}
            </div>
          ` : `
            <button class="btn-reward-founder px-3.5 py-1.5 bg-gradient-to-r from-amber-600 to-yellow-600 hover:from-amber-500 hover:to-yellow-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-amber-600/30 flex items-center gap-1.5 transition-all">
              <span>🎁 Give Reward to Founder</span>
            </button>
          `}
        </div>
      ` : `
        <div class="text-xs font-semibold text-slate-500">
          Claim decision archived.
        </div>
      `)}
    </div>
  `;

  // Attach Approve & Reject Handlers
  const approveBtn = card.querySelector(".btn-approve-claim");
  if (approveBtn) {
    approveBtn.addEventListener("click", async () => {
      approveBtn.disabled = true;
      approveBtn.textContent = "Approving...";
      try {
        await API.approveClaim(claim.id);
        UI.showToast("Verification Approved! Items officially marked as REUNITED!", "success");
        await refreshAll();
      } catch (e) {
        UI.showToast("Approval failed: " + e.message, "error");
        approveBtn.disabled = false;
      }
    });
  }

  const rejectBtn = card.querySelector(".btn-reject-claim");
  if (rejectBtn) {
    rejectBtn.addEventListener("click", async () => {
      rejectBtn.disabled = true;
      try {
        await API.rejectClaim(claim.id);
        UI.showToast("Claim rejected.", "info");
        await refreshAll();
      } catch (e) {
        UI.showToast("Rejection failed: " + e.message, "error");
        rejectBtn.disabled = false;
      }
    });
  }

  const rewardBtn = card.querySelector(".btn-reward-founder");
  if (rewardBtn) {
    rewardBtn.addEventListener("click", () => {
      openRewardModal(claim);
    });
  }

  return card;
}

// Navigation Tabs
function setupNavigation() {
  const navButtons = document.querySelectorAll(".nav-tab-btn");
  navButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      switchTab(target);
    });
  });

  const syncBtn = document.getElementById("btn-recalculate");
  if (syncBtn) {
    syncBtn.addEventListener("click", async () => {
      UI.showToast("Synchronizing AI Matches...", "info");
      try {
        const res = await API.recalculateMatches();
        UI.showToast(`Sync complete! ${res.matches_evaluated_or_updated} pairs checked.`, "success");
        await refreshAll();
      } catch (err) {
        UI.showToast("Sync error: " + err.message, "error");
      }
    });
  }

  // Filters change listener
  ["filter-category", "filter-type", "filter-search"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", debounce(loadItems, 300));
    }
  });
}

function switchTab(tabName) {
  state.currentTab = tabName;
  document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.add("hidden"));
  document.querySelectorAll(".nav-tab-btn").forEach(btn => {
    if (btn.dataset.tab === tabName) {
      btn.classList.add("bg-purple-600/20", "text-purple-300", "border-purple-500/40");
      btn.classList.remove("text-slate-400", "border-transparent");
    } else {
      btn.classList.remove("bg-purple-600/20", "text-purple-300", "border-purple-500/40");
      btn.classList.add("text-slate-400", "border-transparent");
    }
  });

  const activePane = document.getElementById(`tab-${tabName}`);
  if (activePane) activePane.classList.remove("hidden");

  if (tabName === "claims") {
    loadClaims();
  }
}

// Geolocation Auto-Detection
function setupGeolocationDetectors() {
  const bindDetector = (btnId, latId, lonId, textId, inputNameId) => {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    btn.addEventListener("click", () => {
      if (!navigator.geolocation) {
        UI.showToast("Geolocation is not supported by your browser.", "warning");
        return;
      }

      btn.disabled = true;
      btn.innerHTML = `<span>⏳ Detecting...</span>`;

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const lat = position.coords.latitude;
          const lon = position.coords.longitude;

          document.getElementById(latId).value = lat.toFixed(6);
          document.getElementById(lonId).value = lon.toFixed(6);
          document.getElementById(textId).textContent = `${lat.toFixed(4)}° N, ${lon.toFixed(4)}° E (GPS Verified)`;

          // Reverse geocoding lookup
          try {
            const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`);
            const data = await res.json();
            const nameInput = document.getElementById(inputNameId);
            if (data && data.display_name && nameInput && !nameInput.value.trim()) {
              nameInput.value = data.display_name.split(",").slice(0, 3).join(", ");
            }
          } catch (e) {
            // Silently maintain coordinates
          }

          btn.disabled = false;
          btn.innerHTML = `<span>✓ Location Captured</span>`;
          UI.showToast("Exact GPS coordinates captured!", "success");
        },
        (error) => {
          btn.disabled = false;
          btn.innerHTML = `<span>📍 Detect My Location</span>`;
          UI.showToast("Location access denied or unavailable. You can enter landmark name manually.", "warning");
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    });
  };

  bindDetector("btn-lost-detect-gps", "lost-lat", "lost-lon", "lost-coords-text", "lost-location-name");
  bindDetector("btn-found-detect-gps", "found-lat", "found-lon", "found-coords-text", "found-location-name");
}

// Helper: render gallery thumbnails
function renderGalleryToContainer(imgPathsString, galleryContainerId, mainImgId) {
  const container = document.getElementById(galleryContainerId);
  const mainImg = document.getElementById(mainImgId);
  if (!container) return;
  container.innerHTML = "";

  if (!imgPathsString) return;
  const paths = imgPathsString.split(",").map(p => p.trim()).filter(Boolean);
  if (paths.length <= 1) return;

  paths.forEach((p, idx) => {
    const thumb = document.createElement("img");
    thumb.src = p;
    thumb.className = "w-12 h-12 rounded-lg object-cover cursor-pointer border border-slate-700 hover:border-purple-400 transition-all";
    thumb.title = `Photo #${idx + 1}`;
    thumb.addEventListener("click", () => {
      if (mainImg) mainImg.src = p;
      container.querySelectorAll("img").forEach(i => i.classList.remove("border-purple-400", "ring-2", "ring-purple-500"));
      thumb.classList.add("border-purple-400", "ring-2", "ring-purple-500");
    });
    container.appendChild(thumb);
  });
}

// Side-by-Side Inspect Modal
function openInspectModal(match) {
  try {
    if (!match) return;
    state.activeMatch = match;
    const modal = document.getElementById("inspect-modal");
    if (!modal) {
      console.error("inspect-modal element not found");
      return;
    }
    
    const lost = match.lost_item || {};
    const found = match.found_item || {};

    // Banner Custody Highlight
    const custodySpot = found.custody_location || "Campus Security Room 102";
    const banner = document.getElementById("modal-custody-banner");
    if (banner) banner.textContent = custodySpot;
    const foundCustody = document.getElementById("modal-found-custody");
    if (foundCustody) foundCustody.textContent = custodySpot;

    // Direct Call / Email buttons
    const callBtn = document.getElementById("modal-contact-call-btn");
    const emailBtn = document.getElementById("modal-contact-email-btn");
    if (callBtn) {
      if (found.contact_phone) {
        callBtn.href = `tel:${found.contact_phone}`;
        callBtn.classList.remove("hidden");
      } else {
        callBtn.classList.add("hidden");
      }
    }
    if (emailBtn) {
      if (found.contact_email) {
        emailBtn.href = `mailto:${found.contact_email}?subject=Regarding Found Item: ${encodeURIComponent(found.title || 'Found Item')}`;
        emailBtn.classList.remove("hidden");
      } else {
        emailBtn.classList.add("hidden");
      }
    }

    // Safe Text Setter
    const setTxt = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val !== null && val !== undefined ? String(val) : "N/A";
    };

    // Lost details
    setTxt("modal-lost-title", lost.title || "Lost Item");
    setTxt("modal-lost-category", lost.category || "General");
    setTxt("modal-lost-desc", lost.description || "No description provided");
    setTxt("modal-lost-loc", lost.location_name || "Location unknown");
    setTxt("modal-lost-date", lost.date_occurred || "Recent");
    setTxt("modal-lost-contact-name", lost.contact_name || "Anonymous Owner");
    setTxt("modal-lost-contact-email", lost.contact_email || "N/A");

    const lostPaths = (lost.image_path || "").split(",").map(p => p.trim()).filter(Boolean);
    const lostImg = document.getElementById("modal-lost-img");
    if (lostImg) {
      lostImg.src = lostPaths[0] || "https://images.unsplash.com/photo-1584438784894-089d6a62b8fa?w=600";
    }
    renderGalleryToContainer(lost.image_path, "modal-lost-gallery", "modal-lost-img");

    // Found details
    setTxt("modal-found-title", found.title || "Found Item");
    setTxt("modal-found-category", found.category || "General");
    setTxt("modal-found-desc", found.description || "No description provided");
    setTxt("modal-found-loc", found.location_name || "Location unknown");
    setTxt("modal-found-date", found.date_occurred || "Recent");
    setTxt("modal-found-contact-name", found.contact_name || "Campus Security / Finder");
    setTxt("modal-found-contact-phone", found.contact_phone || found.contact_email || "N/A");

    const foundPaths = (found.image_path || "").split(",").map(p => p.trim()).filter(Boolean);
    const foundImg = document.getElementById("modal-found-img");
    if (foundImg) {
      foundImg.src = foundPaths[0] || "https://images.unsplash.com/photo-1584438784894-089d6a62b8fa?w=600";
    }
    renderGalleryToContainer(found.image_path, "modal-found-gallery", "modal-found-img");

    // Score breakdown
    const compPct = Math.round((match.composite_score || 0) * 100);
    const vScorePct = Math.round((match.visual_score || 0) * 100);
    const tScorePct = Math.round((match.text_score || 0) * 100);
    const gScorePct = Math.round((match.geo_score || 0) * 100);

    setTxt("modal-comp-score", `${compPct}%`);
    setTxt("modal-visual-score", `${vScorePct}%`);
    const vBar = document.getElementById("modal-visual-bar");
    if (vBar) vBar.style.width = `${vScorePct}%`;
    
    setTxt("modal-text-score", `${tScorePct}%`);
    const tBar = document.getElementById("modal-text-bar");
    if (tBar) tBar.style.width = `${tScorePct}%`;
    
    setTxt("modal-geo-score", `${gScorePct}%`);
    const gBar = document.getElementById("modal-geo-bar");
    if (gBar) gBar.style.width = `${gScorePct}%`;

    const distM = match.distance_meters !== null && match.distance_meters !== undefined ? match.distance_meters : 0;
    setTxt("modal-distance-text", distM < 1000 ? `${Math.round(distM)} meters` : `${(distM / 1000).toFixed(2)} km`);
    
    // AI reasoning formatted
    setTxt("modal-ai-reasoning", match.ai_reasoning || "Reasoning synthesized by Tri-Factor AI engine.");

    // Wire View Claims button
    const viewClaimsBtn = document.getElementById("btn-inspect-view-claims");
    if (viewClaimsBtn) {
      viewClaimsBtn.classList.remove("hidden");
      viewClaimsBtn.onclick = () => {
        try { modal.close(); } catch(e){}
        switchTab("claims");
      };
    }

    // Open modal safely
    if (typeof modal.showModal === "function") {
      if (!modal.open) {
        modal.showModal();
      }
    } else {
      modal.setAttribute("open", "");
    }
  } catch (err) {
    console.error("openInspectModal error:", err);
    UI.showToast("Could not open inspector: " + err.message, "error");
  }
}

// Modals Setup
function setupModals() {
  const inspectModal = document.getElementById("inspect-modal");
  const claimModal = document.getElementById("claim-modal");
  const apiKeyModal = document.getElementById("apikey-modal");

  document.getElementById("btn-close-inspect").addEventListener("click", () => inspectModal.close());
  document.getElementById("btn-close-claim").addEventListener("click", () => claimModal.close());
  document.getElementById("btn-close-apikey").addEventListener("click", () => apiKeyModal.close());

  // Inspect modal "Claim Item" button
  document.getElementById("btn-open-claim").addEventListener("click", async () => {
    inspectModal.close();
    await openClaimVerificationFlow(state.activeMatch);
  });
}

// Anti-Fraud Claim Verification Flow
async function openClaimVerificationFlow(match) {
  if (!match) return;
  const modal = document.getElementById("claim-modal");
  document.getElementById("claim-match-id").value = match.id;
  document.getElementById("claim-lost-title").textContent = match.lost_item.title;
  document.getElementById("claim-found-title").textContent = `${match.found_item.title} (${match.found_item.custody_location || 'Campus Security'})`;

  const questionsContainer = document.getElementById("claim-ai-questions");
  questionsContainer.innerHTML = `<div class="text-xs text-purple-400 animate-pulse">Generating personalized AI anti-fraud challenge questions...</div>`;
  modal.showModal();

  try {
    const res = await API.generateClaimQuestions(
      match.lost_item.description,
      match.found_item.description,
      match.lost_item.category
    );
    
    questionsContainer.innerHTML = "";
    if (res.questions && res.questions.length > 0) {
      res.questions.forEach((q, idx) => {
        const qBlock = document.createElement("div");
        qBlock.className = "p-3 bg-purple-950/30 rounded-xl border border-purple-800/40 text-xs";
        qBlock.innerHTML = `
          <label class="block font-semibold text-purple-200 mb-1.5">Challenge Question #${idx + 1}:</label>
          <p class="text-slate-300 italic mb-2">${q}</p>
          <input type="text" name="challenge_answer_${idx}" placeholder="Provide exact identifying details (e.g. markings, contents, serials)..." class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-purple-500">
        `;
        questionsContainer.appendChild(qBlock);
      });
    }
  } catch (err) {
    questionsContainer.innerHTML = `<div class="text-xs text-slate-400">Describe specific distinguishing marks (serial number, scratches, contents) to claim this item.</div>`;
  }
}

// Forms: Lost & Found Submissions
function setupForms() {
  const today = new Date().toISOString().split("T")[0];
  const lostDateInput = document.getElementById("lost-date");
  const foundDateInput = document.getElementById("found-date");
  if (lostDateInput) lostDateInput.value = today;
  if (foundDateInput) foundDateInput.value = today;

  // Multiple Photos Preview & Upload Handlers
  setupImageUploader("lost-image-input", "lost-dropzone", "lost-images-gallery", "lostFiles", "purple");
  setupImageUploader("found-image-input", "found-dropzone", "found-images-gallery", "foundFiles", "emerald");

  // Lost Form Submit
  const lostForm = document.getElementById("form-report-lost");
  lostForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = lostForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Submitting & Running Matching...</span>`;

    try {
      const formData = new FormData(lostForm);
      // Remove any raw empty file entries and append each confirmed file
      formData.delete("images");
      formData.delete("image");
      (state.lostFiles || []).forEach(f => {
        formData.append("images", f);
      });

      const res = await API.createLostItem(formData);
      UI.showToast(`Lost item registered! Identified ${res.matches_found} candidate matches!`, "success");
      lostForm.reset();
      state.lostFiles = [];
      document.getElementById("lost-images-gallery").innerHTML = "";
      await refreshAll();
      switchTab("matches");
    } catch (err) {
      UI.showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Submit Lost Item Report</span> <span>→</span>`;
    }
  });

  // Found Form Submit
  const foundForm = document.getElementById("form-report-found");
  foundForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = foundForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Submitting & Running Matching...</span>`;

    try {
      const formData = new FormData(foundForm);
      // Remove any raw empty file entries and append each confirmed file
      formData.delete("images");
      formData.delete("image");
      (state.foundFiles || []).forEach(f => {
        formData.append("images", f);
      });

      const res = await API.createFoundItem(formData);
      UI.showToast(`Found item recorded! Connected with ${res.matches_found} potential owners!`, "success");
      foundForm.reset();
      state.foundFiles = [];
      document.getElementById("found-images-gallery").innerHTML = "";
      await refreshAll();
      switchTab("matches");
    } catch (err) {
      UI.showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Submit Found Item Report</span> <span>→</span>`;
    }
  });

  // Claim Form Submit
  const claimForm = document.getElementById("form-submit-claim");
  claimForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = claimForm.querySelector("button[type='submit']");
    submitBtn.disabled = true;

    try {
      const matchId = parseInt(document.getElementById("claim-match-id").value);
      const name = document.getElementById("claim-name").value;
      const contact = document.getElementById("claim-contact").value;
      const proof = document.getElementById("claim-proof").value;

      // Gather challenge answers
      const answerInputs = document.querySelectorAll("#claim-ai-questions input");
      const answers = Array.from(answerInputs).map(inp => inp.value).filter(Boolean).join(" | ");

      const claimData = {
        match_id: matchId,
        claimant_name: name,
        claimant_contact: contact,
        secret_verification_answer: answers,
        proof_details: proof
      };

      const res = await API.submitClaim(claimData);
      UI.showToast(res.message, "success");

      document.getElementById("claim-modal").close();
      await refreshAll();
      switchTab("claims");
    } catch (err) {
      UI.showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
    }
  });
}

function setupImageUploader(inputId, dropzoneId, galleryId, stateProp, accentColor) {
  const input = document.getElementById(inputId);
  const dropzone = document.getElementById(dropzoneId);
  const gallery = document.getElementById(galleryId);
  if (!input || !gallery) return;

  function renderGallery() {
    gallery.innerHTML = "";
    const files = state[stateProp] || [];
    if (files.length === 0) return;

    const countPill = document.createElement("div");
    countPill.className = `w-full text-xs font-bold text-${accentColor}-300 mb-1 flex items-center justify-between`;
    countPill.innerHTML = `
      <span>📷 ${files.length} Photo${files.length > 1 ? 's' : ''} Selected (Ready to Upload):</span>
      <button type="button" class="btn-clear text-[10px] text-rose-400 hover:text-rose-300 underline font-semibold">Clear All</button>
    `;
    countPill.querySelector(".btn-clear").addEventListener("click", (e) => {
      e.preventDefault();
      state[stateProp] = [];
      input.value = "";
      renderGallery();
    });
    gallery.appendChild(countPill);

    files.forEach((file, idx) => {
      const reader = new FileReader();
      reader.onload = (re) => {
        const wrapper = document.createElement("div");
        wrapper.className = "w-16 h-16 rounded-xl overflow-hidden border border-slate-700 bg-slate-900 shadow relative group";
        wrapper.innerHTML = `
          <img src="${re.target.result}" alt="Preview ${idx + 1}" class="w-full h-full object-cover">
          <span class="absolute top-1 left-1 px-1 rounded bg-black/75 text-[9px] text-white font-mono">${idx + 1}</span>
          <button type="button" class="btn-del absolute top-1 right-1 w-4 h-4 rounded-full bg-rose-600/90 hover:bg-rose-500 text-white text-[10px] flex items-center justify-center shadow">✕</button>
        `;
        wrapper.querySelector(".btn-del").addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          state[stateProp].splice(idx, 1);
          renderGallery();
        });
        gallery.appendChild(wrapper);
      };
      reader.readAsDataURL(file);
    });
  }

  function addFiles(newFiles) {
    const valid = Array.from(newFiles).filter(f => f.type && f.type.startsWith("image/"));
    if (valid.length === 0) return;
    if (!state[stateProp]) state[stateProp] = [];
    state[stateProp].push(...valid);
    renderGallery();
  }

  input.addEventListener("change", (e) => {
    addFiles(e.target.files);
    input.value = ""; // Reset so user can click again to add more photos
  });

  if (dropzone) {
    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add(`border-${accentColor}-400`, "bg-slate-800/80");
    });
    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove(`border-${accentColor}-400`, "bg-slate-800/80");
    });
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove(`border-${accentColor}-400`, "bg-slate-800/80");
      if (e.dataTransfer && e.dataTransfer.files) {
        addFiles(e.dataTransfer.files);
      }
    });
  }
}

// API Key Manager Setup
function setupApiKeyManager() {
  const modal = document.getElementById("apikey-modal");
  const badge = document.getElementById("ai-status-badge");
  badge.addEventListener("click", () => modal.showModal());

  const form = document.getElementById("form-api-key");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const key = document.getElementById("input-api-key").value;
    const saveBtn = form.querySelector("button[type='submit']");
    saveBtn.disabled = true;
    saveBtn.textContent = "Verifying with Google Gemini...";

    try {
      const res = await API.updateApiKey(key);
      UI.showToast("Key verified! " + res.message, "success");
      modal.close();
      await refreshAll();
    } catch (err) {
      UI.showToast(err.message, "error");
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = "Test & Save Key";
    }
  });
}

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Open Reward Modal
function openRewardModal(claim) {
  if (!claim) return;
  const modal = document.getElementById("reward-modal");
  if (!modal) return;

  document.getElementById("reward-claim-id").value = claim.id;
  document.getElementById("reward-founder-name").textContent = claim.founder_name || "Campus Security / Founder";
  document.getElementById("reward-custody-location").textContent = claim.custody_location || "Security Office";
  
  const upiId = claim.founder_upi || claim.founder_phone || "";
  const upiEl = document.getElementById("reward-founder-upi");
  const upiBox = document.getElementById("reward-upi-box");
  const upiBtn = document.getElementById("btn-pay-upi-app");

  if (upiId && upiId.trim()) {
    upiEl.textContent = upiId;
    upiBox.classList.remove("hidden");
    const amount = document.getElementById("reward-amount").value || "100";
    const upiLink = `upi://pay?pa=${encodeURIComponent(upiId)}&pn=${encodeURIComponent(claim.founder_name || 'Founder')}&am=${amount}&tn=${encodeURIComponent('Relink AI - Reward for Found Item')}`;
    upiBtn.href = upiLink;
    upiBtn.classList.remove("hidden");
  } else {
    upiEl.textContent = "Not specified (Direct Handover / Cash)";
    upiBtn.classList.add("hidden");
  }

  modal.showModal();
}

function setupRewardManager() {
  const modal = document.getElementById("reward-modal");
  const closeBtn = document.getElementById("btn-close-reward");
  if (closeBtn) closeBtn.addEventListener("click", () => modal.close());

  // Preset buttons
  const presetBtns = document.querySelectorAll(".btn-preset-reward");
  const amountInput = document.getElementById("reward-amount");
  const upiBtn = document.getElementById("btn-pay-upi-app");

  presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const amt = btn.dataset.amount;
      amountInput.value = amt;
      presetBtns.forEach(b => {
        b.classList.remove("border-amber-500/60", "bg-amber-600/20", "text-amber-300");
        b.classList.add("border-slate-700", "bg-slate-900", "text-slate-200");
      });
      btn.classList.add("border-amber-500/60", "bg-amber-600/20", "text-amber-300");
      btn.classList.remove("border-slate-700", "bg-slate-900", "text-slate-200");

      const upiText = document.getElementById("reward-founder-upi").textContent;
      if (upiText && !upiText.includes("Not specified") && upiBtn) {
        const name = document.getElementById("reward-founder-name").textContent;
        upiBtn.href = `upi://pay?pa=${encodeURIComponent(upiText)}&pn=${encodeURIComponent(name)}&am=${amt}&tn=${encodeURIComponent('Relink AI - Reward for Found Item')}`;
      }
    });
  });

  if (amountInput) {
    amountInput.addEventListener("input", () => {
      const amt = amountInput.value;
      const upiText = document.getElementById("reward-founder-upi").textContent;
      if (upiText && !upiText.includes("Not specified") && upiBtn) {
        const name = document.getElementById("reward-founder-name").textContent;
        upiBtn.href = `upi://pay?pa=${encodeURIComponent(upiText)}&pn=${encodeURIComponent(name)}&am=${amt}&tn=${encodeURIComponent('Relink AI - Reward for Found Item')}`;
      }
    });
  }

  const form = document.getElementById("form-send-reward");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const claimId = parseInt(document.getElementById("reward-claim-id").value);
      const amount = parseFloat(document.getElementById("reward-amount").value);
      const message = document.getElementById("reward-message").value;
      const submitBtn = document.getElementById("btn-submit-reward");

      if (!amount || amount <= 0) {
        UI.showToast("Please enter a valid reward amount.", "warning");
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "Processing Reward...";

      try {
        const res = await API.sendReward(claimId, {
          amount: amount,
          message: message,
          payment_mode: "UPI / Direct"
        });
        UI.showToast(res.message, "success");
        modal.close();
        await refreshAll();
      } catch (err) {
        UI.showToast("Reward recording failed: " + err.message, "error");
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>✓ Record & Send Reward</span>`;
      }
    });
  }
}

function setupNotificationsManager() {
  const notifBtn = document.getElementById("btn-notifications");
  const modal = document.getElementById("notifications-modal");
  const closeBtn = document.getElementById("btn-close-notifications");
  const container = document.getElementById("notifications-container");

  if (closeBtn) closeBtn.addEventListener("click", () => modal.close());

  if (notifBtn) {
    notifBtn.addEventListener("click", async () => {
      modal.showModal();
      container.innerHTML = `<div class="p-4 text-center text-xs text-slate-400">Loading automated alerts...</div>`;
      try {
        const list = await API.getNotifications();
        container.innerHTML = "";
        if (!list || list.length === 0) {
          container.innerHTML = `
            <div class="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-xs text-slate-400">
              <span class="text-3xl block mb-2">🔕</span>
              <span class="font-semibold text-slate-300 block mb-1">No automated email alerts sent yet.</span>
              <span>When an AI match reaches or exceeds 70% confidence, an email notification is automatically recorded and sent to the owner.</span>
            </div>
          `;
          return;
        }

        list.forEach(n => {
          const card = document.createElement("div");
          const scorePct = Math.round((n.match_score || 0) * 100);
          card.className = "p-4 bg-slate-900/80 rounded-xl border border-purple-500/20 hover:border-purple-500/40 transition-all text-xs space-y-2";
          card.innerHTML = `
            <div class="flex items-center justify-between">
              <span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-600/30 text-purple-300 border border-purple-500/40 flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-purple-400 animate-ping"></span>
                ${scorePct}% Match Confidence
              </span>
              <span class="text-[10px] text-slate-400 font-mono">${n.created_at}</span>
            </div>
            <div class="font-bold text-white text-sm">${n.subject}</div>
            <div class="text-slate-300 text-[11px] flex flex-wrap items-center gap-x-4 gap-y-1">
              <span>📧 <strong>To:</strong> ${n.recipient_email} (${n.recipient_name || 'Owner'})</span>
              <span>📡 <strong>Delivery:</strong> <span class="${n.status === 'sent' ? 'text-emerald-400 font-bold' : 'text-blue-400 font-bold'}">${n.status === 'sent' ? '✓ SMTP Sent' : '✓ Logged & Ready'}</span></span>
            </div>
            <details class="cursor-pointer text-[11px] text-slate-400 pt-1 border-t border-slate-800">
              <summary class="hover:text-purple-300 transition-colors">View Email Content Preview</summary>
              <pre class="mt-2 p-2.5 bg-slate-950 rounded-lg text-[10px] text-slate-300 whitespace-pre-wrap font-mono">${n.body}</pre>
            </details>
          `;
          container.appendChild(card);
        });
      } catch (err) {
        container.innerHTML = `<div class="p-4 text-center text-xs text-rose-400">Failed to load notifications: ${err.message}</div>`;
      }
    });
  }
}
