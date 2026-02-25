import datetime


WEEKDAY_LABELS = [
    (1, "월"),
    (2, "화"),
    (3, "수"),
    (4, "목"),
    (5, "금"),
]


PERIOD_NUMBERS = [1, 2, 3, 4, 5, 6]


SLOT_LAYOUT = [
    {
        "code": "p1",
        "kind": "period",
        "order": 1,
        "period": 1,
        "label": "1교시",
        "start": datetime.time(9, 0),
        "end": datetime.time(9, 40),
    },
    {
        "code": "b1",
        "kind": "break",
        "order": 2,
        "period": None,
        "label": "쉬는시간 (1-2)",
        "start": datetime.time(9, 40),
        "end": datetime.time(9, 50),
    },
    {
        "code": "p2",
        "kind": "period",
        "order": 3,
        "period": 2,
        "label": "2교시",
        "start": datetime.time(9, 50),
        "end": datetime.time(10, 30),
    },
    {
        "code": "b2",
        "kind": "break",
        "order": 4,
        "period": None,
        "label": "쉬는시간 (2-3)",
        "start": datetime.time(10, 30),
        "end": datetime.time(10, 40),
    },
    {
        "code": "p3",
        "kind": "period",
        "order": 5,
        "period": 3,
        "label": "3교시",
        "start": datetime.time(10, 40),
        "end": datetime.time(11, 20),
    },
    {
        "code": "b3",
        "kind": "break",
        "order": 6,
        "period": None,
        "label": "쉬는시간 (3-4)",
        "start": datetime.time(11, 20),
        "end": datetime.time(11, 30),
    },
    {
        "code": "p4",
        "kind": "period",
        "order": 7,
        "period": 4,
        "label": "4교시",
        "start": datetime.time(11, 30),
        "end": datetime.time(12, 10),
    },
    {
        "code": "lunch",
        "kind": "lunch",
        "order": 8,
        "period": None,
        "label": "점심시간 (4-5)",
        "start": datetime.time(12, 10),
        "end": datetime.time(13, 0),
    },
    {
        "code": "p5",
        "kind": "period",
        "order": 9,
        "period": 5,
        "label": "5교시",
        "start": datetime.time(13, 0),
        "end": datetime.time(13, 40),
    },
    {
        "code": "b5",
        "kind": "break",
        "order": 10,
        "period": None,
        "label": "쉬는시간 (5-6)",
        "start": datetime.time(13, 40),
        "end": datetime.time(13, 50),
    },
    {
        "code": "p6",
        "kind": "period",
        "order": 11,
        "period": 6,
        "label": "6교시",
        "start": datetime.time(13, 50),
        "end": datetime.time(14, 30),
    },
]


SLOT_BY_CODE = {row["code"]: row for row in SLOT_LAYOUT}

