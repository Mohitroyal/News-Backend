from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import stripe
from typing import Any

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.auth.dependencies import get_current_active_user
from app.services.stripe_service import stripe_service
from app.core.config import settings

router = APIRouter()

@router.get("/plans", response_model=dict)
def get_plans() -> Any:
    """
    Get all subscription plans
    """
    plans = [
        {
            "id": "free",
            "name": "Free",
            "monthlyPrice": 0,
            "annualPrice": 0,
            "features": ["5 generations/month", "Watermarked exports", "Standard quality (72 dpi)", "Basic English support", "1 basic template"],
            "creditsPerMonth": 5,
            "maxExportsPerMonth": 5,
            "highResExport": False,
            "apiAccess": False,
            "customBranding": False
        },
        {
            "id": "pro",
            "name": "Pro",
            "monthlyPrice": 19,
            "annualPrice": 15,
            "features": ["100 generations/month", "No watermark", "High-res PNG & PDF (300 dpi)", "All 6+ languages", "All 20+ templates", "Priority support"],
            "creditsPerMonth": 100,
            "maxExportsPerMonth": 100,
            "highResExport": True,
            "apiAccess": False,
            "customBranding": False
        },
        {
            "id": "enterprise",
            "name": "Enterprise",
            "monthlyPrice": 59,
            "annualPrice": 49,
            "features": ["Unlimited generations", "No watermark", "High-res PNG & PDF (300 dpi)", "All 6+ languages", "All 20+ templates", "REST API access", "Custom branding & fonts", "Dedicated support"],
            "creditsPerMonth": 99999,
            "maxExportsPerMonth": 99999,
            "highResExport": True,
            "apiAccess": True,
            "customBranding": True
        }
    ]
    return jsonable_encoder({
        "success": True,
        "data": plans,
        "message": "Plans retrieved successfully"
    })

