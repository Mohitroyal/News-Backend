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
from app.services.storage_service import storage_service
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
    """Core asynchronous logic for formatting and rendering."""
    if isinstance(clipping_id, str):
        try:
            clipping_id = uuid.UUID(clipping_id)
        except Exception:
            pass

    is_external_db = db is not None
    if not is_external_db:
        from app.db.session import SessionLocal
        db = SessionLocal()

    try:
        clipping = db.query(Clipping).filter(Clipping.id == clipping_id).first()
        if not clipping:
            return

        # 1. AI Formatting
        formatted = await grok_service.format_article(clipping.article_content, clipping.language)
        clipping.content_formatted = formatted
        clipping.status = "rendering"
        db.commit()

        # 2. Render HTML
        owner = db.query(User).filter(User.id == clipping.user_id).first()
        is_premium = owner and owner.subscription_plan in ["pro", "enterprise"]

        render_data = {
            **formatted,
            "id": str(clipping_id),
            "publication_name": clipping.publication_name,
            "publication_date": clipping.publication_date,
            "image_url": clipping.image_url,
            "image_urls": clipping.image_urls or [],
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

        # 3. Generate PNG
        temp_png = f"temp_{clipping_id}.png"
        await render_service.generate_png(html, temp_png)
        png_url = storage_service.upload_file(temp_png, f"clippings/{clipping_id}.png")
        os.remove(temp_png)

        # 4. Generate PDF
        temp_pdf = f"temp_{clipping_id}.pdf"
        await render_service.generate_pdf(html, temp_pdf)
        pdf_url = storage_service.upload_file(temp_pdf, f"clippings/{clipping_id}.pdf")
        os.remove(temp_pdf)

        # 5. Update Record
        clipping.png_url = png_url
        clipping.pdf_url = pdf_url
        clipping.status = "completed"
        db.commit()

        # Send email update
        try:
            from app.services.email_service import email_service
            owner = db.query(User).filter(User.id == clipping.user_id).first()
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

    except Exception as e:
        try:
            clipping.status = "failed"
            db.commit()

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
        except Exception:
            pass
        print(f"Error processing clipping {clipping_id}: {repr(e)}")
    finally:
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

    return jsonable_encoder({
        "success": True,
        "data": {
            "items": clippings,
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
    return jsonable_encoder({
        "success": True,
        "data": clipping,
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
