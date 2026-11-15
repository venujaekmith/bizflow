from django.http import HttpResponseForbidden

from .models import Business, BusinessMembership


class BusinessResolutionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        slug = view_kwargs.get("slug") or view_kwargs.get("business_slug")
        if not slug:
            return None
        if not request.user.is_authenticated:
            return None
        if not request.user.is_active:
            return HttpResponseForbidden("This user account is inactive.")

        membership = (
            BusinessMembership.objects.select_related("business")
            .filter(
                user=request.user,
                is_active=True,
                business__slug=slug,
            )
            .first()
        )
        if membership is None:
            return HttpResponseForbidden("You do not have access to this business.")
        if membership.business.status != Business.Status.ACTIVE:
            return HttpResponseForbidden("This business is not currently active.")
        subscription = getattr(membership.business, "subscription", None)
        if subscription and subscription.status in {
            "cancelled",
            "expired",
        }:
            return HttpResponseForbidden(
                "This business subscription does not permit access."
            )

        request.business = membership.business
        request.business_membership = membership
        return None