@router.get("/current", response_model=dict)
def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get current user's subscription details
    """
    # Fetch details from user model
    return jsonable_encoder({
        "success": True,
        "data": {
            "id": current_user.subscription_id or "free_sub",
            "userId": str(current_user.id),
            "planId": current_user.subscription_plan or "free",
            "status": current_user.subscription_status or "active",
            "currentPeriodEnd": "2030-01-01T00:00:00Z",
            "cancelAtPeriodEnd": current_user.subscription_status == "canceled"
        },
        "message": "Current subscription retrieved"
    })

@router.post("/checkout", response_model=dict)
def create_checkout(
    checkout_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Create a Stripe Checkout Session
    """
    plan_id = checkout_data.get("planId")
    billing_interval = checkout_data.get("billingInterval", "monthly")
    
    if plan_id not in ["pro", "enterprise"]:
        raise HTTPException(status_code=400, detail="Invalid plan ID")
        
    # 1. Get or create Stripe Price ID
    try:
        price_id = stripe_service.get_or_create_price(plan_id, billing_interval)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Stripe pricing: {str(e)}")
        
    # 2. Get or create Stripe Customer ID
    customer_id = current_user.stripe_customer_id
    if not customer_id:
        try:
            customer_id = stripe_service.create_customer(current_user.email, current_user.full_name or current_user.email)
            current_user.stripe_customer_id = customer_id
            db.commit()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create Stripe customer: {str(e)}")
            
    # 3. Setup Success and Cancel Redirect URLs
    app_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3000"
    success_url = f"{app_url}/dashboard/subscription?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{app_url}/dashboard/subscription?canceled=true"
    
    # 4. Create Stripe Checkout Session
    try:
        stripe.api_key = settings.STRIPE_API_KEY
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            client_reference_id=str(current_user.id),
            metadata={
                "user_id": str(current_user.id),
                "plan_id": plan_id,
                "billing_interval": billing_interval
            },
            subscription_data={
                "metadata": {
                    "user_id": str(current_user.id),
                    "plan_id": plan_id
                }
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")
        
    return jsonable_encoder({
        "success": True,
        "data": {"checkoutUrl": session.url},
        "message": "Checkout session created successfully"
    })

@router.post("/cancel", response_model=dict)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Cancel subscription at period end
    """
    if not current_user.subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found")
        
    try:
        stripe.api_key = settings.STRIPE_API_KEY
        sub = stripe.Subscription.modify(
            current_user.subscription_id,
            cancel_at_period_end=True
        )
        
        current_user.subscription_status = "canceled"
        db.commit()
        
        return jsonable_encoder({
            "success": True,
            "data": {
                "id": sub.id,
                "userId": str(current_user.id),
                "planId": current_user.subscription_plan,
                "status": "canceled",
                "currentPeriodEnd": datetime.fromtimestamp(sub.current_period_end).isoformat() + "Z",
                "cancelAtPeriodEnd": True
            },
            "message": "Subscription will be canceled at the end of the billing period"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")

@router.post("/reactivate", response_model=dict)
def reactivate_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Reactivate canceled subscription before period ends
    """
    if not current_user.subscription_id:
        raise HTTPException(status_code=400, detail="No active subscription found")
        
    try:
        stripe.api_key = settings.STRIPE_API_KEY
        sub = stripe.Subscription.modify(
            current_user.subscription_id,
            cancel_at_period_end=False
        )
        
        current_user.subscription_status = "active"
        db.commit()
        
        return jsonable_encoder({
            "success": True,
            "data": {
                "id": sub.id,
                "userId": str(current_user.id),
                "planId": current_user.subscription_plan,
                "status": "active",
                "currentPeriodEnd": datetime.fromtimestamp(sub.current_period_end).isoformat() + "Z",
                "cancelAtPeriodEnd": False
            },
            "message": "Subscription reactivated successfully"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reactivate subscription: {str(e)}")

@router.post("/webhook", response_model=dict)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> Any:
    """
    Public webhook receiver for Stripe events
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe Signature header")
        
    try:
        stripe.api_key = settings.STRIPE_API_KEY
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    event_type = event["type"]
    data_object = event["data"]["object"]
    
    print(f"[STRIPE WEBHOOK] Received event: {event_type}")
    
    # 1. checkout.session.completed
    if event_type == "checkout.session.completed":
        user_id = data_object.get("client_reference_id")
        customer_id = data_object.get("customer")
        subscription_id = data_object.get("subscription")
        metadata = data_object.get("metadata", {})
        plan_id = metadata.get("plan_id", "pro")
        
        if user_id:
            try:
                user_uuid = uuid.UUID(user_id)
                user = db.query(User).filter(User.id == user_uuid).first()
                if user:
                    user.stripe_customer_id = customer_id
                    user.subscription_id = subscription_id
                    user.subscription_plan = plan_id
                    user.subscription_status = "active"
                    db.commit()
                    print(f"[STRIPE WEBHOOK] Updated user {user.email} to {plan_id} subscription")
            except Exception as e:
                print(f"[STRIPE WEBHOOK] Error handling checkout completion: {e}")
                
    # 2. invoice.paid
    elif event_type == "invoice.paid":
        subscription_id = data_object.get("subscription")
        if subscription_id:
            user = db.query(User).filter(User.subscription_id == subscription_id).first()
            if user:
                user.subscription_status = "active"
                db.commit()
                print(f"[STRIPE WEBHOOK] Verified active subscription payment for {user.email}")
                
    # 3. customer.subscription.deleted
    elif event_type == "customer.subscription.deleted":
        subscription_id = data_object.get("id")
        if subscription_id:
            user = db.query(User).filter(User.subscription_id == subscription_id).first()
            if user:
                user.subscription_plan = "free"
                user.subscription_status = "active"
                user.subscription_id = None
                db.commit()
                print(f"[STRIPE WEBHOOK] Subscription deleted, reverted user {user.email} to free plan")
                
    return {"success": True, "message": "Webhook handled successfully"}
