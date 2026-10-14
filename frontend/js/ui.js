/**
 * Relink AI - UI Component Renderer & Modal Controllers
 */

export const UI = {
  showToast(message, type = "info") {
    const toast = document.createElement("div");
    const colors = {
      success: "bg-emerald-600 text-white border-emerald-400",
      error: "bg-rose-600 text-white border-rose-400",
      info: "bg-blue-600 text-white border-blue-400",
      warning: "bg-amber-600 text-white border-amber-400"
    };

    toast.className = `fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl border shadow-2xl flex items-center gap-3 text-sm font-medium transition-all duration-300 transform translate-y-2 opacity-0 ${colors[type] || colors.info}`;
    toast.innerHTML = `
      <span>${type === 'success' ? '✓' : (type === 'error' ? '✕' : 'ℹ')}</span>
      <span>${message}</span>
    `;

    document.body.appendChild(toast);
    requestAnimationFrame(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    });

    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  },

  formatPercentage(val) {
    return `${Math.round((val || 0) * 100)}%`;
  },

  getScoreColorClass(score) {
    if (score >= 0.75) return "text-purple-400 bg-purple-500/10 border-purple-500/30";
    if (score >= 0.55) return "text-blue-400 bg-blue-500/10 border-blue-500/30";
    return "text-slate-400 bg-slate-500/10 border-slate-500/30";
  },

  getCategoryIcon(cat = "") {
    const c = (cat || "").toLowerCase();
    if (c.includes("bottle") || c.includes("flask") || c.includes("sipper") || c.includes("thermos")) return "🍶";
    if (c.includes("electronic") || c.includes("laptop") || c.includes("phone")) return "💻";
    if (c.includes("wallet") || c.includes("purse")) return "👛";
    if (c.includes("bag") || c.includes("backpack")) return "🎒";
    if (c.includes("key")) return "🔑";
    if (c.includes("doc") || c.includes("card")) return "📄";
    if (c.includes("pet")) return "🐾";
    return "📦";
  },

  renderImageOrPlaceholder(imgPath, category = "", title = "") {
    if (imgPath && imgPath.trim()) {
      const paths = imgPath.split(",").map(p => p.trim()).filter(Boolean);
      const primary = paths[0];
      const countBadge = paths.length > 1 
        ? `<div class="absolute bottom-2 right-2 px-2 py-0.5 rounded-md bg-black/70 backdrop-blur-sm text-[10px] font-semibold text-white border border-white/20">📷 ${paths.length} Photos</div>`
        : "";

      return `
        <div class="w-full h-full relative group">
          <img src="${primary}" alt="${title}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500">
          ${countBadge}
        </div>
      `;
    }
    const icon = this.getCategoryIcon(category);
    return `
      <div class="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 to-slate-950 text-slate-500">
        <span class="text-3xl mb-1">${icon}</span>
        <span class="text-[10px] tracking-wider uppercase font-semibold text-slate-400">Photo Not Provided</span>
      </div>
    `;
  },

  renderMatchCard(match, onInspect) {
    const scorePct = Math.round(match.composite_score * 100);
    const vScorePct = Math.round(match.visual_score * 100);
    const tScorePct = Math.round(match.text_score * 100);
    const gScorePct = Math.round(match.geo_score * 100);

    const lost = match.lost_item;
    const found = match.found_item;

    const distFormatted = match.distance_meters < 1000 
      ? `${Math.round(match.distance_meters)}m` 
      : `${(match.distance_meters / 1000).toFixed(1)}km`;

    const card = document.createElement("div");
    card.className = "glass-panel rounded-2xl p-5 hover:border-purple-500/40 transition-all duration-300 relative group overflow-hidden";

    card.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <span class="px-2.5 py-1 rounded-full text-xs font-bold border ${this.getScoreColorClass(match.composite_score)} flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full ${scorePct >= 70 ? 'bg-purple-400 animate-ping' : 'bg-blue-400'}"></span>
            ${scorePct}% AI Match
          </span>
          <span class="text-xs text-slate-400">Proximity: <strong class="text-slate-200">${distFormatted}</strong></span>
        </div>
        ${match.status === 'verified' 
          ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40">✓ REUNITED</span>'
          : `<span class="text-[11px] font-mono text-slate-500">Match #${match.id}</span>`
        }
      </div>

      <!-- Side by Side Preview -->
      <div class="grid grid-cols-2 gap-3 mb-3">
        <!-- Lost Box -->
        <div class="bg-slate-900/60 rounded-xl p-2.5 border border-red-500/20">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-[10px] font-bold tracking-wider uppercase text-red-400">Lost Item</span>
            <span class="text-[10px] text-slate-400">${lost.category}</span>
          </div>
          <div class="h-28 rounded-lg overflow-hidden bg-slate-950 mb-2 relative border border-slate-800">
            ${this.renderImageOrPlaceholder(lost.image_path, lost.category, lost.title)}
          </div>
          <h4 class="font-bold text-xs text-slate-200 truncate" title="${lost.title}">${lost.title}</h4>
          <p class="text-[11px] text-slate-400 truncate">📍 ${lost.location_name}</p>
        </div>

        <!-- Found Box -->
        <div class="bg-slate-900/60 rounded-xl p-2.5 border border-emerald-500/20">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-[10px] font-bold tracking-wider uppercase text-emerald-400">Found Item</span>
            <span class="text-[10px] text-slate-400">${found.category}</span>
          </div>
          <div class="h-28 rounded-lg overflow-hidden bg-slate-950 mb-2 relative border border-slate-800">
            ${this.renderImageOrPlaceholder(found.image_path, found.category, found.title)}
          </div>
          <h4 class="font-bold text-xs text-slate-200 truncate" title="${found.title}">${found.title}</h4>
          <p class="text-[11px] text-emerald-400/90 font-medium truncate" title="${found.custody_location || 'Security Desk'}">
            🏢 ${found.custody_location || 'Campus Security'}
          </p>
        </div>
      </div>

      <!-- Safe Custody Callout Bar -->
      <div class="mb-3 px-3 py-2 bg-emerald-950/30 rounded-xl border border-emerald-800/40 text-xs flex items-center justify-between">
        <span class="text-slate-400 text-[11px]">Pickup Spot:</span>
        <span class="font-bold text-emerald-300 text-[11px] truncate max-w-[200px]" title="${found.custody_location || 'Campus Security Desk'}">
          ${found.custody_location || 'Campus Security Desk'}
        </span>
      </div>

      <!-- Tri-Factor Radar Bars -->
      <div class="space-y-1.5 mb-4 text-xs bg-slate-950/40 p-3 rounded-xl border border-slate-800/80">
        <div class="flex items-center justify-between text-[11px]">
          <span class="text-slate-400 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-blue-400"></span> Visual Match (40%)
          </span>
          <span class="font-mono font-semibold text-slate-200">${vScorePct}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-blue-500 h-1.5 rounded-full transition-all duration-500" style="width: ${vScorePct}%"></div>
        </div>

        <div class="flex items-center justify-between text-[11px] pt-1">
          <span class="text-slate-400 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Description & Category (35%)
          </span>
          <span class="font-mono font-semibold text-slate-200">${tScorePct}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-emerald-500 h-1.5 rounded-full transition-all duration-500" style="width: ${tScorePct}%"></div>
        </div>

        <div class="flex items-center justify-between text-[11px] pt-1">
          <span class="text-slate-400 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span> Proximity Match (25%)
          </span>
          <span class="font-mono font-semibold text-slate-200">${gScorePct}%</span>
        </div>
        <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div class="bg-amber-500 h-1.5 rounded-full transition-all duration-500" style="width: ${gScorePct}%"></div>
        </div>
      </div>

      <!-- Action Button -->
      <button type="button" class="inspect-btn w-full py-2.5 px-4 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 active:scale-[0.98] text-white font-semibold text-xs rounded-xl shadow-lg shadow-purple-600/20 flex items-center justify-center gap-2 transition-all cursor-pointer select-none" onclick="if(window.relinkOpenInspect){window.relinkOpenInspect(${match.id});}">
        <span>Inspect & Verify Ownership</span>
        <span>→</span>
      </button>
    `;

    const btn = card.querySelector(".inspect-btn");
    if (btn) {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        onInspect(match);
      });
    }
    return card;
  },

  renderItemCard(item, onSelect) {
    const isLost = item.type === "lost";
    const badgeBg = isLost ? "bg-red-500/15 text-red-400 border-red-500/30" : "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";

    const card = document.createElement("div");
    card.className = "glass-panel rounded-2xl overflow-hidden hover:border-slate-600 transition-all duration-200 flex flex-col";

    card.innerHTML = `
      <div class="h-44 w-full bg-slate-950 relative overflow-hidden border-b border-slate-800/80">
        ${this.renderImageOrPlaceholder(item.image_path, item.category, item.title)}
        <div class="absolute top-3 left-3 flex gap-2">
          <span class="px-2.5 py-1 rounded-full text-[11px] font-bold border uppercase tracking-wider ${badgeBg}">
            ${item.type}
          </span>
          <span class="px-2.5 py-1 rounded-full text-[11px] font-medium bg-slate-900/80 backdrop-blur-md text-slate-300 border border-slate-700">
            ${item.category}
          </span>
        </div>
        ${item.status === 'reunited' ? '<div class="absolute inset-0 bg-blue-900/70 backdrop-blur-sm flex items-center justify-center font-bold text-white text-sm">🎉 REUNITED</div>' : ''}
      </div>
      <div class="p-4 flex-1 flex flex-col justify-between">
        <div>
          <h3 class="font-bold text-base text-slate-100 mb-1 leading-snug line-clamp-1">${item.title}</h3>
          <p class="text-xs text-slate-400 line-clamp-2 mb-2">${item.description}</p>
          ${item.custody_location ? `<p class="text-[11px] text-emerald-300 font-medium truncate mb-2">🏢 Safe Custody: ${item.custody_location}</p>` : ''}
        </div>
        <div class="border-t border-slate-800/80 pt-3 space-y-1 text-[11px] text-slate-400">
          <div class="flex items-center gap-1.5 truncate">
            <span>📍</span> <span>${item.location_name}</span>
          </div>
          <div class="flex items-center justify-between text-slate-500">
            <span>📅 ${item.date_occurred}</span>
            <span>👤 ${item.contact_name}</span>
          </div>
        </div>
      </div>
    `;

    card.addEventListener("click", () => onSelect(item));
    return card;
  }
};
