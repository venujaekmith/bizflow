from django import forms

from business_runtime.registry import all_applications

from .models import Business


class PlatformBusinessForm(forms.ModelForm):
    application = forms.ChoiceField(
        choices=[
            (application.key.lower(), application.key)
            for application in all_applications()
        ]
    )

    class Meta:
        model = Business
        fields = ("name", "slug", "status")
