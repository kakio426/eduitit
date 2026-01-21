import requests
import json

def send_kakao_notification(inquiry):
    """
    카카오톡 파트너센터(또는 비즈니스 API 서비스)를 통해 알림을 전송하는 함수입니다.
    사용자님께서 가입하신 서비스(예: 솔라피, 알림톡 API 등)의 endpoint와 API Key를 나중에 여기에 넣으시면 됩니다.
    """
    # 현재는 개발 환경이므로 콘솔에 알림 내용을 출력합니다.
    print("\n" + "="*50)
    print("📢 카카오톡 알림 발송 (시뮬레이션)")
    print(f"문의자: {inquiry.name} ({inquiry.organization})")
    print(f"주제: {inquiry.topic}")
    print(f"연락처: {inquiry.phone}")
    print("위 내용이 카카오톡 파트너센터 연동을 통해 전송됩니다.")
    print("="*50 + "\n")
    
    # TODO: 사용자님의 파트너센터/API Key가 확보되면 실제 POST 요청 코드를 구현합니다.
    return True
