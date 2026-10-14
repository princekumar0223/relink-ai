import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.database import init_db, db_context

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def run_integration_checks():
    print("[*] Running Clean Production Integration Checks...")
    init_db()

    # Pre-clean database to ensure pristine initial test state
    with db_context() as conn:
        conn.execute("DELETE FROM claims")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM items")
        conn.commit()

    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.text}"
    health_data = res_health.json()
    print("  [OK] GET /api/health passed:", health_data)
    assert health_data["gemini_active"] is True, "Expected Gemini API to be active with user's key"

    # 2. Clean Stats summary
    res_stats = client.get("/api/claims/stats/summary")
    assert res_stats.status_code == 200, f"Stats summary failed: {res_stats.text}"
    stats_data = res_stats.json()
    print("  [OK] Clean state stats:", stats_data)
    assert stats_data["total_lost"] == 0, f"Expected 0 lost items, got {stats_data['total_lost']}"
    assert stats_data["total_found"] == 0, f"Expected 0 found items, got {stats_data['total_found']}"
    assert stats_data["active_matches"] == 0, f"Expected 0 matches, got {stats_data['active_matches']}"
    assert stats_data["pending_claims"] == 0, f"Expected 0 pending claims, got {stats_data['pending_claims']}"

    # 3. Test submitting a live Lost item (Bottles & Flasks category)
    res_lost = client.post("/api/items/lost", data={
        "title": "Milton Stainless Steel Insulated Water Bottle",
        "category": "bottles",
        "description": "Silver 1-litre Milton thermosteel water bottle with black strap and small dent near bottom",
        "latitude": 28.6315,
        "longitude": 77.2167,
        "location_name": "Library Reading Hall 2nd Floor",
        "date_occurred": "2026-10-14",
        "contact_name": "Rahul Verma",
        "contact_email": "rahul.student@campus.edu",
        "contact_phone": "+91 98765 43210",
        "primary_color": "Silver",
        "brand": "Milton"
    })
    assert res_lost.status_code == 200, f"Lost bottle report failed: {res_lost.text}"
    lost_id = res_lost.json()["item"]["id"]
    print(f"  [OK] POST /api/items/lost (Category: bottles) passed, created ID: {lost_id}")

    # 4. Test submitting a matching Found item with Safe Custody details
    res_found = client.post("/api/items/found", data={
        "title": "Milton Silver Flask Water Bottle",
        "category": "bottles",
        "description": "Silver insulated flask bottle with carrying strap found on library table",
        "latitude": 28.6317,
        "longitude": 77.2169,
        "location_name": "Campus Central Library",
        "date_occurred": "2026-10-14",
        "contact_name": "Officer Sharma",
        "contact_email": "security@campus.edu",
        "contact_phone": "+91 91234 56789",
        "custody_location": "Campus Security Room 102 (Locker B-4)",
        "primary_color": "Silver",
        "brand": "Milton"
    })
    assert res_found.status_code == 200, f"Found bottle report failed: {res_found.text}"
    found_id = res_found.json()["item"]["id"]
    print(f"  [OK] POST /api/items/found (Safe Custody: Campus Security Room 102) passed, created ID: {found_id}")

    # 5. Verify Automatic Tri-Factor Match Discovery
    res_matches = client.get("/api/matches?min_score=0.40")
    assert res_matches.status_code == 200
    matches = res_matches.json()
    assert len(matches) > 0, "Expected an automatic match between Milton bottles"
    top_match = matches[0]
    match_id = top_match["id"]
    print(f"  [OK] Automatic AI Match Identified: #{match_id} with {int(top_match['composite_score']*100)}% Confidence!")
    print(f"       Visual: {int(top_match['visual_score']*100)}%, Text: {int(top_match['text_score']*100)}%, Geo: {int(top_match['geo_score']*100)}%")

    # 6. Test Owner Filing Claim with 2 Challenge Answers
    claim_payload = {
        "match_id": match_id,
        "claimant_name": "Rahul Verma",
        "claimant_contact": "+91 98765 43210 (rahul.student@campus.edu)",
        "secret_verification_answer": "Q1: Any stickers/engravings? -> Has tiny star sticker at bottom. | Q2: Dent/unique mark? -> Small dent on lower right base.",
        "proof_details": "I have the original purchase receipt from Amazon"
    }
    res_claim = client.post("/api/claims", json=claim_payload)
    assert res_claim.status_code == 200, f"Claim submission failed: {res_claim.text}"
    claim_id = res_claim.json()["claim_id"]
    print(f"  [OK] POST /api/claims passed, claim #{claim_id} created in 'pending' status for founder verification.")

    # 7. Founder Reviews Claims List
    res_claims_list = client.get("/api/claims")
    assert res_claims_list.status_code == 200
    claims = res_claims_list.json()
    assert len(claims) == 1
    c = claims[0]
    assert c["custody_location"] == "Campus Security Room 102 (Locker B-4)"
    assert "Small dent on lower right base" in c["secret_verification_answer"]
    print(f"  [OK] GET /api/claims passed: Founder correctly sees owner's answers and custody location.")

    # 8. Founder Approves Claim & Releases Item
    res_approve = client.patch(f"/api/claims/{claim_id}/approve")
    assert res_approve.status_code == 200
    print(f"  [OK] PATCH /api/claims/{claim_id}/approve passed: {res_approve.json()['message']}")

    # Check stats after approval
    res_stats_after = client.get("/api/claims/stats/summary")
    stats_after = res_stats_after.json()
    assert stats_after["reunited_items"] == 2
    assert stats_after["pending_claims"] == 0
    print(f"  [OK] Items officially marked as REUNITED: {stats_after['reunited_items']}")

    # 9. Clean up test entries so the database is 100% pristine for deployment
    with db_context() as conn:
        conn.execute("DELETE FROM claims")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM items")
        conn.commit()
    print("  [OK] Database cleaned: 0 Lost, 0 Found, 0 Claims. Ready for deployment!")

    print("\n[SUCCESS] Production readiness verification passed 100%!")

if __name__ == "__main__":
    run_integration_checks()
