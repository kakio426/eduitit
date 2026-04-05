from __future__ import annotations

from dataclasses import dataclass


RARITY_COMMON = "common"
RARITY_RARE = "rare"
RARITY_EPIC = "epic"
RARITY_LEGENDARY = "legendary"

RARITY_LABELS = {
    RARITY_COMMON: "기본",
    RARITY_RARE: "희귀",
    RARITY_EPIC: "에픽",
    RARITY_LEGENDARY: "전설",
}

PALETTE_TOKENS = {
    "mint": {"bg_start": "#dff8ef", "bg_end": "#b6f0d7", "text": "#0f3d2e", "accent": "#10b981", "ring": "#9de5c8"},
    "coral": {"bg_start": "#ffe1da", "bg_end": "#ffc0b5", "text": "#6a2e21", "accent": "#fb7185", "ring": "#ffb4a7"},
    "sky": {"bg_start": "#dbeafe", "bg_end": "#bfdbfe", "text": "#163153", "accent": "#3b82f6", "ring": "#93c5fd"},
    "lemon": {"bg_start": "#fff7cc", "bg_end": "#fde68a", "text": "#5b4300", "accent": "#f59e0b", "ring": "#fcd34d"},
    "lilac": {"bg_start": "#efe4ff", "bg_end": "#ddd6fe", "text": "#4c1d95", "accent": "#8b5cf6", "ring": "#c4b5fd"},
    "leaf": {"bg_start": "#dcfce7", "bg_end": "#bbf7d0", "text": "#14532d", "accent": "#22c55e", "ring": "#86efac"},
    "peach": {"bg_start": "#ffe7d6", "bg_end": "#fdba74", "text": "#7c2d12", "accent": "#f97316", "ring": "#fdba74"},
    "ruby": {"bg_start": "#ffe0e7", "bg_end": "#fda4af", "text": "#6b1020", "accent": "#e11d48", "ring": "#fb7185"},
    "teal": {"bg_start": "#d9fbfb", "bg_end": "#99f6e4", "text": "#134e4a", "accent": "#14b8a6", "ring": "#5eead4"},
    "cobalt": {"bg_start": "#dde7ff", "bg_end": "#c7d2fe", "text": "#1e1b4b", "accent": "#4f46e5", "ring": "#a5b4fc"},
    "rose": {"bg_start": "#ffe4ef", "bg_end": "#fbcfe8", "text": "#831843", "accent": "#ec4899", "ring": "#f9a8d4"},
    "ice": {"bg_start": "#ecfeff", "bg_end": "#dbeafe", "text": "#164e63", "accent": "#38bdf8", "ring": "#bae6fd"},
    "plum": {"bg_start": "#f5e8ff", "bg_end": "#e9d5ff", "text": "#581c87", "accent": "#a855f7", "ring": "#d8b4fe"},
    "denim": {"bg_start": "#dfe7f6", "bg_end": "#bfdbfe", "text": "#1e3a8a", "accent": "#2563eb", "ring": "#93c5fd"},
    "seafoam": {"bg_start": "#dbfff5", "bg_end": "#a7f3d0", "text": "#065f46", "accent": "#10b981", "ring": "#6ee7b7"},
    "butter": {"bg_start": "#fffbea", "bg_end": "#fde68a", "text": "#713f12", "accent": "#facc15", "ring": "#fde68a"},
    "slate": {"bg_start": "#e2e8f0", "bg_end": "#cbd5e1", "text": "#334155", "accent": "#64748b", "ring": "#cbd5e1"},
    "bubblegum": {"bg_start": "#ffe4f1", "bg_end": "#fbcfe8", "text": "#831843", "accent": "#f472b6", "ring": "#f9a8d4"},
    "sunset": {"bg_start": "#ffedd5", "bg_end": "#fdba74", "text": "#7c2d12", "accent": "#f97316", "ring": "#fdba74"},
    "forest": {"bg_start": "#dcfce7", "bg_end": "#86efac", "text": "#14532d", "accent": "#16a34a", "ring": "#4ade80"},
    "charcoal": {"bg_start": "#e5e7eb", "bg_end": "#9ca3af", "text": "#111827", "accent": "#374151", "ring": "#d1d5db"},
    "nightgold": {"bg_start": "#ccfbf1", "bg_end": "#fef3c7", "text": "#083344", "accent": "#0f766e", "ring": "#facc15"},
}

