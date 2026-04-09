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

LOCKED_AVATAR_ASCII = "\n".join(
    (
        " .--. ",
        "/_.._\\",
        "|_[]_|",
        " '--' ",
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


def _has_batchim(value: str) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False
    for char in reversed(cleaned):
        if char.isspace():
            continue
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        lowered = char.lower()
        if lowered in "aeiou":
            return False
        if lowered.isalpha() or lowered.isdigit():
            return True
        return False
    return False


def with_particle(value: str, pair: tuple[str, str]) -> str:
    first, second = pair
    return f"{value}{first if _has_batchim(value) else second}"


def _messages(name: str) -> tuple[str, str, str]:
    return (
        f"{with_particle(name, ('이', '가'))} 오늘 교실 흐름을 살펴보고 있어요.",
        f"{with_particle(name, ('이', '가'))} 한 칸씩 차분하게 맞춰 보고 있어요.",
        f"{with_particle(name, ('과', '와'))} 오늘 반짝 조각을 완성했어요.",
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
    _buddy("chalk_bean", "분필콩", RARITY_COMMON, "mint", "CK", "spark", "chalk", "칠판 위 첫 줄을 또박하게 잡아 주는 산뜻한 분필 메이트예요.", (
        "  ____  ",
        " / __ \\ ",
        "| |..| |",
        "| |__| |",
        " \\____/ ",
    )),
    _buddy("memo_sprout", "메모싹", RARITY_COMMON, "coral", "MS", "spark", "memo", "흩어진 생각을 작은 메모 한 장처럼 살포시 모아 싹틔워 줘요.", (
        " .----.  ",
        "| .^. |  ",
        "| '--' | ",
        "|_____|  ",
        "   /\\    ",
    )),
    _buddy("eraser_mate", "지우미", RARITY_COMMON, "sky", "EM", "seal", "eraser", "지워야 할 건 말끔히 덜어 내고 다시 시작할 자리를 만들어 줘요.", (
        " ______ ",
        "| .--. |",
        "| |__| |",
        "|  --  |",
        "|______|",
    )),
    _buddy("clip_ring", "집게링", RARITY_COMMON, "lemon", "CR", "spark", "clip", "자료와 할 일을 흐트러짐 없이 살짝 집어 두는 정리 메이트예요.", (
        "  .--.  ",
        " / .. \\ ",
        "| |  | |",
        " \\ __ / ",
        "  '--'  ",
    )),
    _buddy("star_corner", "별쪽이", RARITY_COMMON, "lilac", "SC", "spark", "star", "교실 한쪽 구석까지 반짝임을 데려오는 별빛 메이트예요.", (
        "   /\\    ",
        " _/..\\_  ",
        "<_.--._> ",
        " /_  _\\  ",
        "   \\/    ",
    )),
    _buddy("sprout_cup", "새싹컵", RARITY_COMMON, "leaf", "SU", "petal", "cup", "맑은 물 한 컵처럼 교실 공기를 산뜻하게 환기해 줘요.", (
        "  ____   ",
        " / ..\\   ",
        " |    |  ",
        " |____|  ",
        "  ||||   ",
    )),
    _buddy("pencil_tot", "연필총총", RARITY_COMMON, "peach", "PT", "spark", "pencil", "아이디어가 번뜩일 순간을 연필 끝처럼 또렷하게 세워 줘요.", (
        "   /\\    ",
        "  /..\\   ",
        " /_==_\\  ",
        "   ||    ",
        "  _||_   ",
    )),
    _buddy("magnet_bean", "자석콩", RARITY_COMMON, "teal", "MG", "seal", "magnet", "붙어 있어야 할 공지와 일정에 찰싹 힘을 더해 줘요.", (
        " |\\  /|  ",
        " | .. |  ",
        " | || |  ",
        " |_||_|  ",
        "  /__\\   ",
    )),
    _buddy("bookmark_leaf", "북마크잎", RARITY_COMMON, "leaf", "BM", "petal", "bookmark", "중요한 장면과 페이지에 잎사귀 표시처럼 살짝 머물러 줘요.", (
        " .----.  ",
        " | /\\ |  ",
        " | \\/ |  ",
        " | __>|  ",
        " '----'  ",
    )),
    _buddy("post_moon", "포스트문", RARITY_COMMON, "coral", "PM", "spark", "moon", "포스트잇 한 장에 달빛을 얹듯 해야 할 일을 조용히 비춰 줘요.", (
        "  .--.   ",
        " / () \\  ",
        "|  ..  | ",
        "| '--' | ",
        " '----'  ",
    )),
    _buddy("attendance_bell", "출석방울", RARITY_COMMON, "butter", "AB", "seal", "attendance", "출석과 시작 신호를 맑고 가볍게 울려 주는 메이트예요.", (
        "  .--.   ",
        " / ()\\   ",
        "|  __  | ",
        "| |__| | ",
        "  /__\\   ",
    )),
    _buddy("pin_star", "압정별", RARITY_COMMON, "ruby", "PS", "spark", "pin", "게시판의 핵심 한 점을 별처럼 또렷하게 눌러 주는 메이트예요.", (
        "   /\\    ",
        "  <..>   ",
        " /_==_\\  ",
        "   ||    ",
        "   ||    ",
    )),
    _buddy("highlight_band", "형광띠", RARITY_COMMON, "lemon", "HB", "spark", "marker", "꼭 남겨야 할 순간을 형광 한 줄처럼 선명하게 살려 줘요.", (
        " ______  ",
        "|= .. =| ",
        "|=____=| ",
        "  ||||   ",
        "  '--'   ",
    )),
    _buddy("storage_tray", "정리받침", RARITY_COMMON, "ice", "SY", "seal", "tray", "준비물과 작은 소품을 한자리에 고르게 받쳐 두는 메이트예요.", (
        " ______  ",
        "/_...._\\ ",
        "|      | ",
        "|______| ",
        " \\____/  ",
    )),
    _buddy("note_pot", "메모화분", RARITY_COMMON, "mint", "NP", "petal", "pot", "짧은 메모와 아이디어를 포근하게 키워 내는 화분 메이트예요.", (
        "  .--.    ",
        " / ..\\    ",
        "| |~~|    ",
        "| |__|    ",
        "  /||\\    ",
    )),
    _buddy("paper_crane", "종이학", RARITY_COMMON, "sky", "PC", "spark", "crane", "접어 둔 쪽지 한 장처럼 다음 할 일을 가볍게 띄워 줘요.", (
        "   /\\     ",
        "  /..\\    ",
        " <_==_>   ",
        "  /\\/\\    ",
        "   \\/     ",
    )),
    _buddy("desk_pouch", "책상주머니", RARITY_COMMON, "butter", "DP", "seal", "pouch", "자주 쓰는 작은 준비물을 책상 곁에 포근히 모아 두는 살림 메이트예요.", (
        "  ____    ",
        " / __ \\   ",
        "| |~~| |  ",
        "| |__| |  ",
        "'------'  ",
    )),
    _buddy("notice_pinwheel", "알림바람개비", RARITY_COMMON, "sky", "PW", "spark", "pinwheel", "수시로 바뀌는 공지와 할 일을 바람개비처럼 가볍게 돌려 알려 줘요.", (
        "   /\\     ",
        "  /..\\    ",
        " <_==_>   ",
        "  \\/\\/    ",
        "   ||     ",
    )),
    _buddy("stamp_captain", "도장반장", RARITY_RARE, "ruby", "SP", "seal", "stamp", "완료해야 할 순간에 도장 한 번 같은 확실함을 남겨 줘요.", (
        " .----.  ",
        "/ .--.\\  ",
        "| |##| | ",
        "| '--' | ",
        " '----'  ",
    )),
    _buddy("bell_ring", "종소링", RARITY_RARE, "teal", "BR", "seal", "bell", "시작과 전환 타이밍을 가볍고 맑은 울림으로 알려 줘요.", (
        "  .--.   ",
        " / ()\\   ",
        "|  __  | ",
        "| /__\\ | ",
        "  /  \\   ",
    )),
    _buddy("timetable_fairy", "시간표요정", RARITY_RARE, "cobalt", "TF", "grid", "timetable", "복잡한 시간표 흐름을 한눈에 읽히는 리듬으로 정리해 줘요.", (
        " .====.  ",
        "| 12  |  ",
        "| --  |  ",
        "|_..__|  ",
        "  /__\\   ",
    )),
    _buddy("ribbon_file", "리본파일", RARITY_RARE, "rose", "RF", "ribbon", "file", "소중한 자료를 예쁘고 반듯하게 묶어 두는 파일 메이트예요.", (
        " .-----. ",
        "| >--< | ",
        "| |__| | ",
        "| |  | | ",
        "'------' ",
    )),
    _buddy("color_flower", "색연필꽃", RARITY_RARE, "sunset", "CF", "petal", "flower", "색이 필요한 순간마다 교실 분위기를 환하게 피워 줘요.", (
        "   /\\    ",
        " _<..>_  ",
        " \\\\||//  ",
        "  /__\\   ",
        "   ||    ",
    )),
    _buddy("drawer_keeper", "서랍지기", RARITY_RARE, "slate", "DK", "cabinet", "drawer", "잊기 쉬운 준비물도 서랍 속에서 정확히 찾아오게 도와줘요.", (
        " .----.  ",
        "| [] []| ",
        "| [] []| ",
        "|  __  | ",
        "'------' ",
    )),
    _buddy("timer_ring", "타이머링", RARITY_RARE, "plum", "TR", "spark", "timer", "수업의 템포가 흐트러지지 않도록 시간을 둥글게 감싸 줘요.", (
        "  .--.   ",
        " / 12\\   ",
        "|  .. |  ",
        " \\ -- /  ",
        "  '--'   ",
    )),
    _buddy("clipboard_ri", "체크보드리", RARITY_RARE, "denim", "CB", "grid", "clipboard", "해야 할 목록을 한 줄씩 또박또박 챙겨 주는 체크 메이트예요.", (
        " .----.  ",
        "|====| | ",
        "| .. | | ",
        "|____|_| ",
        "  ||||   ",
    )),
    _buddy("ruler_captain", "줄반장", RARITY_RARE, "peach", "RL", "grid", "ruler", "길이와 간격을 맞추듯 교실 흐름을 반듯하게 세워 줘요.", (
        " .-----.  ",
        "|0 5 10|  ",
        "|  ..  |  ",
        "|_____ |  ",
        "   ||     ",
    )),
    _buddy("file_basket", "파일바구니", RARITY_RARE, "seafoam", "FB", "cabinet", "basket", "여러 장의 자료를 한 번에 담아 가지런히 모아 주는 바구니예요.", (
        " .----.  ",
        "/_/\\/\\_\\ ",
        "| .. ..| ",
        "|______| ",
        " /____\\  ",
    )),
    _buddy("pointer_beam", "포인터빔", RARITY_RARE, "sky", "PB", "spark", "pointer", "시선이 머물 핵심 지점을 반짝이는 선으로 짚어 줘요.", (
        "   /\\     ",
        "  /..\\--  ",
        " /_==_\\\\  ",
        "    ||    ",
        "    ||    ",
    )),
    _buddy("book_trolley", "북트롤리", RARITY_RARE, "forest", "BT", "cabinet", "cart", "읽을거리와 활동 자료를 차분하게 실어 나르는 이동 메이트예요.", (
        " .----.  ",
        "| [] []| ",
        "| .--. | ",
        "|_|__|_| ",
        "  oo oo  ",
    )),
    _buddy("seat_mapper", "자리맵퍼", RARITY_RARE, "cobalt", "SM", "grid", "seatmap", "자리와 역할 배치를 한눈에 읽히게 정리해 주는 배치 메이트예요.", (
        " .-----.  ",
        "|[] [] |  ",
        "|  ..  |  ",
        "|[]_[] |  ",
        "'------'  ",
    )),
    _buddy("label_printer", "라벨프린터", RARITY_RARE, "teal", "LP", "cabinet", "printer", "이름표와 준비물 표기를 또렷하게 뽑아 정리 속도를 높여 줘요.", (
        " .------. ",
        "|[__] ..| ",
        "| |____>| ",
        "|_|____>| ",
        "   ||||   ",
    )),
    _buddy("board_aurora", "칠판오로라", RARITY_EPIC, "cobalt", "BA", "aurora", "aurora", "칠판 위 분위기를 오로라처럼 넓고 맑게 바꿔 주는 에픽 메이트예요.", (
        " .------. ",
        "| .--. *| ",
        "| |..|~ | ",
        "| |__|  | ",
        " '------' ",
    )),
    _buddy("time_compass", "시간나침반", RARITY_EPIC, "plum", "TC", "spark", "compass", "복잡한 하루 속에서도 다음 한 걸음을 정확히 가리켜 줘요.", (
        "   /\\    ",
        " .-..-.  ",
        "<| 00 |> ",
        " '-..-'  ",
        "   \\/    ",
    )),
    _buddy("paper_castle", "종이성", RARITY_EPIC, "peach", "PA", "window", "castle", "수업 계획과 자료를 층층이 지켜 주는 작은 성 같은 메이트예요.", (
        "  /\\/\\   ",
        " /_.._\\  ",
        "| |__| | ",
        "| |  | | ",
        "|_|__|_| ",
    )),
    _buddy("ribbon_cabinet", "리본캐비닛", RARITY_EPIC, "rose", "RC", "cabinet", "cabinet_ribbon", "정리와 장식을 동시에 챙겨 교실의 결을 곱게 다듬어 줘요.", (
        " .-----. ",
        "| >==< | ",
        "| [] []| ",
        "| [] []| ",
        "'------' ",
    )),
    _buddy("class_window_star", "교실창별", RARITY_EPIC, "ice", "CW", "window", "window", "창가로 스미는 별빛처럼 교실 전체를 환하게 열어 줘요.", (
        " .-[]-.  ",
        "| *  * | ",
        "|  ..  | ",
        "| *  * | ",
        " '-----' ",
    )),
    _buddy("desk_arch", "교탁아치", RARITY_EPIC, "charcoal", "DA", "window", "desk", "수업의 중심이 흔들리지 않도록 교탁 흐름을 단단히 받쳐 줘요.", (
        "  ____   ",
        " / __ \\  ",
        "| |..| | ",
        "| |__| | ",
        "|_|  |_| ",
    )),
    _buddy("routine_station", "루틴정거장", RARITY_EPIC, "seafoam", "RS", "grid", "station", "매일 같은 루틴이 편안하게 출발하도록 자리를 잡아 줘요.", (
        " .------. ",
        "| [__]  | ",
        "|  ..   | ",
        "|__||___| ",
        "   /__\\   ",
    )),
    _buddy("class_lantern", "수업등불", RARITY_EPIC, "sunset", "LN", "spark", "lantern", "수업 흐름의 어두운 틈을 조용한 불빛으로 밝혀 줘요.", (
        "   /\\    ",
        " .-..-.  ",
        "| |..| | ",
        "| |__| | ",
        " '--||'  ",
    )),
    _buddy("time_display", "시간전광판", RARITY_EPIC, "denim", "TD", "grid", "display", "지금 해야 할 일을 가장 먼저 보이게 정리해 주는 메이트예요.", (
        " .------. ",
        "| 08:30 | ",
        "|  ..   | ",
        "|______ | ",
        "   /__\\   ",
    )),
    _buddy("notice_garden", "알림정원", RARITY_EPIC, "forest", "NG", "window", "garden", "공지와 일정이 한곳에서 차분히 피어나도록 정리해 주는 정원 메이트예요.", (
        "  .--.    ",
        " /_.._\\   ",
        "|  ..  |  ",
        "| |~~| |  ",
        "'------'  ",
    )),
    _buddy("library_arch", "독서아치", RARITY_EPIC, "butter", "LA", "window", "library", "읽기와 활동이 오가는 길목을 포근한 아치처럼 이어 줘요.", (
        "  ____    ",
        " /_[]_\\   ",
        "| |..| |  ",
        "| |__| |  ",
        "|_/__\\_|  ",
    )),
    _buddy("class_greenhouse", "교실온실", RARITY_EPIC, "leaf", "GH", "window", "greenhouse", "작은 아이디어와 교실 변화를 온실처럼 차분히 키워 주는 에픽 메이트예요.", (
        "  .--.    ",
        " /_.._\\   ",
        "| |~~| |  ",
        "| |__| |  ",
        "'------'  ",
    )),
    _buddy("archive_atrium", "기록아트리움", RARITY_EPIC, "charcoal", "AR", "cabinet", "atrium", "기록, 공지, 수업 메모가 흩어지지 않도록 한가운데에서 흐름을 모아 줘요.", (
        "  ____    ",
        " /_[]_\\   ",
        "| |..| |  ",
        "| |[]| |  ",
        "'------'  ",
    )),
    _buddy("board_lighthouse", "칠판등대", RARITY_LEGENDARY, "nightgold", "LH", "lighthouse", "lighthouse", "교실 전체 흐름을 가장 밝은 방향으로 이끄는 전설 메이트예요.", (
        "    /\\    ",
        "   /++\\   ",
        "  /_==_\\  ",
        " <| /\\ |> ",
        " <|_||_|> ",
        "   /__\\   ",
    )),
    _buddy("homeroom_observatory", "학급천문대", RARITY_LEGENDARY, "nightgold", "HO", "window", "observatory", "교실 전체 흐름을 멀리까지 읽어 내고 다음 움직임을 먼저 비춰 주는 전설 메이트예요.", (
        "  .--.    ",
        " /_++_\\   ",
        "|  /\\  |  ",
        "| |..| |  ",
        "|_|__|_|  ",
        "  /__\\    ",
    )),
    _buddy("festival_clocktower", "축제시계탑", RARITY_LEGENDARY, "sunset", "FT", "lighthouse", "clocktower", "행사와 하루의 리듬을 가장 또렷한 울림으로 맞춰 주는 전설 메이트예요.", (
        "   /\\     ",
        "  /12\\    ",
        " | .. |   ",
        " | || |   ",
        " |_||_|   ",
        "  /__\\    ",
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
    ("pearl", "펄룸", "ice", "PR"),
    ("graphite", "그라파이트", "charcoal", "GP"),
    ("ember", "앰버빛", "sunset", "AM"),
    ("ocean", "오션룸", "teal", "OC"),
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
