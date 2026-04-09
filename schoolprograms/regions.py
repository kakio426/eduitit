REGION_SUGGESTIONS_BY_PROVINCE = {
    "nationwide": [
        "전국",
        "수도권",
        "서울 전역",
        "경기 남부",
        "경기 북부",
        "충청권",
        "호남권",
        "영남권",
    ],
    "seoul": ["강남구", "강서구", "노원구", "마포구", "송파구", "영등포구", "은평구", "중랑구"],
    "busan": ["해운대구", "부산진구", "사하구", "수영구", "연제구", "금정구"],
    "daegu": ["수성구", "달서구", "북구", "중구", "동구"],
    "incheon": ["부평구", "연수구", "남동구", "서구", "계양구"],
    "gwangju": ["광산구", "북구", "서구", "남구"],
    "daejeon": ["유성구", "서구", "중구", "대덕구"],
    "ulsan": ["남구", "북구", "중구", "울주군"],
    "sejong": ["세종시"],
    "gyeonggi": ["수원", "성남", "용인", "고양", "화성", "부천", "안산", "평택", "남양주", "의정부"],
    "gangwon": ["춘천", "원주", "강릉", "동해", "속초"],
    "chungbuk": ["청주", "충주", "제천", "진천", "음성"],
    "chungnam": ["천안", "아산", "서산", "논산", "당진"],
    "jeonbuk": ["전주", "군산", "익산", "정읍", "남원"],
    "jeonnam": ["순천", "여수", "목포", "광양", "나주"],
    "gyeongbuk": ["포항", "구미", "경주", "안동", "김천"],
    "gyeongnam": ["창원", "김해", "진주", "양산", "거제"],
    "jeju": ["제주시", "서귀포시"],
}


DEFAULT_REGION_SUGGESTIONS = [
    "서울",
    "수원",
    "성남",
    "고양",
    "부천",
    "인천 연수구",
    "대전 유성구",
    "천안",
    "전주",
    "창원",
    "제주",
]


def region_suggestions_for(province: str) -> list[str]:
    province = str(province or "").strip()
    suggestions = list(DEFAULT_REGION_SUGGESTIONS)
    if province and province in REGION_SUGGESTIONS_BY_PROVINCE:
        for item in REGION_SUGGESTIONS_BY_PROVINCE[province]:
            if item not in suggestions:
                suggestions.append(item)
    return suggestions
