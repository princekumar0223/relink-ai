from fastapi import APIRouter, Depends, HTTPException
import sqlite3
from ..database import get_db
from ..schemas import ClaimCreate
from ..config import settings

router = APIRouter(prefix="/api/claims", tags=["claims"])

@router.post("")
def submit_claim(claim: ClaimCreate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    # Check if match exists
    cursor.execute("SELECT * FROM matches WHERE id = ?", (claim.match_id,))
    match_row = cursor.fetchone()
    if not match_row:
        raise HTTPException(status_code=404, detail="Match not found.")
        
    cursor.execute("""
    INSERT INTO claims (
        match_id, claimant_name, claimant_contact,
        secret_verification_answer, proof_details, status
    ) VALUES (?, ?, ?, ?, ?, 'pending')
    """, (
        claim.match_id, claim.claimant_name, claim.claimant_contact,
        claim.secret_verification_answer, claim.proof_details
    ))
    db.commit()
    claim_id = cursor.lastrowid
    return {
        "status": "submitted",
        "claim_id": claim_id,
        "message": "Ownership claim submitted! The founder / custody desk can now review your verification answers."
    }

@router.get("")
def list_claims(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
    SELECT c.*, m.lost_item_id, m.found_item_id, m.composite_score,
           l.title as lost_title, l.description as lost_desc, l.image_path as lost_image,
           l.contact_name as owner_name, l.contact_email as owner_email, l.contact_phone as owner_phone,
           f.title as found_title, f.description as found_desc, f.image_path as found_image,
           f.custody_location, f.contact_name as founder_name, f.contact_email as founder_email, f.contact_phone as founder_phone
    FROM claims c
    JOIN matches m ON c.match_id = m.id
    JOIN items l ON m.lost_item_id = l.id
    JOIN items f ON m.found_item_id = f.id
    ORDER BY c.created_at DESC
    """)
    return [dict(r) for r in cursor.fetchall()]

@router.get("/match/{match_id}")
def get_claims_for_match(match_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("""
    SELECT c.*, m.lost_item_id, m.found_item_id, m.composite_score,
           l.title as lost_title, f.title as found_title, f.custody_location,
           f.contact_name as founder_name, f.contact_email as founder_email, f.contact_phone as founder_phone
    FROM claims c
    JOIN matches m ON c.match_id = m.id
    JOIN items l ON m.lost_item_id = l.id
    JOIN items f ON m.found_item_id = f.id
    WHERE c.match_id = ?
    ORDER BY c.created_at DESC
    """, (match_id,))
    return [dict(r) for r in cursor.fetchall()]

@router.patch("/{claim_id}/approve")
def approve_claim(claim_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
    claim = cursor.fetchone()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
        
    cursor.execute("SELECT * FROM matches WHERE id = ?", (claim["match_id"],))
    match_row = cursor.fetchone()
    
    # Update claim status
    cursor.execute("UPDATE claims SET status = 'approved' WHERE id = ?", (claim_id,))
    # Update match status
    cursor.execute("UPDATE matches SET status = 'verified' WHERE id = ?", (claim["match_id"],))
    # Update both items to 'reunited'
    if match_row:
        cursor.execute("UPDATE items SET status = 'reunited' WHERE id IN (?, ?)", (match_row["lost_item_id"], match_row["found_item_id"]))
        
    db.commit()
    return {
        "status": "success",
        "message": "Verification Approved! Handover verified and items officially marked as REUNITED."
    }

@router.patch("/{claim_id}/reject")
def reject_claim(claim_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
    claim = cursor.fetchone()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found.")
        
    cursor.execute("UPDATE claims SET status = 'rejected' WHERE id = ?", (claim_id,))
    db.commit()
    return {
        "status": "success",
        "message": "Claim rejected. Verification answers did not match found item details."
    }

@router.get("/stats/summary")
def get_system_stats(db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM items WHERE type = 'lost'")
    total_lost = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items WHERE type = 'found'")
    total_found = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM matches WHERE composite_score >= ?", (settings.MATCH_ALERT_THRESHOLD,))
    active_matches = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'reunited'")
    reunited_items = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM claims WHERE status = 'pending'")
    pending_claims = cursor.fetchone()[0]
    
    has_key = bool(settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY.strip()) > 5)
    
    return {
        "total_lost": total_lost,
        "total_found": total_found,
        "active_matches": active_matches,
        "reunited_items": reunited_items,
        "pending_claims": pending_claims,
        "gemini_ai_active": has_key,
        "engine_mode": "Gemini 3.8 Flash Multimodal" if has_key else "Local CV & Geo Proximity"
    }
