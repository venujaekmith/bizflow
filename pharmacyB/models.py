from django.db import models


class Medicine(models.Model):
    name = models.CharField(max_length=150)
    batch_number = models.CharField(max_length=80, unique=True)
    expiry_date = models.DateField()
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=10)

    def __str__(self):
        return f"{self.name} ({self.batch_number})"


class Prescription(models.Model):
    patient_name = models.CharField(max_length=150)
    medicine = models.ForeignKey(
        Medicine, on_delete=models.PROTECT, related_name="prescriptions"
    )
    quantity = models.PositiveIntegerField()
    prescribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient_name} - {self.medicine}"