LOCKED_BUDDY_ASCII = "\n".join(
    (
        "  .----.  ",
        " / ....\\ ",
        "| LOCKED |",
        " \\______/ ",
    )
)


@dataclass(frozen=True)
class TeacherBuddyDefinition:
    key: str
    name: str
    rarity: str
    palette: str
    avatar_mark: str
    share_frame: str
    silhouette_family: str
    share_caption: str
    share_gradient: tuple[str, str]
    idle_ascii: str
    unlock_ascii: str
    messages: tuple[str, str, str]

    @property
    def rarity_label(self) -> str:
        return RARITY_LABELS[self.rarity]


@dataclass(frozen=True)
class TeacherBuddySkinDefinition:
    key: str
    buddy_key: str
    label: str
    palette: str
    share_gradient: tuple[str, str]
    avatar_accent: str
    preview_badge: str
    unlock_cost_dust: int
    sort_order: int


def _join_lines(*lines: str) -> str:
    return "\n".join(lines)


def _messages(name: str) -> tuple[str, str, str]:
    return (
        f"{name}가 오늘 교실 흐름을 살펴보고 있어요.",
        f"{name}가 한 칸씩 차분하게 맞춰 보고 있어요.",
        f"{name}와 오늘 티켓을 완성했어요.",
    )


def _unlock_ascii(idle_ascii: str) -> str:
    lines = idle_ascii.splitlines()[:5]
    return "\n".join(("   NEW!   ",) + tuple(lines[:5]))


def _unlock_ascii_legendary(idle_ascii: str) -> str:
    lines = idle_ascii.splitlines()[:5]
    return "\n".join(("LEGENDARY!",) + tuple(lines))


def _buddy(
    key: str,
    name: str,
    rarity: str,
    palette: str,
    avatar_mark: str,
    share_frame: str,
    silhouette_family: str,
    share_caption: str,
    lines: tuple[str, ...],
) -> TeacherBuddyDefinition:
    tokens = PALETTE_TOKENS[palette]
    idle_ascii = _join_lines(*lines)
    unlock_ascii = _unlock_ascii_legendary(idle_ascii) if rarity == RARITY_LEGENDARY else _unlock_ascii(idle_ascii)
    return TeacherBuddyDefinition(
        key=key,
        name=name,
        rarity=rarity,
        palette=palette,
        avatar_mark=avatar_mark,
        share_frame=share_frame,
        silhouette_family=silhouette_family,
        share_caption=share_caption,
        share_gradient=(tokens["bg_start"], tokens["bg_end"]),
        idle_ascii=idle_ascii,
        unlock_ascii=unlock_ascii,
        messages=_messages(name),
    )


