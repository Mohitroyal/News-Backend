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
from datetime import datetime, timedelta

router = APIRouter()

import sys
import asyncio

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
                print("[13] Database Update: FAILED (Clipping record not found)")
                return

            print(f"\n--- GENERATION PIPELINE START (Attempt {attempt + 1}/{max_retries + 1}) ---")

            # --- [3] Image Resize ---
            stage = "image_resize"
            print(f"[3] Image Resize: Started")
            from app.services.image_service import image_service
            try:
                safe_image_url = image_service.process_and_resize(clipping.image_url) if clipping.image_url else ""
                safe_image_urls = [image_service.process_and_resize(u) for u in (clipping.image_urls or [])]
                print(f"[3] Image Resize: SUCCESS")
            except Exception as img_err:
                print(f"[3] Image Resize: FAILED ({img_err})")
                raise Exception(f"Image dimensions exceeded limits or processing failed: {img_err}")

            # --- [4] OCR/Article Processing ---
            stage = "article_processing"
            print(f"[4] OCR/Article Processing: Started")
            try:
                formatted = await grok_service.format_article(clipping.article_content, clipping.language)
                clipping.content_formatted = formatted
                clipping.status = "rendering"
                db.commit()
                print(f"[4] OCR/Article Processing: SUCCESS")
            except Exception as ocr_err:
                print(f"[4] OCR/Article Processing: FAILED ({ocr_err})")
                raise Exception(f"Article processing failed: {ocr_err}")

            # --- [5] Template Selection ---
            stage = "template_selection"
            print(f"[5] Template Selection: Started")
            try:
                # Selecting the template
                template_id = clipping.template_id or "classic"
                print(f"[5] Template Selection: SUCCESS (Selected: {template_id})")
            except Exception as temp_err:
                print(f"[5] Template Selection: FAILED ({temp_err})")
                raise Exception(f"Template selection failed: {temp_err}")

            # --- [6] HTML Generation ---
            stage = "html_generation"
            print(f"[6] HTML Generation: Started")
            try:
                owner = db.query(User).filter(User.id == clipping.user_id).first()
                is_premium = owner and owner.subscription_plan in ["pro", "enterprise"]
                
                # Rewrite image URLs to absolute so Playwright can load them
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
                        print(f"[6] HTML Generation: SUCCESS (Custom layout empty, skipping render)")
                        return
                    import os as _os
                    _frontend = settings.FRONTEND_URL or _os.getenv("RENDER_EXTERNAL_URL", "http://localhost:3000")
                    html = f"{_frontend.rstrip('/')}/render/{clipping_id}"
                else:
                    html = await render_service.render_html(render_data, f"{clipping.template_id}.html")
                print(f"[6] HTML Generation: SUCCESS")
            except Exception as html_err:
                print(f"[6] HTML Generation: FAILED ({html_err})")
                raise Exception(f"HTML generation failed: {html_err}")

            # Steps [7] (Font Loading) & [8] (Playwright Launch) & [9] (Screenshot Creation)
            # are executed internally inside render_service.generate_png
            stage = "screenshot_generation"
            temp_png = f"temp_{clipping_id}.png"
            try:
                await render_service.generate_png(html, temp_png)
            except Exception as png_err:
                # Map internal failures to correct stages
                err_str = str(png_err)
                if "[7] Font Loading" in err_str:
                    stage = "font_loading"
                elif "[8] Playwright Launch" in err_str:
                    stage = "playwright_launch"
                else:
                    stage = "screenshot_generation"
                raise Exception(f"Playwright timeout or screenshot failed: {png_err}")

            # --- [10] PNG Upload ---
            stage = "png_upload"
            print(f"[10] PNG Upload: Started")
            try:
                png_url = storage_service.upload_file(temp_png, f"clippings/{clipping_id}.png")
                import os
                if os.path.exists(temp_png):
                    os.remove(temp_png)
                print(f"[10] PNG Upload: SUCCESS (URL: {png_url})")
            except Exception as up_err:
                print(f"[10] PNG Upload: FAILED ({up_err})")
                raise Exception(f"Supabase upload failed: {up_err}")

            # Steps [7] (Font Loading) & [8] (Playwright Launch) & [11] (PDF Creation)
            # are executed internally inside render_service.generate_pdf
            stage = "pdf_generation"
            temp_pdf = f"temp_{clipping_id}.pdf"
            try:
                await render_service.generate_pdf(html, temp_pdf)
            except Exception as pdf_err:
                err_str = str(pdf_err)
                if "[7] Font Loading" in err_str:
                    stage = "font_loading"
                elif "[8] Playwright Launch" in err_str:
                    stage = "playwright_launch"
                else:
                    stage = "pdf_generation"
                raise Exception(f"Playwright timeout or PDF creation failed: {pdf_err}")

            # --- [12] PDF Upload ---
            stage = "pdf_upload"
            print(f"[12] PDF Upload: Started")
            try:
                pdf_url = storage_service.upload_file(temp_pdf, f"clippings/{clipping_id}.pdf")
                import os
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
                print(f"[12] PDF Upload: SUCCESS (URL: {pdf_url})")
            except Exception as up_err:
                print(f"[12] PDF Upload: FAILED ({up_err})")
                raise Exception(f"Supabase upload failed: {up_err}")

            # --- [13] Database Update ---
            stage = "database_update"
            print(f"[13] Database Update: Started")
            try:
                clipping.png_url = png_url
                clipping.pdf_url = pdf_url
                clipping.status = "completed"
                
                # Clear previous custom_layout errors
                if clipping.custom_layout and "error" in clipping.custom_layout:
                    del clipping.custom_layout["error"]
                    if "stage" in clipping.custom_layout:
                        del clipping.custom_layout["stage"]
                    temp_layout = dict(clipping.custom_layout)
                    clipping.custom_layout = temp_layout

                db.commit()
                print(f"[13] Database Update: SUCCESS")
            except Exception as db_err:
                print(f"[13] Database Update: FAILED ({db_err})")
                raise Exception(f"Database update failed: {db_err}")

            # Send Email
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
                print(f"Failed to send success mail: {mail_err}")
                
            break  # Generation succeeded, break the retry loop

        except Exception as e:
            error_msg = str(e)
            print(f"\n[PIPELINE FAILURE] Stage: {stage} | Reason: {error_msg}")
            
            # Map stage to user-friendly names for step console logging
            stage_to_step = {
                "image_resize": "[3] Image Resize",
                "article_processing": "[4] OCR/Article Processing",
                "template_selection": "[5] Template Selection",
                "html_generation": "[6] HTML Generation",
                "font_loading": "[7] Font Loading",
                "playwright_launch": "[8] Playwright Launch",
                "screenshot_generation": "[9] Screenshot Creation",
                "png_upload": "[10] PNG Upload",
                "pdf_generation": "[11] PDF Creation",
                "pdf_upload": "[12] PDF Upload",
                "database_update": "[13] Database Update"
            }
            step_name = stage_to_step.get(stage, f"Stage: {stage}")
            print(f"{step_name}: FAILED (Reason: {error_msg})")

            import traceback
            traceback.print_exc()

            if attempt < max_retries:
                print(f"[AUTO-RECOVERY] Retrying the entire pipeline in 3 seconds... (Attempt {attempt + 1}/{max_retries})")
                # Clean up any temp files if they exist before retrying
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
                temp_layout = clipping.custom_layout or {}
                temp_layout["stage"] = stage
                temp_layout["error"] = error_msg
                clipping.custom_layout = temp_layout
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
                    print(f"Failed to send failure mail: {mail_err}")
            except Exception as final_err:
                print(f"Failed to write failure status to database: {final_err}")
            
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
            resp_data["stage"] = custom_layout.get("stage", "unknown")
            resp_data["message"] = custom_layout.get("error", "An unexpected error occurred during clipping generation.")
            resp_data["error"] = custom_layout.get("error", "An unexpected error occurred during clipping generation.")
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
        resp_data["stage"] = custom_layout.get("stage", "unknown")
        resp_data["message"] = custom_layout.get("error", "An unexpected error occurred during clipping generation.")
        resp_data["error"] = custom_layout.get("error", "An unexpected error occurred during clipping generation.")

    return jsonable_encoder({
        "success": True,
        "data": resp_data,
        "message": "Clipping retrieved successfully"
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
    return jsonable_encoder({
        "success": True,
        "data": clipping,
        "message": "Clipping retrieved successfully"
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
