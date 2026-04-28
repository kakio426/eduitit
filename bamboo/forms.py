from django import forms


class BambooStoryForm(forms.Form):
    raw_text = forms.CharField(
        max_length=200,
        min_length=5,
        widget=forms.Textarea,
        error_messages={
            "required": "사연을 적어주세요.",
            "max_length": "200자 안으로 줄여주세요.",
            "min_length": "조금만 더 적어주세요.",
        },
    )
    def clean_raw_text(self):
        value = (self.cleaned_data.get("raw_text") or "").strip()
        if not value:
            raise forms.ValidationError("사연을 적어주세요.")
        if len(value) > 200:
            raise forms.ValidationError("200자 안으로 줄여주세요.")
        return value


class BambooCommentForm(forms.Form):
    body = forms.CharField(
        max_length=100,
        min_length=1,
        widget=forms.Textarea,
        error_messages={
            "required": "댓글을 적어주세요.",
            "max_length": "100자 안으로 줄여주세요.",
        },
    )

    def clean_body(self):
        value = (self.cleaned_data.get("body") or "").strip()
        if not value:
            raise forms.ValidationError("댓글을 적어주세요.")
        if len(value) > 100:
            raise forms.ValidationError("100자 안으로 줄여주세요.")
        return value