_BUDDIES = (
    _buddy("chalk_bean", "분필콩", RARITY_COMMON, "mint", "CK", "spark", "chalk", "분필 한 줄처럼 오늘 수업 흐름을 또박또박 정리해요.", (
        "  ____  ",
        " / __ \\ ",
        "| |..| |",
        "| |__| |",
        " \\____/ ",
    )),
    _buddy("memo_sprout", "메모싹", RARITY_COMMON, "coral", "MS", "spark", "memo", "메모 한 장에서 오늘 아이디어가 싹트도록 돕는 메이트예요.", (
        " .----. ",
        "| .^. | ",
        "| '--'| ",
        "|_____| ",
        "  /\\    ",
    )),
    _buddy("eraser_mate", "지우미", RARITY_COMMON, "sky", "EM", "seal", "eraser", "흐트러진 흔적을 지우고 깔끔하게 다시 시작하게 해줘요.", (
        " ______ ",
        "| .--. |",
        "| |__| |",
        "|  --  |",
        "|______|",
    )),
    _buddy("clip_ring", "집게링", RARITY_COMMON, "lemon", "CR", "spark", "clip", "종이와 할 일을 가지런히 묶어 두는 작은 도우미예요.", (
        "  .--.  ",
        " / .. \\ ",
        "| |  | |",
        " \\ __ / ",
        "  '--'  ",
    )),
    _buddy("star_corner", "별쪽이", RARITY_COMMON, "lilac", "SC", "spark", "star", "칠판 귀퉁이에 반짝이는 별 메모처럼 분위기를 밝혀요.", (
        "   /\\    ",
        " _/..\\_  ",
        "<_.--._> ",
        " /_  _\\  ",
        "   \\/    ",
    )),
    _buddy("sprout_cup", "새싹컵", RARITY_COMMON, "leaf", "SU", "petal", "cup", "작은 새싹 물컵처럼 교실 분위기를 상쾌하게 바꿔 줘요.", (
        "  ____   ",
        " / ..\\   ",
        "|    |   ",
        "|____|   ",
        "  ||||   ",
    )),
    _buddy("pencil_tot", "연필총총", RARITY_COMMON, "peach", "PT", "spark", "pencil", "연필 끝에서 아이디어가 또렷하게 서도록 곁을 지켜요.", (
        "   /\\    ",
        "  /..\\   ",
        " /_==_\\  ",
        "   ||    ",
        "  _||_   ",
    )),
    _buddy("magnet_bean", "자석콩", RARITY_COMMON, "teal", "MG", "seal", "magnet", "붙어 있어야 할 일정과 메모를 착 붙여 주는 메이트예요.", (
        " |\\  /|  ",
        " | .. |  ",
        " | || |  ",
        " |_||_|  ",
        "  /__\\   ",
    )),
    _buddy("bookmark_leaf", "북마크잎", RARITY_COMMON, "leaf", "BM", "petal", "bookmark", "중요한 페이지와 순간을 잎사귀처럼 살짝 표시해 줘요.", (
        " .----.  ",
        " | /\\ |  ",
        " | \\/ |  ",
        " | __>|  ",
        " '----'  ",
    )),
    _buddy("post_moon", "포스트문", RARITY_COMMON, "coral", "PM", "spark", "moon", "포스트잇 달빛처럼 조용히 할 일을 비춰 주는 친구예요.", (
        " .----.  ",
        "/ .--.\\  ",
        "| |()| | ",
        "| '--' | ",
        " '----'  ",
    )),
    _buddy("attendance_bell", "출석방울", RARITY_COMMON, "butter", "AB", "seal", "attendance", "출석 체크 순간을 가볍고 또렷하게 알려 주는 방울이에요.", (
        "  .--.   ",
        " / ()\\   ",
        "|  __  | ",
        "| |__| | ",
        "  /__\\   ",
    )),
    _buddy("pin_star", "압정별", RARITY_COMMON, "ruby", "PS", "spark", "pin", "게시판 한쪽에 꼭 눌러 둔 반짝 메모 같은 존재예요.", (
        "   /\\    ",
        "  <..>   ",
        " /_==_\\  ",
        "   ||    ",
        "   ||    ",
    )),
    _buddy("highlight_band", "형광띠", RARITY_COMMON, "lemon", "HB", "spark", "marker", "중요한 순간을 형광펜처럼 또렷하게 남겨 줘요.", (
        " ______  ",
        "|= .. =| ",
        "|=____=| ",
        "  ||||   ",
        "  '--'   ",
    )),
    _buddy("storage_tray", "수납트레이", RARITY_COMMON, "ice", "SY", "seal", "tray", "작은 준비물을 한 번에 담아 두는 정리 메이트예요.", (
        " ______  ",
        "/_...._\\ ",
        "|      | ",
        "|______| ",
        " \\____/  ",
    )),
    _buddy("stamp_captain", "도장대장", RARITY_RARE, "ruby", "SP", "seal", "stamp", "도장 한 번처럼 분명하게 완료 감각을 남겨 줘요.", (
        " .----.  ",
        "/ .--.\\  ",
        "| |##| | ",
        "| '--' | ",
        " '----'  ",
    )),
    _buddy("bell_ring", "종소링", RARITY_RARE, "teal", "BR", "seal", "bell", "시작과 전환 타이밍을 맑게 울려 주는 메이트예요.", (
        "  .--.   ",
        " / ()\\   ",
        "|  __  | ",
        "| /__\\ | ",
        "  /  \\   ",
    )),
    _buddy("timetable_fairy", "시간표요정", RARITY_RARE, "cobalt", "TF", "grid", "timetable", "복잡한 시간표도 한눈에 잡히게 정리해 줘요.", (
        " .====.  ",
        "| 12  |  ",
        "| --  |  ",
        "|_..__|  ",
        " /__\\    ",
    )),
    _buddy("ribbon_file", "리본파일", RARITY_RARE, "rose", "RF", "ribbon", "file", "중요 자료를 예쁘게 묶어 두는 리본 파일이에요.", (
        " .-----. ",
        "| >--< | ",
        "| |__| | ",
        "| |  | | ",
        "'------' ",
    )),
    _buddy("color_flower", "색연필꽃", RARITY_RARE, "sunset", "CF", "petal", "flower", "색연필 끝에서 피어난 꽃처럼 교실을 화사하게 채워요.", (
        "   /\\    ",
        " _<..>_  ",
        " \\\\||//  ",
        "  /__\\   ",
        "   ||    ",
    )),
    _buddy("drawer_keeper", "서랍지기", RARITY_RARE, "slate", "DK", "cabinet", "drawer", "서랍 속 준비물을 잊지 않게 챙겨 주는 지기예요.", (
        " .----.  ",
        "| [] []| ",
        "| [] []| ",
        "|  __  | ",
        "'------' ",
    )),
    _buddy("timer_ring", "타이머링", RARITY_RARE, "plum", "TR", "spark", "timer", "수업 템포를 놓치지 않도록 시간을 둥글게 감싸요.", (
        "  .--.   ",
        " / 12\\   ",
        "|  .. |  ",
        " \\ -- /  ",
        "  '--'   ",
    )),
    _buddy("clipboard_ri", "클립보드리", RARITY_RARE, "denim", "CB", "grid", "clipboard", "체크할 목록을 또박또박 들고 다니는 보드 친구예요.", (
        " .----.  ",
        "|==== |  ",
        "| ..  |  ",
        "|_____|  ",
        "  ||     ",
    )),
    _buddy("ruler_captain", "자대장", RARITY_RARE, "peach", "RL", "grid", "ruler", "길이와 간격을 맞추듯 교실 흐름을 반듯하게 세워 줘요.", (
        " .-----.  ",
        "|0 5 10|  ",
        "|  ..  |  ",
        "|_____ |  ",
        "   ||     ",
    )),
    _buddy("file_basket", "파일바구니", RARITY_RARE, "seafoam", "FB", "cabinet", "basket", "여러 장의 자료를 한 번에 담아 정리해 주는 바구니예요.", (
        " .----.  ",
        "/_/\\/\\_\\ ",
        "| .. ..| ",
        "|______| ",
        " /____\\  ",
    )),
    _buddy("pointer_beam", "포인터빔", RARITY_RARE, "sky", "PB", "spark", "pointer", "시선이 머물 곳을 반짝 선으로 알려 주는 빔이에요.", (
        "   /\\     ",
        "  /..\\--  ",
        " /_==_\\\\  ",
        "    ||    ",
        "    ||    ",
    )),
    _buddy("book_trolley", "북트롤리", RARITY_RARE, "forest", "BT", "cabinet", "cart", "자료 묶음을 차곡차곡 싣고 다니는 이동 메이트예요.", (
        " .----.  ",
        "| [] []| ",
        "| .--. | ",
        "|_|__|_| ",
        "  oo oo  ",
    )),
    _buddy("board_aurora", "칠판오로라", RARITY_EPIC, "cobalt", "BA", "aurora", "aurora", "칠판 위 공기를 오로라처럼 맑게 바꾸는 에픽 메이트예요.", (
        " .------. ",
        "| .--. *| ",
        "| |..|~ | ",
        "| |__|  | ",
        " '------' ",
    )),
    _buddy("time_compass", "시간나침반", RARITY_EPIC, "plum", "TC", "spark", "compass", "복잡한 일정 속에서도 다음 방향을 가리키는 나침반이에요.", (
        "   /\\    ",
        " .-..-.  ",
        "<| 00 |> ",
        " '-..-'  ",
        "   \\/    ",
    )),
    _buddy("paper_castle", "종이성", RARITY_EPIC, "peach", "PA", "window", "castle", "종이와 계획이 층층이 쌓여 만들어진 교실의 작은 성이에요.", (
        "  /\\/\\   ",
        " /_.._\\  ",
        "| |__| | ",
        "| |  | | ",
        "|_|__|_| ",
    )),
    _buddy("ribbon_cabinet", "리본캐비닛", RARITY_EPIC, "rose", "RC", "cabinet", "cabinet_ribbon", "정리와 장식을 동시에 챙기는 리본 캐비닛 메이트예요.", (
        " .-----. ",
        "| >==< | ",
        "| [] []| ",
        "| [] []| ",
        "'------' ",
    )),
    _buddy("class_window_star", "교실창별", RARITY_EPIC, "ice", "CW", "window", "window", "교실 창에 비친 별빛처럼 공간을 환하게 열어 줘요.", (
        " .-[]-.  ",
        "| *  * | ",
        "|  ..  | ",
        "| *  * | ",
        " '-----' ",
    )),
    _buddy("desk_arch", "교탁아치", RARITY_EPIC, "charcoal", "DA", "window", "desk", "교탁 위 흐름을 단단하게 감싸는 아치형 메이트예요.", (
        "  ____   ",
        " / __ \\  ",
        "| |..| | ",
        "| |__| | ",
        "|_|  |_| ",
    )),
    _buddy("routine_station", "루틴정거장", RARITY_EPIC, "seafoam", "RS", "grid", "station", "교실 루틴이 매번 같은 자리에서 출발하도록 잡아 줘요.", (
        " .------. ",
        "| [__]  | ",
        "|  ..   | ",
        "|__||___| ",
        "   /__\\   ",
    )),
    _buddy("class_lantern", "수업등불", RARITY_EPIC, "sunset", "LN", "spark", "lantern", "수업 흐름의 어두운 틈을 조용히 밝혀 주는 등불이에요.", (
        "   /\\    ",
        " .-..-.  ",
        "| |..| | ",
        "| |__| | ",
        " '--||'  ",
    )),
    _buddy("time_display", "시간전광판", RARITY_EPIC, "denim", "TD", "grid", "display", "지금 해야 할 일을 한 번에 보여 주는 전광판 메이트예요.", (
        " .------. ",
        "| 08:30 | ",
        "|  ..   | ",
        "|______ | ",
        "   /__\\   ",
    )),
    _buddy("board_lighthouse", "칠판등대", RARITY_LEGENDARY, "nightgold", "LH", "lighthouse", "lighthouse", "교실 전체를 비추는 전설 메이트로, 꾸준한 흐름 끝에 만날 수 있어요.", (
        "    /\\    ",
        "   /..\\   ",
        "  /_==_\\  ",
        "  | || |  ",
        " .|_||_|. ",
        "   /__\\   ",
    )),
)

