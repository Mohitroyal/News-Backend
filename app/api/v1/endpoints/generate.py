from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import Any, List
from app.api import deps
from app.db.session import get_db
from app.models.clipping import Clipping
from app.schemas.all import ClippingCreate, Clipping as ClippingSchema
from app.services.grok_service import grok_service
from app.services.render_service import render_service
from app.services.storage_service import storage_service, _rewrite_to_absolute
from app.auth.dependencies import get_current_active_user
from app.core.config import settings
from app.models.user import User
import uuid
import os
import logging
import traceback as _traceback
import sys
import asyncio
import gc
import psutil
from datetime import datetime, timedelta

# Concurrency control – Render free tier supports only one generation at a time
MAX_CONCURRENT_GENERATIONS = 1
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)


def _get_peak_memory() -> float:
    """Return peak memory usage (max RSS) in MB."""
    if sys.platform != 'win32':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    else:
        try:
            process = psutil.Process(os.getpid())
            return getattr(process.memory_info(), 'peak_wset', 0) / (1024 * 1024)
        except Exception:
            return 0.0


def _log_memory(stage: str):
    """Log current and peak memory usage in MB."""
    try:
        process = psutil.Process(os.getpid())
        current_mem = process.memory_info().rss / (1024 * 1024)
        peak_mem = _get_peak_memory()
        msg = f"[MEMORY] {stage} - Current RSS: {current_mem:.2f} MB | Peak RSS: {peak_mem:.2f} MB"
        logger.info(msg)
        print(msg)
        sys.stdout.flush()
        if current_mem > 450:
            print("[MEMORY WARNING] Memory usage is critically high! Approaching Render Free limit.")
            sys.stdout.flush()
            gc.collect()
    except Exception as e:
        logger.error(f"[MEMORY LOG ERROR] Failed to log memory: {e}")

router = APIRouter()

logger = logging.getLogger(__name__)


def _flush_error(stage: str, e: Exception) -> dict:
    """Extract and immediately print full exception details to stdout/logs."""
    exc_type = type(e).__name__
    exc_msg = str(e)
    tb_str = _traceback.format_exc()
    exc_tb = e.__traceback__
    file_info = ""
    line_info = ""
    func_info = ""
    if exc_tb:
        tb_frames = _traceback.extract_tb(exc_tb)
        if tb_frames:
            last = tb_frames[-1]
            file_info = os.path.basename(last.filename)
            line_info = str(last.lineno)
            func_info = last.name

    details = (
        f"[{exc_type}] in {file_info}:{line_info} ({func_info}): {exc_msg}"
    )

    # Print IMMEDIATELY to stdout so it appears in Render logs right away
    print("=" * 70)
    print(f"[PIPELINE FAILURE] Stage: {stage}")
    print(f"[EXCEPTION TYPE]   {exc_type}")
    print(f"[EXCEPTION MSG]    {exc_msg}")
    print(f"[FILE]             {file_info}")
    print(f"[LINE]             {line_info}")
    print(f"[FUNCTION]         {func_info}")
    print("[TRACEBACK]")
    print(tb_str)
    print("=" * 70)
    sys.stdout.flush()

    return {
        "stage": stage,
        "error_type": exc_type,
        "message": exc_msg,
        "error": exc_msg,
        "details": details,
        "traceback": tb_str,
    }

