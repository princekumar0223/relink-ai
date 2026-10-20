import sqlite3
from typing import Dict, Any, Tuple, Optional
from .visual_matcher import VisualMatcher
from .text_matcher import TextMatcher
from .geo_matcher import GeoMatcher
from ..config import settings

class HybridMatcher:
    """
    Fuses Visual, Semantic/Textual, and Geospatial engines into a single composite match score.
    Automatically evaluates pairs and stores high-confidence candidate matches.
    """
    
    @classmethod
    def evaluate_pair(
        cls,
        lost_item: Dict[str, Any],
        found_item: Dict[str, Any],
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculates all 3 sub-scores and the composite score with fast heuristic pre-filtering.
        """
        # 1. Geospatial Match (Instant 0ms calculation)
        g_score, dist_m, g_reason = GeoMatcher.match(
            lat1=float(lost_item["latitude"]),
            lon1=float(lost_item["longitude"]),
            loc_name1=lost_item.get("location_name", ""),
            lat2=float(found_item["latitude"]),
            lon2=float(found_item["longitude"]),
            loc_name2=found_item.get("location_name", "")
        )

        has_v1 = bool(lost_item.get("image_path"))
        has_v2 = bool(found_item.get("image_path"))

        cat1 = (lost_item.get("category") or "").strip().lower()
        cat2 = (found_item.get("category") or "").strip().lower()
        cat_compat_score = TextMatcher._category_score(cat1, cat2)

        tokens1 = TextMatcher._clean_tokens((lost_item.get("title") or "") + " " + (lost_item.get("description") or ""))
        tokens2 = TextMatcher._clean_tokens((found_item.get("title") or "") + " " + (found_item.get("description") or ""))
        shared_tokens = tokens1.intersection(tokens2)

        # Fast heuristic rejection: if categories are completely unrelated and no words overlap,
        # avoid redundant Gemini API network roundtrips to keep execution ultra-fast!
        if cat_compat_score <= 0.15 and not shared_tokens:
            t_score = 0.05
            t_reason = f"Distinct categories ({cat1} vs {cat2}) with no matching descriptor keywords."
            v_score = 0.0
            v_reason = "Visual comparison bypassed for dissimilar categories."
        else:
            # 2. Text / Semantic Match
            t_score, t_reason = TextMatcher.match(
                title1=lost_item.get("title", ""),
                desc1=lost_item.get("description", ""),
                cat1=lost_item.get("category", ""),
                brand1=lost_item.get("brand"),
                color1=lost_item.get("primary_color"),
                title2=found_item.get("title", ""),
                desc2=found_item.get("description", ""),
                cat2=found_item.get("category", ""),
                brand2=found_item.get("brand"),
                color2=found_item.get("primary_color"),
                api_key=api_key
            )

            # 3. Visual Match
            v_score, v_reason = VisualMatcher.match(
                lost_item.get("image_path"), lost_item.get("image_hash"),
                found_item.get("image_path"), found_item.get("image_hash"),
                api_key=api_key
            )

        # 4. Weighted Composite Score
        if not has_v1 or not has_v2:
            # Rebalance weights if images are missing
            w_text = 0.55
            w_geo = 0.45
            composite = (t_score * w_text) + (g_score * w_geo)
        else:
            w_v = settings.WEIGHT_VISUAL
            w_t = settings.WEIGHT_TEXT
            w_g = settings.WEIGHT_GEO
            composite = (v_score * w_v) + (t_score * w_t) + (g_score * w_g)

        composite = round(max(0.0, min(1.0, composite)), 4)
        
        # 5. Synthesize Unified AI Reasoning Summary
        confidence_label = "High Confidence" if composite >= settings.MATCH_ALERT_THRESHOLD else (
            "Potential Candidate" if composite >= settings.CANDIDATE_THRESHOLD else "Low Match Probability"
        )
        
        summary_lines = [
            f"[{confidence_label} - Match Score: {int(composite * 100)}%]",
            f"• Location Proximity ({int(g_score * 100)}%): {g_reason}",
            f"• Description & Category ({int(t_score * 100)}%): {t_reason}",
            f"• Visual Correspondence ({int(v_score * 100)}%): {v_reason}"
        ]
        
        ai_reasoning = "\n".join(summary_lines)
        
        return {
            "lost_item_id": lost_item["id"],
            "found_item_id": found_item["id"],
            "visual_score": v_score,
            "text_score": t_score,
            "geo_score": g_score,
            "composite_score": composite,
            "distance_meters": dist_m,
            "ai_reasoning": ai_reasoning
        }

    @classmethod
    def match_item_against_all(cls, item_id: int, conn: sqlite3.Connection, api_key: Optional[str] = None):
        """
        When an item is newly created or updated, evaluate it against all opposite-type items.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        source_row = cursor.fetchone()
        if not source_row:
            return []
            
        source_item = dict(source_row)
        target_type = "found" if source_item["type"] == "lost" else "lost"
        
        cursor.execute("SELECT * FROM items WHERE type = ? AND status IN ('active', 'matched')", (target_type,))
        targets = [dict(r) for r in cursor.fetchall()]
        
        matches_found = []
        for target in targets:
            if source_item["type"] == "lost":
                lost_i, found_i = source_item, target
            else:
                lost_i, found_i = target, source_item
                
            result = cls.evaluate_pair(lost_i, found_i, api_key=api_key)
            
            # If composite score meets candidate threshold, save/update in DB
            if result["composite_score"] >= settings.CANDIDATE_THRESHOLD:
                cursor.execute("""
                INSERT INTO matches (
                    lost_item_id, found_item_id, visual_score, text_score,
                    geo_score, composite_score, distance_meters, ai_reasoning, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(lost_item_id, found_item_id) DO UPDATE SET
                    visual_score = excluded.visual_score,
                    text_score = excluded.text_score,
                    geo_score = excluded.geo_score,
                    composite_score = excluded.composite_score,
                    distance_meters = excluded.distance_meters,
                    ai_reasoning = excluded.ai_reasoning;
                """, (
                    result["lost_item_id"], result["found_item_id"],
                    result["visual_score"], result["text_score"], result["geo_score"],
                    result["composite_score"], result["distance_meters"], result["ai_reasoning"]
                ))
                
                # Fetch match record to check email notification status
                cursor.execute("SELECT id, email_notified FROM matches WHERE lost_item_id = ? AND found_item_id = ?",
                               (result["lost_item_id"], result["found_item_id"]))
                match_row = cursor.fetchone()
                if match_row:
                    m_id = match_row[0]
                    notified = bool(match_row[1]) if len(match_row) > 1 and match_row[1] is not None else False
                    result["id"] = m_id
                    
                    # User condition: if AI matching score >= 70% (0.70), send email notification to lost item owner
                    if result["composite_score"] >= settings.EMAIL_ALERT_THRESHOLD and not notified:
                        try:
                            from ..utils.email_notifier import send_match_notification
                            send_match_notification(lost_i, found_i, result, conn)
                        except Exception as e:
                            print(f"[WARN] Failed to send email alert: {e}")
                
                matches_found.append(result)
                
        conn.commit()
        return matches_found

    @classmethod
    def recalculate_all(cls, conn: sqlite3.Connection, api_key: Optional[str] = None):
        """
        Recalculate matches across all active lost vs found items.
        """
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE type = 'lost' AND status IN ('active', 'matched')")
        lost_items = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM items WHERE type = 'found' AND status IN ('active', 'matched')")
        found_items = [dict(r) for r in cursor.fetchall()]
        
        total_created = 0
        for l_item in lost_items:
            for f_item in found_items:
                res = cls.evaluate_pair(l_item, f_item, api_key=api_key)
                if res["composite_score"] >= settings.CANDIDATE_THRESHOLD:
                    cursor.execute("""
                    INSERT INTO matches (
                        lost_item_id, found_item_id, visual_score, text_score,
                        geo_score, composite_score, distance_meters, ai_reasoning, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                    ON CONFLICT(lost_item_id, found_item_id) DO UPDATE SET
                        visual_score = excluded.visual_score,
                        text_score = excluded.text_score,
                        geo_score = excluded.geo_score,
                        composite_score = excluded.composite_score,
                        distance_meters = excluded.distance_meters,
                        ai_reasoning = excluded.ai_reasoning;
                    """, (
                        res["lost_item_id"], res["found_item_id"],
                        res["visual_score"], res["text_score"], res["geo_score"],
                        res["composite_score"], res["distance_meters"], res["ai_reasoning"]
                    ))
                    
                    cursor.execute("SELECT id, email_notified FROM matches WHERE lost_item_id = ? AND found_item_id = ?",
                                   (res["lost_item_id"], res["found_item_id"]))
                    m_row = cursor.fetchone()
                    if m_row:
                        m_id = m_row[0]
                        notified = bool(m_row[1]) if len(m_row) > 1 and m_row[1] is not None else False
                        res["id"] = m_id
                        if res["composite_score"] >= settings.EMAIL_ALERT_THRESHOLD and not notified:
                            try:
                                from ..utils.email_notifier import send_match_notification
                                send_match_notification(l_item, f_item, res, conn)
                            except Exception as e:
                                print(f"[WARN] Failed to send email alert during recalculation: {e}")
                                
                    total_created += 1
        conn.commit()
        return total_created
