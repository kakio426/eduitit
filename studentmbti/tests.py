from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import TestSession, StudentMBTIResult
from .student_mbti_data import STUDENT_QUESTIONS_LOW, STUDENT_QUESTIONS_HIGH
from happy_seed.models import HSClassroom

class StudentMBTITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teacher', password='password')
        self.user.email = 'teacher@example.com'
        self.user.save()
        
        # Profile is created by signal. Just update it.
        # UserProfile.objects.get_or_create(user=self.user) might be redundant due to signal
        if hasattr(self.user, 'userprofile'):
            self.user.userprofile.nickname = 'TeacherTest'
            self.user.userprofile.save()
        else:
            from core.models import UserProfile
            UserProfile.objects.create(user=self.user, nickname='TeacherTest')
        
        self.client = Client()
        self.client.login(username='teacher', password='password')

    def test_test_session_has_test_type_field(self):
        """TestSession 모델에 test_type 필드가 있는지 확인"""
        session = TestSession.objects.create(session_name="Test Session", teacher=self.user)
        self.assertTrue(hasattr(session, 'test_type'))
        self.assertEqual(session.test_type, 'low')  # Default value check

    def test_data_constants_exist(self):
        """데이터 상수가 존재하는지 확인"""
        self.assertIsNotNone(STUDENT_QUESTIONS_LOW)
        self.assertIsNotNone(STUDENT_QUESTIONS_HIGH)
        self.assertEqual(len(STUDENT_QUESTIONS_LOW), 12)
        self.assertEqual(len(STUDENT_QUESTIONS_HIGH), 28)

    def test_session_create_accepts_test_type(self):
        """세션 생성 시 test_type을 저장하는지 확인"""
        response = self.client.post('/studentmbti/session/create/', {
            'session_name': 'High Grade Session',
            'test_type': 'high'
        })
        self.assertEqual(response.status_code, 302)
        session = TestSession.objects.get(session_name='High Grade Session')
        self.assertEqual(session.test_type, 'high')

    def test_session_create_uses_active_classroom_when_available(self):
        """세션 학급 단축키가 있으면 TestSession.classroom에 자동 연결"""
        classroom = HSClassroom.objects.create(teacher=self.user, name='3학년 2반')

        session_store = self.client.session
        session_store['active_classroom_source'] = 'hs'
        session_store['active_classroom_id'] = str(classroom.id)
        session_store.save()

        response = self.client.post('/studentmbti/session/create/', {
            'session_name': 'Classroom Linked Session',
            'test_type': 'low',
        })
        self.assertEqual(response.status_code, 302)

        created = TestSession.objects.get(session_name='Classroom Linked Session')
        self.assertEqual(created.classroom_id, classroom.id)

    def test_session_test_serves_correct_questions(self):
        """세션 유형에 따라 다른 질문 개수를 반환하는지 확인"""
        # Test as anonymous student
        self.client.logout()

        # Low Session
        session_low = TestSession.objects.create(session_name="Low", teacher=self.user, test_type='low')
        response_low = self.client.get(f'/studentmbti/session/{session_low.id}/')
        self.assertEqual(response_low.status_code, 200)
        self.assertIn('questions', response_low.context)
        self.assertEqual(len(response_low.context['questions']), 12)

        # High Session
        session_high = TestSession.objects.create(session_name="High", teacher=self.user, test_type='high')
        response_high = self.client.get(f'/studentmbti/session/{session_high.id}/')
        self.assertEqual(response_high.status_code, 200)
        self.assertIn('questions', response_high.context)
        self.assertEqual(len(response_high.context['questions']), 28)

    def test_analyze_logic_high_grade(self):
        """고학년용 분석 로직 (7문항, 컷오프 4) 확인"""
        # Test as anonymous student
        self.client.logout()

        session = TestSession.objects.create(session_name="High", teacher=self.user, test_type='high')
        
        # E성향 4개, I성향 3개 -> E
        data = {
            'student_name': 'Tester',
            # E/I: Q1-Q7. 0 is E, 1 is I.
            'q1': 0, 'q2': 0, 'q3': 0, 'q4': 0, 'q5': 1, 'q6': 1, 'q7': 1, # 4E, 3I -> E
            # S/N: Q8-Q14. 0 is S, 1 is N.
            'q8': 0, 'q9': 0, 'q10': 0, 'q11': 0, 'q12': 1, 'q13': 1, 'q14': 1, # 4S, 3N -> S
            # T/F: Q15-Q21. 0 is T, 1 is F.
            'q15': 0, 'q16': 0, 'q17': 0, 'q18': 0, 'q19': 1, 'q20': 1, 'q21': 1, # 4T, 3F -> T
            # J/P: Q22-Q28. 0 is J, 1 is P.
            'q22': 0, 'q23': 0, 'q24': 0, 'q25': 0, 'q26': 1, 'q27': 1, 'q28': 1, # 4J, 3P -> J
        }
        
        response = self.client.post(f'/studentmbti/session/{session.id}/analyze/', data)
        self.assertEqual(response.status_code, 302)
        
        # Get result created by analyze view
        # Since analyze creates a NEW result if session is empty (logout above),
        # we can expect one result for this session.
        result = StudentMBTIResult.objects.filter(session=session).first()
        self.assertIsNotNone(result)
        self.assertEqual(result.mbti_type, 'ESTJ')