_COMMON_SKIN_THEMES = (
    ("breeze", "하늘빛", "ice", "SK"),
    ("candy", "사탕빛", "bubblegum", "CM"),
    ("sunny", "햇살빛", "butter", "SN"),
    ("denim", "데님빛", "denim", "DN"),
    ("plum", "자두빛", "plum", "PL"),
    ("forest", "숲빛", "forest", "FR"),
    ("coral", "코랄빛", "coral", "CR"),
)
_RARE_SKIN_THEMES = (
    ("studio", "스튜디오", "slate", "SD"),
    ("aurora", "오로라", "plum", "AU"),
    ("festival", "축제빛", "sunset", "FS"),
    ("mint", "민트빛", "mint", "MN"),
    ("night", "밤하늘", "denim", "NT"),
    ("glow", "반짝광", "bubblegum", "GW"),
    ("green", "그린룸", "seafoam", "GR"),
    ("berry", "베리룸", "ruby", "BY"),
    ("butter", "버터빛", "butter", "BT"),
    ("ice", "빙하빛", "ice", "IC"),
    ("leaf", "초록빛", "leaf", "LF"),
    ("lilac", "라일락빛", "lilac", "LL"),
)


def _skin(
    key: str,
    buddy_key: str,
    label: str,
    palette: str,
    preview_badge: str,
    unlock_cost_dust: int,
    sort_order: int,
) -> TeacherBuddySkinDefinition:
    tokens = PALETTE_TOKENS[palette]
    return TeacherBuddySkinDefinition(
        key=key,
        buddy_key=buddy_key,
        label=label,
        palette=palette,
        share_gradient=(tokens["bg_start"], tokens["bg_end"]),
        avatar_accent=tokens["accent"],
        preview_badge=preview_badge,
        unlock_cost_dust=unlock_cost_dust,
        sort_order=sort_order,
    )


