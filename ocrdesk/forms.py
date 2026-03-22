from pathlib import Path

from django import forms


MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_GENERIC_CONTENT_TYPES = {"", "application/octet-stream"}


class OCRImageUploadForm(forms.Form):
    image = forms.FileField(
        label="사진 1장",
        required=True,
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp",
            }
        ),
        error_messages={
            "required": "사진을 먼저 골라 주세요.",
        },
    )

    def clean_image(self):
        uploaded_file = self.cleaned_data.get("image")
        if not uploaded_file:
            raise forms.ValidationError("사진을 먼저 골라 주세요.")

        suffix = Path(uploaded_file.name or "").suffix.lower()
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            raise forms.ValidationError("JPG, PNG, WEBP 사진만 올릴 수 있습니다.")

        if uploaded_file.size > MAX_IMAGE_BYTES:
            raise forms.ValidationError("사진은 10MB 이하만 올릴 수 있습니다.")

        content_type = str(getattr(uploaded_file, "content_type", "") or "").lower().strip()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES and content_type not in ALLOWED_GENERIC_CONTENT_TYPES:
            raise forms.ValidationError("휴대폰 사진(JPG, PNG, WEBP)만 읽을 수 있습니다.")

        return uploaded_file

