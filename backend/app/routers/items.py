from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
import sqlite3
from ..database import get_db
from ..utils.image_helpers import save_uploaded_image
from ..engine.hybrid_matcher import HybridMatcher

router = APIRouter(prefix="/api/items", tags=["items"])

@router.post("/lost")
async def report_lost_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_name: str = Form(...),
    date_occurred: str = Form(...),
    contact_name: str = Form(...),
    contact_email: str = Form(...),
    primary_color: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    image: Optional[UploadFile] = File(None),
    db: sqlite3.Connection = Depends(get_db)
):
    all_files = []
    if images:
        all_files.extend(images)
    if image:
        all_files.append(image)

    saved_paths = []
    saved_hashes = []
    for f in all_files:
        if f and f.filename and len(f.filename.strip()) > 0:
            try:
                content = await f.read()
                if len(content) > 0:
                    p, h = save_uploaded_image(content, f.filename)
                    saved_paths.append(p)
                    saved_hashes.append(h)
            except Exception as e:
                print(f"[WARN] Image processing failed for {f.filename}: {e}")

    image_path = ",".join(saved_paths) if saved_paths else None
    image_hash = saved_hashes[0] if saved_hashes else None
            
    cursor = db.cursor()
    cursor.execute("""
    INSERT INTO items (
        type, title, description, category, primary_color, brand,
        latitude, longitude, location_name, date_occurred,
        contact_name, contact_email, contact_phone,
        image_path, image_hash, status
    ) VALUES ('lost', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (
        title, description, category, primary_color, brand,
        latitude, longitude, location_name, date_occurred,
        contact_name, contact_email, contact_phone,
        image_path, image_hash
    ))
    db.commit()
    item_id = cursor.lastrowid
    
    # Run immediate tri-factor matching against found items
    new_matches = HybridMatcher.match_item_against_all(item_id, db)
    
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item_data = dict(cursor.fetchone())
    return {
        "item": item_data,
        "matches_found": len(new_matches),
        "top_matches": sorted(new_matches, key=lambda x: x["composite_score"], reverse=True)[:3]
    }

@router.post("/found")
async def report_found_item(
    title: str = Form(...),
    description: str = Form(...),
    category: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    location_name: str = Form(...),
    date_occurred: str = Form(...),
    contact_name: str = Form(...),
    contact_email: str = Form(...),
    custody_location: str = Form("Safe keeping / Security desk"),
    primary_color: Optional[str] = Form(None),
    brand: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
    image: Optional[UploadFile] = File(None),
    db: sqlite3.Connection = Depends(get_db)
):
    all_files = []
    if images:
        all_files.extend(images)
    if image:
        all_files.append(image)

    saved_paths = []
    saved_hashes = []
    for f in all_files:
        if f and f.filename and len(f.filename.strip()) > 0:
            try:
                content = await f.read()
                if len(content) > 0:
                    p, h = save_uploaded_image(content, f.filename)
                    saved_paths.append(p)
                    saved_hashes.append(h)
            except Exception as e:
                print(f"[WARN] Image processing failed for {f.filename}: {e}")

    image_path = ",".join(saved_paths) if saved_paths else None
    image_hash = saved_hashes[0] if saved_hashes else None
            
    cursor = db.cursor()
    cursor.execute("""
    INSERT INTO items (
        type, title, description, category, primary_color, brand,
        latitude, longitude, location_name, date_occurred,
        contact_name, contact_email, contact_phone, custody_location,
        image_path, image_hash, status
    ) VALUES ('found', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
    """, (
        title, description, category, primary_color, brand,
        latitude, longitude, location_name, date_occurred,
        contact_name, contact_email, contact_phone, custody_location,
        image_path, image_hash
    ))
    db.commit()
    item_id = cursor.lastrowid
    
    # Run immediate tri-factor matching against lost items
    new_matches = HybridMatcher.match_item_against_all(item_id, db)
    
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item_data = dict(cursor.fetchone())
    return {
        "item": item_data,
        "matches_found": len(new_matches),
        "top_matches": sorted(new_matches, key=lambda x: x["composite_score"], reverse=True)[:3]
    }

@router.get("")
def list_items(
    type: Optional[str] = Query(None, pattern="^(lost|found)$"),
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: sqlite3.Connection = Depends(get_db)
):
    query = "SELECT * FROM items WHERE 1=1"
    params = []
    
    if type:
        query += " AND type = ?"
        params.append(type)
    if category and category.lower() != "all":
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)
    if status and status.lower() != "all":
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR location_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])
        
    query += " ORDER BY created_at DESC"
    
    cursor = db.cursor()
    cursor.execute(query, params)
    return [dict(r) for r in cursor.fetchall()]

@router.get("/{item_id}")
def get_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
        
    item = dict(row)
    
    # Fetch existing matches for this item
    if item["type"] == "lost":
        cursor.execute("""
            SELECT m.*, i.title as counterpart_title, i.image_path as counterpart_image,
                   i.category as counterpart_category, i.location_name as counterpart_location
            FROM matches m
            JOIN items i ON m.found_item_id = i.id
            WHERE m.lost_item_id = ?
            ORDER BY m.composite_score DESC
        """, (item_id,))
    else:
        cursor.execute("""
            SELECT m.*, i.title as counterpart_title, i.image_path as counterpart_image,
                   i.category as counterpart_category, i.location_name as counterpart_location
            FROM matches m
            JOIN items i ON m.lost_item_id = i.id
            WHERE m.found_item_id = ?
            ORDER BY m.composite_score DESC
        """, (item_id,))
        
    matches = [dict(r) for r in cursor.fetchall()]
    return {"item": item, "matches": matches}

@router.delete("/{item_id}")
def delete_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
    db.commit()
    return {"status": "deleted", "id": item_id}