_COMMON_BUDDY_LIST = [buddy for buddy in _BUDDIES if buddy.rarity == RARITY_COMMON]
_RARE_BUDDY_LIST = [buddy for buddy in _BUDDIES if buddy.rarity == RARITY_RARE]

_SKINS = []
for index, buddy in enumerate(_COMMON_BUDDY_LIST):
    first_theme = _COMMON_SKIN_THEMES[index % len(_COMMON_SKIN_THEMES)]
    second_theme = _COMMON_SKIN_THEMES[(index + 3) % len(_COMMON_SKIN_THEMES)]
    _SKINS.append(
        _skin(
            f"{buddy.key}__{first_theme[0]}",
            buddy.key,
            f"{buddy.name} {first_theme[1]}",
            first_theme[2],
            first_theme[3],
            6,
            index * 2 + 1,
        )
    )
    _SKINS.append(
        _skin(
            f"{buddy.key}__{second_theme[0]}",
            buddy.key,
            f"{buddy.name} {second_theme[1]}",
            second_theme[2],
            second_theme[3],
            6,
            index * 2 + 2,
        )
    )

for index, buddy in enumerate(_RARE_BUDDY_LIST):
    theme = _RARE_SKIN_THEMES[index]
    _SKINS.append(
        _skin(
            f"{buddy.key}__{theme[0]}",
            buddy.key,
            f"{buddy.name} {theme[1]}",
            theme[2],
            theme[3],
            12,
            100 + index,
        )
    )

