from django import forms

from .models import Appointment, Customer, Sale, Service


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "phone", "email")


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ("name", "description", "duration_minutes", "price", "is_active")


class AppointmentForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = (
            "customer",
            "service",
            "starts_at",
            "staff_user_id",
            "status",
        )
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def save(self, commit=True):
        appointment = super().save(commit=False)
        appointment.service_name = appointment.service.name
        if commit:
            appointment.save()
        return appointment


class CheckoutForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.none(), required=False
    )
    service = forms.ModelChoiceField(queryset=Service.objects.none())
    quantity = forms.IntegerField(min_value=1, initial=1)
    discount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=10, initial=0)
    payment_method = forms.ChoiceField(choices=Sale.PaymentMethod.choices)
