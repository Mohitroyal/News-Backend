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
from datetime import datetime, timedelta

router = APIRouter()

import sys
import asyncio

logger = logging.getLogger(__name__)

async def _async_process_clipping_task(clipping_id: Any, db: Session = None):
    """Core asynchronous logic for formatting and rendering with explicit step-by-step instrumentation and auto-recovery."""
    if isinstance(clipping_id, str):
        try:
            clipping_id = uuid.UUID(clipping_id)
        except Exception:
            pass

    is_external_db = db is not None
    if not is_external_db:
        from app.db.session import SessionLocal
        db = SessionLocal()

    max_retries = 2  # Allows up to 3 total attempts
    for attempt in range(max_retries + 1):
        stage = "initialization"
        try:
            clipping = db.query(Clipping).filter(Clipping.id == clipping_id).first()
            if not clipping:
                logger.error("Database Update: FAILED (Clipping record not found)")
                return

            print(f"\n--- GENERATION PIPELINE START (Attempt {attempt + 1}/{max_retries + 1}) ---")

            # --- [2] Image Processing ---
            stage = "Image Processing"
            logger.info(f"Stage: {stage}")
            from app.services.image_service import image_service
            safe_image_url = image_service.process_and_resize(clipping.image_url) if clipping.image_url else ""
            safe_image_urls = [image_service.process_and_resize(u) for u in (clipping.image_urls or [])]

            # --- [4] Content Generation & Translation ---
            stage = "Translation" if clipping.language and clipping.language.lower() != "en" else "Content Generation"
            logger.info(f"Stage: {stage}")
            formatted = await grok_service.format_article(clipping.article_content, clipping.language)
            clipping.content_formatted = formatted
            
            # --- Save to rendering ---
            stage = "Database Save"
            logger.info(f"Stage: {stage}")
            clipping.status = "rendering"
            db.commit()

            # --- [5] Template Selection ---
            stage = "Template Selection"
            logger.info(f"Stage: {stage}")
            template_id = clipping.template_id or "classic"

            # --- [7] HTML Generation & [6] Layout Rendering ---
            stage = "HTML Generation"
            logger.info(f"Stage: {stage}")
            owner = db.query(User).filter(User.id == clipping.user_id).first()
            is_premium = owner and owner.subscription_plan in ["pro", "enterprise"]
            
            safe_image_url = _rewrite_to_absolute(safe_image_url)
            safe_image_urls = [_rewrite_to_absolute(u) for u in safe_image_urls]

            render_data = {
                **formatted,
                "id": str(clipping_id),
                "publication_name": clipping.publication_name,
                "publication_date": clipping.publication_date,
                "image_url": safe_image_url,
                "image_urls": safe_image_urls,
                "language": clipping.language,
                "layout_columns": clipping.layout_columns,
                "font_family": clipping.font_family or "playfair",
                "logo_id": clipping.logo_id or clipping.template_id,
                "is_premium": is_premium,
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

            # --- [9] Screenshot Generation ---
            stage = "Screenshot Generation"
            logger.info(f"Stage: {stage}")
            temp_png = f"temp_{clipping_id}.png"
            try:
                await render_service.generate_png(html, temp_png)
            except Exception as png_err:
                err_str = str(png_err)
                if "[7] Font Loading" in err_str:
                    stage = "Font Loading"
                elif "[8] Playwright Launch" in err_str:
                    stage = "Layout Rendering"
                elif "[9] Screenshot Creation" in err_str:
                    stage = "PNG Creation"
                else:
                    stage = "Screenshot Generation"
                raise png_err

            # --- [10] Supabase Upload PNG ---
            stage = "Supabase Upload"
            logger.info("Stage: Uploading PNG")
            png_url = storage_service.upload_file(temp_png, f"clippings/{clipping_id}.png")
            if os.path.exists(temp_png):
                os.remove(temp_png)

            # --- [11] PDF Generation ---
            stage = "PDF Generation"
            logger.info(f"Stage: {stage}")
            temp_pdf = f"temp_{clipping_id}.pdf"
            try:
                await render_service.generate_pdf(html, temp_pdf)
            except Exception as pdf_err:
                err_str = str(pdf_err)
                if "[7] Font Loading" in err_str:
                    stage = "Font Loading"
                elif "[8] Playwright Launch" in err_str:
                    stage = "Layout Rendering"
                elif "[11] PDF Creation" in err_str:
                    stage = "PDF Generation"
                else:
                    stage = "PDF Generation"
                raise pdf_err

            # --- [12] Supabase Upload PDF ---
            stage = "Supabase Upload"
            logger.info("Stage: Uploading PDF")
            pdf_url = storage_service.upload_file(temp_pdf, f"clippings/{clipping_id}.pdf")
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)

            # --- [13] Database Save ---
            stage = "Database Save"
            logger.info(f"Stage: {stage}")
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
            logger.exception(e)
            error_msg = str(e)
            error_type = type(e).__name__
            
            # Detailed Exception Metadata Extraction
            import sys
            import traceback
            exc_type, exc_value, exc_tb = sys.exc_info()
            tb_info = traceback.extract_tb(exc_tb)
            if tb_info:
                filename, line, func, text = tb_info[-1]
                filename = os.path.basename(filename)
                details = f"Exception {error_type} in file {filename} at line {line} in function {func}: {error_msg}"
            else:
                details = error_msg
                
            traceback_str = traceback.format_exc()
            print(f"\n[PIPELINE FAILURE] Stage: {stage} | Reason: {error_msg}")

            if attempt < max_retries:
                print(f"[AUTO-RECOVERY] Retrying the entire pipeline in 3 seconds... (Attempt {attempt + 1}/{max_retries})")
                for temp_file in [f"temp_{clipping_id}.png", f"temp_{clipping_id}.pdf"]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass
                await asyncio.sleep(3)
                continue

            # Final attempt failed, mark status as failed and store details
            try:
                clipping.status = "failed"
                clipping.custom_layout = {
                    "stage": stage,
                    "error_type": error_type,
                    "message": error_msg,
                    "error": error_msg,
                    "details": details,
                    "traceback": traceback_str
                }
                db.commit()

                # Clean up any remaining temp files on final failure
                for temp_file in [f"temp_{clipping_id}.png", f"temp_{clipping_id}.pdf"]:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass

                try:
                    from app.services.email_service import email_service
                    owner = db.query(User).filter(User.id == clipping.user_id).first()
                    if owner and owner.email:
                        email_service.send_clipping_status_email(
                            user_email=owner.email,
                            headline=clipping.headline,
                            status="failed"
                        )
                except Exception as mail_err:
                    logger.warning(f"Failed to send failure mail: {mail_err}")
            except Exception as final_err:
                logger.error(f"Failed to write failure status to database: {final_err}")
            
    if not is_external_db:
        db.close()


