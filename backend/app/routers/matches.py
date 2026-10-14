from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3
from ..database import get_db
from ..engine.hybrid_matcher import HybridMatcher

router = APIRouter(prefix="/api/matches", tags=["matches"])

@router.get("")
def list_matches(
    min_score: float = Query(0.40, ge=0.0, le=1.0),
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db)
):
    query = """
    SELECT 
        m.id as match_id, m.visual_score, m.text_score, m.geo_score,
        m.composite_score, m.distance_meters, m.ai_reasoning, m.status as match_status,
        m.created_at as match_created_at,
        
        l.id as lost_id, l.title as lost_title, l.description as lost_desc,
        l.category as lost_category, l.primary_color as lost_color, l.brand as lost_brand,
        l.latitude as lost_lat, l.longitude as lost_lon, l.location_name as lost_location,
        l.date_occurred as lost_date, l.image_path as lost_image, l.status as lost_status,
        l.contact_name as lost_contact_name, l.contact_email as lost_contact_email,
        l.contact_phone as lost_contact_phone,
        
        f.id as found_id, f.title as found_title, f.description as found_desc,
        f.category as found_category, f.primary_color as found_color, f.brand as found_brand,
        f.latitude as found_lat, f.longitude as found_lon, f.location_name as found_location,
        f.date_occurred as found_date, f.image_path as found_image, f.status as found_status,
        f.custody_location as found_custody, f.contact_name as found_contact_name,
        f.contact_email as found_contact_email, f.contact_phone as found_contact_phone
    FROM matches m
    JOIN items l ON m.lost_item_id = l.id
    JOIN items f ON m.found_item_id = f.id
    WHERE m.composite_score >= ?
    """
    params = [min_score]
    
    if status and status.lower() != "all":
        query += " AND m.status = ?"
        params.append(status)
        
    query += " ORDER BY m.composite_score DESC LIMIT ?"
    params.append(limit)
    
    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    results = []
    for r in rows:
        d = dict(r)
        results.append({
            "id": d["match_id"],
            "visual_score": d["visual_score"],
            "text_score": d["text_score"],
            "geo_score": d["geo_score"],
            "composite_score": d["composite_score"],
            "distance_meters": d["distance_meters"],
            "ai_reasoning": d["ai_reasoning"],
            "status": d["match_status"],
            "created_at": d["match_created_at"],
            "lost_item": {
                "id": d["lost_id"],
                "title": d["lost_title"],
                "description": d["lost_desc"],
                "category": d["lost_category"],
                "primary_color": d["lost_color"],
                "brand": d["lost_brand"],
                "latitude": d["lost_lat"],
                "longitude": d["lost_lon"],
                "location_name": d["lost_location"],
                "date_occurred": d["lost_date"],
                "image_path": d["lost_image"],
                "status": d["lost_status"],
                "contact_name": d["lost_contact_name"],
                "contact_email": d["lost_contact_email"],
                "contact_phone": d.get("lost_contact_phone")
            },
            "found_item": {
                "id": d["found_id"],
                "title": d["found_title"],
                "description": d["found_desc"],
                "category": d["found_category"],
                "primary_color": d["found_color"],
                "brand": d["found_brand"],
                "latitude": d["found_lat"],
                "longitude": d["found_lon"],
                "location_name": d["found_location"],
                "date_occurred": d["found_date"],
                "image_path": d["found_image"],
                "status": d["found_status"],
                "custody_location": d["found_custody"],
                "contact_name": d["found_contact_name"],
                "contact_email": d["found_contact_email"],
                "contact_phone": d.get("found_contact_phone")
            }
        })
    return results

@router.post("/recalculate")
def recalculate_matches(db: sqlite3.Connection = Depends(get_db)):
    updated_count = HybridMatcher.recalculate_all(db)
    return {"status": "success", "matches_evaluated_or_updated": updated_count}

@router.patch("/{match_id}/status")
def update_match_status(match_id: int, status: str = Query(..., pattern="^(pending|verified|rejected)$"), db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE matches SET status = ? WHERE id = ?", (status, match_id))
    db.commit()
    return {"status": "success", "match_id": match_id, "new_status": status}
