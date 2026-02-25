import uuid

from django.contrib.auth.models import User
from django.db import models


class HandoffRosterGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="handoff_roster_groups")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=200, blank=True)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_favorite", "name", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "name"],
                name="handoff_roster_group_owner_name_unique",
            )
        ]

    def __str__(self):
        return f"{self.owner.username} - {self.name}"


class HandoffRosterMember(models.Model):
    group = models.ForeignKey(HandoffRosterGroup, on_delete=models.CASCADE, related_name="members")
    display_name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.group.name} - {self.display_name}"


class HandoffSession(models.Model):
    STATUS_CHOICES = [
        ("open", "진행중"),
        ("closed", "마감"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="handoff_sessions")
    roster_group = models.ForeignKey(
        HandoffRosterGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    roster_group_name = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.roster_group and not self.roster_group_name:
            self.roster_group_name = self.roster_group.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.owner.username})"


class HandoffReceipt(models.Model):
    STATE_CHOICES = [
        ("pending", "미수령"),
        ("received", "수령완료"),
    ]
    HANDOFF_TYPE_CHOICES = [
        ("self", "본인 수령"),
        ("proxy", "대리 수령"),
        ("placed", "자리 비치"),
    ]

    session = models.ForeignKey(HandoffSession, on_delete=models.CASCADE, related_name="receipts")
    member = models.ForeignKey(
        HandoffRosterMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipts",
    )
    member_name_snapshot = models.CharField(max_length=100)
    member_order_snapshot = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default="pending")
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handoff_receipt_updates",
    )
    handoff_type = models.CharField(max_length=10, choices=HANDOFF_TYPE_CHOICES, default="self")
    memo = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["member_order_snapshot", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "member"],
                name="handoff_receipt_session_member_unique",
            )
        ]

    def __str__(self):
        return f"{self.session.title} - {self.member_name_snapshot} ({self.get_state_display()})"
