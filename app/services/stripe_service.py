import stripe
from app.core.config import settings
from typing import Optional

class StripeService:
    def __init__(self):
        stripe.api_key = settings.STRIPE_API_KEY

    def get_or_create_price(self, plan_id: str, billing_interval: str) -> str:
        stripe.api_key = settings.STRIPE_API_KEY
        
        # Determine product name and pricing details
        if plan_id == "pro":
            product_name = "NewsCraft AI Pro"
            if billing_interval == "monthly":
                amount = 1900
                interval = "month"
            else:  # annual
                amount = 18000
                interval = "year"
        elif plan_id == "enterprise":
            product_name = "NewsCraft AI Enterprise"
            if billing_interval == "monthly":
                amount = 5900
                interval = "month"
            else:  # annual
                amount = 58800
                interval = "year"
        else:
            raise ValueError(f"Invalid plan ID: {plan_id}")

        # Search for existing active prices matching this product and interval
        try:
            products = stripe.Product.list(active=True)
            target_product = None
            for prod in products.data:
                if prod.get("name") == product_name:
                    target_product = prod
                    break
            
            if not target_product:
                target_product = stripe.Product.create(
                    name=product_name,
                    description=f"{product_name} subscription plan"
                )
            
            prices = stripe.Price.list(product=target_product.id, active=True)
            for pr in prices.data:
                recurring = pr.get("recurring", {})
                if recurring and recurring.get("interval") == interval:
                    if pr.get("unit_amount") == amount:
                        return pr.id
            
            # Create a new price if not found
            new_price = stripe.Price.create(
                product=target_product.id,
                unit_amount=amount,
                currency="usd",
                recurring={"interval": interval},
            )
            return new_price.id
        except Exception as e:
            print(f"Error getting or creating price: {e}")
            raise e

    def create_customer(self, email: str, name: str) -> str:
        stripe.api_key = settings.STRIPE_API_KEY
        customer = stripe.Customer.create(email=email, name=name)
        return customer.id

    def create_checkout_session(self, customer_id: str, price_id: str, success_url: str, cancel_url: str):
        stripe.api_key = settings.STRIPE_API_KEY
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url

    def handle_webhook(self, payload: str, sig_header: str):
        stripe.api_key = settings.STRIPE_API_KEY
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
            return event
        except ValueError as e:
            raise e
        except stripe.error.SignatureVerificationError as e:
            raise e

stripe_service = StripeService()