async def _async_process_clipping_task(clipping_id: Any, db: Session = None):
    """Core asynchronous logic - full debug mode with raw exception exposure."""
    print("GENERATION STARTED"); sys.stdout.flush()
    await _semaphore.acquire()
    print("LOCK ACQUIRED"); sys.stdout.flush()
    try:
        if isinstance(clipping_id, str):
            try:
                clipping_id = uuid.UUID(clipping_id)
            except Exception:
                pass

        is_external_db = db is not None
        if not is_external_db:
            from app.db.session import SessionLocal
            db = SessionLocal()

        # ── Permanent stage tracker: NEVER resets on retry ──────────────────────
        # This ensures we always know where the pipeline last failed.
        last_failed_stage = "initialization"

        max_retries = 2  # Allows up to 3 total attempts
        for attempt in range(max_retries + 1):
            stage = "initialization"
            try:
                clipping = db.query(Clipping).filter(Clipping.id == clipping_id).first()
                if not clipping:
                    logger.error("Database Update: FAILED (Clipping record not found)")
                    return

                print(f"\n{'='*70}")
                print(f"[PIPELINE START] Attempt {attempt + 1}/{max_retries + 1} | Clipping: {clipping_id}")
                print(f"{'='*70}")
                sys.stdout.flush()

                # --- [2] Image Processing ---
                stage = "Image Processing"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                from app.services.image_service import image_service
                safe_image_url = image_service.process_and_resize(clipping.image_url) if clipping.image_url else ""
                safe_image_urls = [image_service.process_and_resize(u) for u in (clipping.image_urls or [])]
                print(f"[COMPLETED] {stage}"); sys.stdout.flush()

                # --- [4] Content Generation & Translation ---
                stage = "Translation" if clipping.language and clipping.language.lower() != "en" else "Content Generation"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                formatted = await grok_service.format_article(clipping.article_content, clipping.language)
                clipping.content_formatted = formatted
                print(f"[COMPLETED] {stage}"); sys.stdout.flush()

                # --- Save to rendering ---
                stage = "Database Save (rendering)"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                print("START status update"); sys.stdout.flush()
                clipping.status = "rendering"
                db.commit()
                print("END status update"); sys.stdout.flush()
                print(f"[COMPLETED] {stage}"); sys.stdout.flush()

                # --- [5] Template Selection ---
                stage = "Template Selection"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                template_id = clipping.template_id or "classic"
                print(f"[COMPLETED] {stage} -> {template_id}"); sys.stdout.flush()

                # --- [7] HTML Generation & [6] Layout Rendering ---
                stage = "HTML Generation"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                owner = db.query(User).filter(User.id == clipping.user_id).first()
                is_premium = owner and owner.subscription_plan in ["pro", "enterprise"]

                safe_image_url = _rewrite_to_absolute(safe_image_url)
                safe_image_urls = [_rewrite_to_absolute(u) for u in safe_image_urls]

                render_data = {
                    **formatted,
                    "id": str(clipping_id),
                    "headline": clipping.headline,
                    "publication_name": clipping.publication_name,
                    "publication_date": clipping.publication_date,
                    "image_url": safe_image_url,
                    "image_urls": safe_image_urls,
                    "language": clipping.language,
                    "layout_columns": clipping.layout_columns,
                    "font_family": clipping.font_family or "playfair",
                    "logo_id": clipping.logo_id or clipping.template_id,
                    "is_premium": is_premium,
                    "show_watermark": clipping.show_watermark if clipping.show_watermark is not None else True,
                    "image_layout": getattr(clipping, "image_layout", "default"),
                    "heading_bg": getattr(clipping, "heading_bg", None),
                    "border_color": getattr(clipping, "border_color", None),
                }

                if clipping.template_id == "custom":
                    if not clipping.custom_layout:
                        clipping.status = "completed"
                        db.commit()
                        return
                    import os as _os
                    _frontend = settings.FRONTEND_URL or _os.getenv("RENDER_EXTERNAL_URL", "http://localhost:3000")
                    html = f"{_frontend.rstrip('/')}/render/{clipping_id}"
                else:
                    html = await render_service.render_html(render_data, f"{clipping.template_id}.html")
                    print(f"[COMPLETED] {stage} -> html len={len(html) if isinstance(html, str) else 'URL'}"); sys.stdout.flush()
                # --- [9] PNG & PDF Asset Generation ---
                stage = "Asset Generation"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                temp_png = f"temp_{clipping_id}.png"
                temp_pdf = f"temp_{clipping_id}.pdf"
                print(f"TEMP FILES CREATED: {temp_png}, {temp_pdf}"); sys.stdout.flush()
                try:
                    print("START asset generation"); sys.stdout.flush()
                    await asyncio.wait_for(render_service.generate_clipping_assets(html, temp_png, temp_pdf), timeout=90.0)
                    print("END asset generation"); sys.stdout.flush()
                    print(f"[COMPLETED] {stage}"); sys.stdout.flush()
                except Exception as asset_err:
                    err_str = f"{type(asset_err).__name__} {str(asset_err)}".lower()
                    if "executable" in err_str or "launch" in err_str or "chromium" in err_str or "browser" in err_str:
                        stage = "Chromium Launch Failed"
                    elif "timeout" in err_str:
                        stage = "Screenshot Timeout"
                    elif "memory" in err_str:
                        stage = "Memory Limit Exceeded"
                    else:
                        stage = "Page Rendering Failed"
                    last_failed_stage = stage
                    print(f"[FAILED] {stage} | {type(asset_err).__name__}: {asset_err}"); sys.stdout.flush()
                    raise asset_err

                # --- [10] Supabase Upload PNG ---
                stage = "Supabase Upload (PNG)"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                try:
                    png_url = storage_service.upload_file(temp_png, f"clippings/{clipping_id}.png")
                    if os.path.exists(temp_png):
                        os.remove(temp_png)
                        print(f"TEMP FILE DELETED: {temp_png}"); sys.stdout.flush()
                    print(f"[COMPLETED] {stage} -> {png_url}"); sys.stdout.flush()
                except Exception as png_up_err:
                    stage = "Supabase Upload Failed"
                    last_failed_stage = stage
                    print(f"[FAILED] {stage} | {type(png_up_err).__name__}: {png_up_err}"); sys.stdout.flush()
                    raise png_up_err

                # --- [11] Supabase Upload PDF ---
                stage = "Supabase Upload (PDF)"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                try:
                    pdf_url = storage_service.upload_file(temp_pdf, f"clippings/{clipping_id}.pdf")
                    if os.path.exists(temp_pdf):
                        os.remove(temp_pdf)
                        print(f"TEMP FILE DELETED: {temp_pdf}"); sys.stdout.flush()
                    print(f"[COMPLETED] {stage} -> {pdf_url}"); sys.stdout.flush()
                except Exception as pdf_up_err:
                    stage = "Supabase Upload Failed"
                    last_failed_stage = stage
                    print(f"[FAILED] {stage} | {type(pdf_up_err).__name__}: {pdf_up_err}"); sys.stdout.flush()
                    raise pdf_up_err

                # --- [13] Database Save (completed) ---
                stage = "Database Save (completed)"
                last_failed_stage = stage
                print(f"[STARTED] {stage}"); sys.stdout.flush()
                print("START status update"); sys.stdout.flush()
                clipping.png_url = png_url
                clipping.pdf_url = pdf_url
                clipping.status = "completed"

                if clipping.custom_layout and "error" in clipping.custom_layout:
                    del clipping.custom_layout["error"]
                    if "stage" in clipping.custom_layout:
                        del clipping.custom_layout["stage"]
                    temp_layout = dict(clipping.custom_layout)
                    clipping.custom_layout = temp_layout

                db.commit()
                print("END status update"); sys.stdout.flush()

                # --- [14] Email Notification ---
                stage = "Email Notification"
                logger.info(f"Stage: {stage}")
                try:
                    from app.services.email_service import email_service
                    if owner and owner.email:
                        email_service.send_clipping_status_email(
                            user_email=owner.email,
                            headline=clipping.headline,
                            status="completed",
                            png_url=png_url,
                            pdf_url=pdf_url
                        )
                except Exception as mail_err:
                    logger.warning(f"Failed to send success mail: {mail_err}")

                # --- [15] Final Response ---
                stage = "Final Response"
                logger.info(f"Stage: {stage}")
                break

            except Exception as e:
                # ── Immediately flush the raw exception to logs ──────────────────
                error_payload = _flush_error(stage, e)
                last_failed_stage = stage  # ensure it's captured

                if attempt < max_retries:
                    print(f"[AUTO-RECOVERY] Retrying pipeline in 3s (attempt {attempt + 1}/{max_retries})...")
                    sys.stdout.flush()
                    for temp_file in [f"temp_{clipping_id}.png", f"temp_{clipping_id}.pdf"]:
                        if os.path.exists(temp_file):
                            try:
                                os.remove(temp_file)
                                print(f"TEMP FILE DELETED: {temp_file}"); sys.stdout.flush()
                            except Exception:
                                pass
                    await asyncio.sleep(3)
                    continue

                # ── All retries exhausted — write failure to DB ──────────────────
                # Use a FRESH session to avoid stale transaction state
                print(f"[FINAL FAILURE] All {max_retries + 1} attempts failed at stage: {last_failed_stage}")
                sys.stdout.flush()

                # Clean up temp files
                for temp_file in [f"temp_{clipping_id}.png", f"temp_{clipping_id}.pdf"]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                            print(f"TEMP FILE DELETED: {temp_file}"); sys.stdout.flush()
                        except Exception:
                            pass

                # Write failure using fresh DB session to avoid stale connection
                from app.db.session import SessionLocal
                fresh_db = SessionLocal()
                try:
                    print("START status update"); sys.stdout.flush()
                    fresh_clipping = fresh_db.query(Clipping).filter(Clipping.id == clipping_id).first()
                    if fresh_clipping:
                        fresh_clipping.status = "failed"
                        fresh_clipping.custom_layout = error_payload
                        fresh_db.commit()
                        print("END status update"); sys.stdout.flush()
                        print(f"[DB SAVED] Failure status written to database for clipping {clipping_id}")
                        sys.stdout.flush()
                    else:
                        print(f"[DB ERROR] Could not find clipping {clipping_id} to write failure status")
                        sys.stdout.flush()
                except Exception as db_write_err:
                    print(f"[DB WRITE FAILURE] Failed to persist error to DB: {type(db_write_err).__name__}: {db_write_err}")
                    print(_traceback.format_exc())
                    sys.stdout.flush()
                    try:
                        fresh_db.rollback()
                    except Exception:
                        pass
                finally:
                    try:
                        fresh_db.close()
                    except Exception:
                        pass

                # Attempt failure email (best-effort)
                try:
                    from app.services.email_service import email_service
                    fresh_db2 = SessionLocal()
                    try:
                        owner = fresh_db2.query(User).filter(
                            User.id == (fresh_clipping.user_id if fresh_clipping else None)
                        ).first()
                        if owner and owner.email:
                            email_service.send_clipping_status_email(
                                user_email=owner.email,
                                headline=getattr(fresh_clipping, 'headline', 'Unknown'),
                                status="failed"
                            )
                    finally:
                        fresh_db2.close()
                except Exception as mail_err:
                    print(f"[MAIL WARNING] Failure email not sent: {mail_err}")

        if not is_external_db:
            try:
                db.close()
            except Exception:
                pass


    finally:
        _semaphore.release()
        print("LOCK RELEASED"); sys.stdout.flush()
        print("GENERATION COMPLETED"); sys.stdout.flush()
        gc.collect()


