from datetime import timedelta
from typing import Protocol

from django.db import transaction
from django.utils import timezone

from .models import Business, BusinessSubscription, PaymentRecord, SubscriptionPlan


class PaymentProvider(Protocol):
    name: str


class ManualPaymentProvider:
    name = "manual"


class BillingService:
    def __init__(self, provider=None):
        self.provider = provider or ManualPaymentProvider()

    @transaction.atomic
    def change_plan(self, business, plan, interval):
        if not plan.is_active:
            raise ValueError("The selected subscription plan is inactive.")
        if interval not in BusinessSubscription.Interval.values:
            raise ValueError("The selected billing interval is invalid.")
        now = timezone.now()
        renews_at = now + (
            timedelta(days=365)
            if interval == BusinessSubscription.Interval.ANNUAL
            else timedelta(days=30)
        )
        subscription, _ = BusinessSubscription.objects.get_or_create(
            business=business,
            defaults={
                "plan": plan,
                "plan_name": plan.name,
                "interval": interval,
                "status": BusinessSubscription.Status.ACTIVE,
                "started_at": now,
                "renews_at": renews_at,
                "provider": self.provider.name,
            },
        )
        subscription.plan = plan
        subscription.plan_name = plan.name
        subscription.interval = interval
        subscription.status = BusinessSubscription.Status.ACTIVE
        subscription.renews_at = renews_at
        subscription.cancelled_at = None
        subscription.provider = self.provider.name
        subscription.save(
            update_fields=[
                "plan",
                "plan_name",
                "interval",
                "status",
                "renews_at",
                "cancelled_at",
                "provider",
            ]
        )
        return subscription

    @transaction.atomic
    def cancel(self, business):
        subscription = business.subscription
        subscription.status = BusinessSubscription.Status.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.save(update_fields=["status", "cancelled_at"])
        return subscription

    def record_payment(self, subscription, amount, status, external_payment_id=""):
        paid_at = timezone.now() if status == PaymentRecord.Status.SUCCEEDED else None
        return PaymentRecord.objects.create(
            business=subscription.business,
            subscription=subscription,
            amount=amount,
            currency=subscription.plan.currency if subscription.plan else "USD",
            status=status,
            provider=self.provider.name,
            external_payment_id=external_payment_id,
            paid_at=paid_at,
        )
