from dataclasses import dataclass

@dataclass(frozen=True)
class BusinessApplicationDefinition:
    key: str
    package: str
    urlconf: str
    dashboard_template: str
    migration_label: str


_APPLICATIONS = {}


def register(application):
    normalized_key = application.key.lower()
    if normalized_key in _APPLICATIONS:
        raise ValueError(f"Business application already registered: {application.key}")
    _APPLICATIONS[normalized_key] = application
    return application


def get_application(key):
    return _APPLICATIONS.get(key.lower())


def all_applications():
    return tuple(_APPLICATIONS.values())


def application_for_business(business):
    configured = business.applications.filter(is_active=True).values_list(
        "slug", flat=True
    )
    for application_key in configured:
        application = get_application(application_key)
        if application:
            return application
    return get_application(business.slug)


register(
    BusinessApplicationDefinition(
        key="salonNEXT",
        package="salonNEXT",
        urlconf="salonNEXT.urls",
        dashboard_template="salonNEXT/dashboard.html",
        migration_label="salonNEXT",
    )
)
register(
    BusinessApplicationDefinition(
        key="pharmacyB",
        package="pharmacyB",
        urlconf="pharmacyB.urls",
        dashboard_template="pharmacyB/dashboard.html",
        migration_label="pharmacyB",
    )
)
register(
    BusinessApplicationDefinition(
        key="graceryshopA",
        package="graceryshopA",
        urlconf="graceryshopA.urls",
        dashboard_template="graceryshopA/dashboard.html",
        migration_label="graceryshopA",
    )
)