async def _background_process_clipping(clipping_id: Any):
    """Thin async wrapper registered directly with FastAPI BackgroundTasks.

    CRITICAL: Must be async so FastAPI runs it in the SAME uvicorn event loop.
    Has a hard 300-second wall-clock timeout so a task can NEVER hang forever.
    """
    print(f"[STEP 1] Task Created - clipping_id={clipping_id}"); sys.stdout.flush()
    try:
        await asyncio.wait_for(
            _async_process_clipping_task(clipping_id),
            timeout=300.0  # 5-minute hard cap — marks FAILED if exceeded
        )
    except asyncio.TimeoutError:
        print(f"[PIPELINE FATAL] Task {clipping_id} exceeded 300s global timeout. Marking FAILED.")
        sys.stdout.flush()
        try:
            from app.db.session import SessionLocal
            emergency_db = SessionLocal()
            try:
                emergency_clipping = emergency_db.query(Clipping).filter(Clipping.id == clipping_id).first()
                if emergency_clipping and emergency_clipping.status not in ("completed", "failed"):
                    emergency_clipping.status = "failed"
                    emergency_clipping.custom_layout = {
                        "stage": "Global Timeout",
                        "error_type": "TimeoutError",
                        "message": "Generation exceeded 300 second global timeout",
                        "error": "Generation timed out after 300 seconds",
                        "details": "The pipeline was forcibly terminated to prevent permanent hang",
                        "traceback": ""
                    }
                    emergency_db.commit()
                    print(f"[PIPELINE FATAL] Task {clipping_id} marked FAILED in DB."); sys.stdout.flush()
            finally:
                emergency_db.close()
        except Exception as emergency_err:
            print(f"[PIPELINE FATAL] Could not write timeout failure to DB: {emergency_err}"); sys.stdout.flush()
    except Exception as e:
        print(f"[PIPELINE FATAL] Unhandled exception in background task: {type(e).__name__}: {e}"); sys.stdout.flush()


