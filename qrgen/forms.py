from django import forms


class QrGeneratorForm(forms.Form):
    url = forms.URLField(required=False)
    label = forms.CharField(required=False, max_length=100)

