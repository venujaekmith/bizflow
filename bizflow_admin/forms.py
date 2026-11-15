from django import forms
from django.contrib.auth import get_user_model

from .models import BusinessInvitation, BusinessMembership, BusinessSetting


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirmation = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ("email", "first_name", "last_name")

    def clean_email(self):
        return self.cleaned_data["email"].lower()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("password_confirmation"):
            self.add_error("password_confirmation", "The passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class EmployeeForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirmation = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=BusinessMembership.Role.choices)

    class Meta:
        model = get_user_model()
        fields = ("email", "first_name", "last_name")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("password_confirmation"):
            self.add_error("password_confirmation", "The passwords do not match.")
        return cleaned_data

    def save_user(self):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.save()
        return user


class EmployeeRoleForm(forms.ModelForm):
    class Meta:
        model = BusinessMembership
        fields = ("role",)


class InvitationForm(forms.ModelForm):
    class Meta:
        model = BusinessInvitation
        fields = ("email", "role")

    def clean_email(self):
        return self.cleaned_data["email"].lower()


class BusinessSettingForm(forms.ModelForm):
    enabled_modules = forms.CharField(required=False)

    class Meta:
        model = BusinessSetting
        fields = ("display_name", "timezone", "currency", "enabled_modules")
        widgets = {
            "enabled_modules": forms.TextInput(
                attrs={"placeholder": "inventory, reports, notifications"}
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and isinstance(self.instance.enabled_modules, list):
            self.initial["enabled_modules"] = ", ".join(
                self.instance.enabled_modules
            )

    def clean_enabled_modules(self):
        value = self.cleaned_data["enabled_modules"]
        if isinstance(value, list):
            return value
        return [module.strip() for module in value.split(",") if module.strip()]