@router.post("/", response_model=dict)
async def create_clipping(
    *,
    db: Session = Depends(get_db),
    clipping_in: ClippingCreate,
    current_user: User = Depends(get_current_active_user),
    background_tasks: BackgroundTasks
) -> Any:
    # 1. Premium template authorization check
    premium_templates = ["tabloid", "magazine"]
    if clipping_in.template_id in premium_templates and current_user.subscription_plan not in ["pro", "enterprise"]:
        raise HTTPException(
            status_code=403,
            detail="This premium template requires a Pro or Enterprise subscription."
        )

    # 2. Monthly generation limits check
    limit = 4000
    if current_user.subscription_plan == "pro":
        limit = 4000
    elif current_user.subscription_plan == "enterprise":
        limit = 4000

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    generations_count = db.query(Clipping).filter(
        Clipping.user_id == current_user.id,
        Clipping.created_at >= thirty_days_ago
    ).count()

    if generations_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Monthly clipping generation limit reached ({generations_count}/{limit}). You have used all 4000 clippings allowed per account."
        )

    clipping = Clipping(
        user_id=current_user.id,
        headline=clipping_in.headline,
        article_content=clipping_in.article_content,
        language=clipping_in.language,
        tone=clipping_in.tone,
        template_id=clipping_in.template_id,
        logo_id=clipping_in.logo_id or clipping_in.template_id,
        image_url=clipping_in.image_url,
        image_urls=clipping_in.image_urls or [],
        publication_name=clipping_in.publication_name,
        publication_date=clipping_in.publication_date,
        layout_columns=clipping_in.layout_columns,
        font_family=clipping_in.font_family or "playfair",
        show_watermark=clipping_in.show_watermark,
        status="processing"
    )
    db.add(clipping)
    db.commit()
    db.refresh(clipping)

    background_tasks.add_task(_background_process_clipping, clipping.id)

    return jsonable_encoder({
        "success": True,
        "data": clipping,
        "message": "Generation started successfully"
    })