SILHOUETTE_FAMILY_SHEET = {}
for definition in _BUDDIES:
    SILHOUETTE_FAMILY_SHEET.setdefault(definition.silhouette_family, []).append(definition.key)
SILHOUETTE_FAMILY_SHEET = {
    family: tuple(keys) for family, keys in SILHOUETTE_FAMILY_SHEET.items()
}

BUDDY_BY_KEY = {buddy.key: buddy for buddy in _BUDDIES}
SKIN_BY_KEY = {skin.key: skin for skin in _SKINS}
SKINS_BY_BUDDY_KEY = {}
for skin in _SKINS:
    SKINS_BY_BUDDY_KEY.setdefault(skin.buddy_key, []).append(skin)
for buddy_key, skins in list(SKINS_BY_BUDDY_KEY.items()):
    SKINS_BY_BUDDY_KEY[buddy_key] = tuple(sorted(skins, key=lambda item: item.sort_order))

COMMON_BUDDY_KEYS = tuple(buddy.key for buddy in _COMMON_BUDDY_LIST)
TOTAL_BUDDY_COUNT = len(_BUDDIES)
TOTAL_SKIN_COUNT = len(_SKINS)


def get_teacher_buddy_palette(palette_key: str) -> dict[str, str]:
    return dict(PALETTE_TOKENS.get(palette_key) or PALETTE_TOKENS["sky"])


def all_teacher_buddies() -> tuple[TeacherBuddyDefinition, ...]:
    return tuple(_BUDDIES)


def get_teacher_buddy(key: str) -> TeacherBuddyDefinition:
    return BUDDY_BY_KEY[key]


def all_teacher_buddy_skins() -> tuple[TeacherBuddySkinDefinition, ...]:
    return tuple(_SKINS)


def get_teacher_buddy_skin(key: str) -> TeacherBuddySkinDefinition:
    return SKIN_BY_KEY[key]


def get_teacher_buddy_skins_for_buddy(buddy_key: str) -> tuple[TeacherBuddySkinDefinition, ...]:
    return tuple(SKINS_BY_BUDDY_KEY.get(buddy_key) or ())