def process_clipping_task(clipping_id: Any, db: Session = None):
    """Background task wrapper to handle asyncio event loop policy on Windows."""
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_async_process_clipping_task(clipping_id, db))


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
    limit = 50
    if current_user.subscription_plan == "pro":
        limit = 100
    elif current_user.subscription_plan == "enterprise":
        limit = 99999

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    generations_count = db.query(Clipping).filter(
        Clipping.user_id == current_user.id,
        Clipping.created_at >= thirty_days_ago
    ).count()

    if generations_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Monthly clipping generation limit reached ({generations_count}/{limit}). Please upgrade your plan."
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
        status="processing"
    )
    db.add(clipping)
    db.commit()
    db.refresh(clipping)

    background_tasks.add_task(process_clipping_task, clipping.id)

    return jsonable_encoder({
        "success": True,
        "data": clipping,
        "message": "Generation started successfully"
    })


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
        if clipping.status == "failed":
            custom_layout = clipping.custom_layout or {}
            resp_data["stage"] = custom_layout.get("stage", "Unknown")
            resp_data["error_type"] = custom_layout.get("error_type", "UnknownError")
            resp_data["message"] = custom_layout.get("message") or custom_layout.get("error") or "An unexpected error occurred"
            resp_data["error"] = custom_layout.get("error") or "An unexpected error occurred"
            resp_data["details"] = custom_layout.get("details", "")
            resp_data["traceback"] = custom_layout.get("traceback", "")
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
    if clipping.status == "failed":
        custom_layout = clipping.custom_layout or {}
        resp_data["stage"] = custom_layout.get("stage", "Unknown")
        resp_data["error_type"] = custom_layout.get("error_type", "UnknownError")
        resp_data["message"] = custom_layout.get("message") or custom_layout.get("error") or "An unexpected error occurred"
        resp_data["error"] = custom_layout.get("error") or "An unexpected error occurred"
        resp_data["details"] = custom_layout.get("details", "")
        resp_data["traceback"] = custom_layout.get("traceback", "")

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
    if clipping.status == "failed":
        custom_layout = clipping.custom_layout or {}
        resp_data["stage"] = custom_layout.get("stage", "Unknown")
        resp_data["error_type"] = custom_layout.get("error_type", "UnknownError")
        resp_data["message"] = custom_layout.get("message") or custom_layout.get("error") or "An unexpected error occurred"
        resp_data["error"] = custom_layout.get("error") or "An unexpected error occurred"
        resp_data["details"] = custom_layout.get("details", "")
        resp_data["traceback"] = custom_layout.get("traceback", "")
        
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