# ── Stage → progress mapping (matches frontend) ───────────────────────────────
_STAGE_PROGRESS = {
    "initialization":           5,
    "Image Processing":         15,
    "Content Generation":       30,
    "Translation":              35,
    "Database Save (rendering)": 40,
    "Template Selection":       45,
    "HTML Generation":          55,
    "Screenshot Generation":    70,
    "Font Loading":             72,
    "Playwright Launch":        74,
    "PNG Screenshot Creation":  80,
    "Supabase Upload (PNG)":    85,
    "PDF Generation":           88,
    "PDF Creation":             90,
    "Supabase Upload (PDF)":    93,
    "Database Save (completed)": 97,
    "Email Notification":       99,
    "Final Response":           100,
}


def _enrich_clipping_response(clipping, resp_data: dict) -> dict:
    """
    Inject stage, progress, and (on failure) full error fields into
    every API response so the frontend can drive its progress bar and
    debug cards without re-fetching or guessing.
    """
    status = clipping.status or "processing"
    custom_layout = clipping.custom_layout or {}

    if status == "failed":
        stage = custom_layout.get("stage", "Unknown")
        resp_data["stage"]      = stage
        resp_data["progress"]   = 0
        resp_data["error_type"] = custom_layout.get("error_type", "UnknownError")
        resp_data["message"]    = custom_layout.get("message") or custom_layout.get("error") or "An unexpected error occurred"
        resp_data["error"]      = custom_layout.get("error") or "An unexpected error occurred"
        resp_data["details"]    = custom_layout.get("details", "")
        resp_data["traceback"]  = custom_layout.get("traceback", "")

    elif status == "completed":
        resp_data["stage"]    = "Final Response"
        resp_data["progress"] = 100

    else:
        # processing / rendering — surface the last known stage from custom_layout
        # (the pipeline writes a heartbeat there when it starts each stage)
        stage = custom_layout.get("current_stage", "processing")
        resp_data["stage"]    = stage
        resp_data["progress"] = _STAGE_PROGRESS.get(stage, 10)
        resp_data["current_stage"] = stage

    return resp_data


