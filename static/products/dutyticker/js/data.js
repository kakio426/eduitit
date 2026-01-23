const mockRoles = [
    {
        id: "r1",
        name: "칠판 지우기",
        assignee: "김철수",
        description: "매 시간 수업이 끝나면 칠판을 깨끗이 지워주세요.",
        timeSlot: "쉬는시간",
        status: "pending",
    },
    {
        id: "r2",
        name: "우유 당번",
        assignee: "이영희",
        description: "2교시 후 우유 급식을 가져옵니다.",
        timeSlot: "2교시 후",
        status: "pending",
    },
    {
        id: "r3",
        name: "창문 열기",
        assignee: "박민수",
        description: "쉬는 시간마다 환기를 위해 창문을 엽니다.",
        timeSlot: "쉬는시간",
        status: "completed",
    },
    {
        id: "r4",
        name: "에너지 지킴이",
        assignee: "최지우",
        description: "이동 수업 시 전등과 선풍기를 끕니다.",
        timeSlot: "수시로",
        status: "pending",
    }
];

const mockStudents = [
    '김철수', '이영희', '박지민', '최수민', '정우성',
    '강다니엘', '아이유', '유재석', '박명수', '노홍철',
    '정형돈', '하동훈', '길성준', '전진', '황광희',
    '양세형', '조세호', '남창희', '이광수', '송지효',
    '김종국', '지석진', '하하', '개리', '송중기'
];

const mockWeeklySchedule = {
    1: [ // Monday
        { id: "mon1", name: "1교시 국어", startTime: "09:00", endTime: "09:40" },
        { id: "mon2", name: "2교시 사회", startTime: "09:50", endTime: "10:30" },
        { id: "mon3", name: "3교시 과학", startTime: "10:40", endTime: "11:20" },
        { id: "mon4", name: "4교시 수학", startTime: "11:30", endTime: "12:10" },
        { id: "mon5", name: "5교시 체육", startTime: "13:00", endTime: "13:40" },
        { id: "mon6", name: "6교시 음악", startTime: "13:50", endTime: "14:30" },
    ],
    2: [ // Tuesday
        { id: "tue1", name: "1교시 체육", startTime: "09:00", endTime: "09:40" },
        { id: "tue2", name: "2교시 미술", startTime: "09:50", endTime: "10:30" },
        { id: "tue3", name: "3교시 음악", startTime: "10:40", endTime: "11:20" },
        { id: "tue4", name: "4교시 영어", startTime: "11:30", endTime: "12:10" },
        { id: "tue5", name: "5교시 국어", startTime: "13:00", endTime: "13:40" },
        { id: "tue6", name: "6교시 사회", startTime: "13:50", endTime: "14:30" },
    ],
    3: [ // Wednesday
        { id: "wed1", name: "1교시 국어", startTime: "09:00", endTime: "09:40" },
        { id: "wed2", name: "2교시 수학", startTime: "09:50", endTime: "10:30" },
        { id: "wed3", name: "3교시 창체", startTime: "10:40", endTime: "11:20" },
        { id: "wed4", name: "4교시 사회", startTime: "11:30", endTime: "12:10" },
        { id: "wed5", name: "5교시 과학", startTime: "13:00", endTime: "13:40" },
        { id: "wed6", name: "6교시 실과", startTime: "13:50", endTime: "14:30" },
    ],
    4: [ // Thursday
        { id: "thu1", name: "1교시 과학", startTime: "09:00", endTime: "09:40" },
        { id: "thu2", name: "2교시 영어", startTime: "09:50", endTime: "10:30" },
        { id: "thu3", name: "3교시 체육", startTime: "10:40", endTime: "11:20" },
        { id: "thu4", name: "4교시 국어", startTime: "11:30", endTime: "12:10" },
        { id: "thu5", name: "5교시 수학", startTime: "13:00", endTime: "13:40" },
        { id: "thu6", name: "6교시 영어", startTime: "13:50", endTime: "14:30" },
    ],
    5: [ // Friday
        { id: "fri1", name: "1교시 수학", startTime: "09:00", endTime: "09:40" },
        { id: "fri2", name: "2교시 실과", startTime: "09:50", endTime: "10:30" },
        { id: "fri3", name: "3교시 사회", startTime: "10:40", endTime: "11:20" },
        { id: "fri4", name: "4교시 국어", startTime: "11:30", endTime: "12:10" },
        { id: "fri5", name: "5교시 창체", startTime: "13:00", endTime: "13:40" },
        { id: "fri6", name: "6교시 자치", startTime: "13:50", endTime: "14:30" },
    ],
    0: [], // Sunday
    6: [], // Saturday
};