@router.get("/", response_model=dict)
def get_all_clippings(
    page: int = 1,
    pageSize: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    skip = (page - 1) * pageSize
    clippings = db.query(Clipping).filter(Clipping.user_id == current_user.id).order_by(Clipping.created_at.desc()).offset(skip).limit(pageSize).all()
    total = db.query(Clipping).filter(Clipping.user_id == current_user.id).count()

    serialized_items = []
    for clipping in clippings:
        resp_data = jsonable_encoder(clipping)
        resp_data = _enrich_clipping_response(clipping, resp_data)
        serialized_items.append(resp_data)

    return jsonable_encoder({
        "success": True,
        "data": {
            "items": serialized_items,
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "totalPages": (total + pageSize - 1) // pageSize
        },
        "message": "Clippings retrieved successfully"
    })


@router.get("/{id}", response_model=dict)
def get_clipping(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    clipping = db.query(Clipping).filter(Clipping.id == id, Clipping.user_id == current_user.id).first()
    if not clipping:
        raise HTTPException(status_code=404, detail="Clipping not found")

    resp_data = jsonable_encoder(clipping)
    resp_data = _enrich_clipping_response(clipping, resp_data)

    return jsonable_encoder({
        "success": True,
        "data": resp_data,
        "message": "Clippings retrieved successfully"
    })


@router.get("/{id}/public", response_model=dict)
def get_clipping_public(
    id: uuid.UUID,
    db: Session = Depends(get_db)
) -> Any:
    # Public read-only access for the headless renderer (UUID acts as capability)
    clipping = db.query(Clipping).filter(Clipping.id == id).first()
    if not clipping:
        raise HTTPException(status_code=404, detail="Clipping not found")
        
    resp_data = jsonable_encoder(clipping)
    resp_data = _enrich_clipping_response(clipping, resp_data)

    return jsonable_encoder({
        "success": True,
        "data": resp_data,
        "message": "Clippings retrieved successfully"
    })


@router.delete("/{id}", response_model=dict)
def delete_clipping(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    clipping = db.query(Clipping).filter(Clipping.id == id, Clipping.user_id == current_user.id).first()
    if not clipping:
        raise HTTPException(status_code=404, detail="Clipping not found")

    db.delete(clipping)
    db.commit()
    return jsonable_encoder({
        "success": True,
        "data": None,
        "message": "Clipping deleted successfully"
    })


from pydantic import BaseModel


class LayoutUpdate(BaseModel):
    custom_layout: dict


@router.put("/{id}/layout", response_model=dict)
def update_clipping_layout(
    id: uuid.UUID,
    layout_in: LayoutUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    clipping = db.query(Clipping).filter(Clipping.id == id, Clipping.user_id == current_user.id).first()
    if not clipping:
        raise HTTPException(status_code=404, detail="Clipping not found")

    clipping.custom_layout = layout_in.custom_layout
    clipping.status = "rendering"
    db.commit()

    background_tasks.add_task(process_clipping_task, clipping.id)

    return jsonable_encoder({
        "success": True,
        "data": clipping,
        "message": "Layout saved and re-rendering started"
    })
