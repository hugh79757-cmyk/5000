"""ETAP 블로그용 제휴 링크 생성 모듈

지원 제휴 프로그램:
- Trip.com (호텔/항공권)
- Skyscanner (항공권 비교)
- Booking.com (호텔)
- Viator (투어/액티비티) - DB의 deep_link 사용
- Klook (액티비티)
- Rentalcars.com (렌터카)

주의: API 키는 .env 파일에서 로드함.
"""

import hashlib
import hmac
import logging
import os
import sys
import time
from typing import Optional

sys.path.insert(0, "/Users/twinssn/Projects/5000")
from dotenv import load_dotenv

load_dotenv("/Users/twinssn/Projects/5000/.env")

logger = logging.getLogger(__name__)


class ETAPAffiliate:
    """ETAP 블로그 제휴 링크 생성기"""
    
    def __init__(self):
        # Trip.com API
        self.trip_access_key = os.environ.get("TRIP_ACCESS_KEY", "")
        self.trip_secret_key = os.environ.get("TRIP_SECRET_KEY", "")
        self.trip_partner_id = os.environ.get("TRIP_PARTNER_ID", "")
        
        # Skyscanner API
        self.skyscanner_api_key = os.environ.get("SKYSCANNER_API_KEY", "")
        
        # Booking.com API
        self.booking_api_key = os.environ.get("BOOKING_API_KEY", "")
        
        # Viator (이미 DB에 deep_link 있음 - 별도 API 불필요)
        self.viator_api_key = os.environ.get("VIATOR_API_KEY", "")
    
    def is_configured(self) -> bool:
        """최소 하나의 제휴 프로그램이 설정되었는지 확인"""
        return bool(
            self.trip_access_key or 
            self.skyscanner_api_key or 
            self.booking_api_key
        )
    
    def is_trip_configured(self) -> bool:
        return bool(self.trip_access_key and self.trip_secret_key and self.trip_partner_id)
    
    def is_skyscanner_configured(self) -> bool:
        return bool(self.skyscanner_api_key)
    
    def is_booking_configured(self) -> bool:
        return bool(self.booking_api_key)
    
    def generate_trip_hotel_link(self, hotel_id: str, checkin: str, checkout: str, 
                                  rooms: int = 1, adults: int = 2) -> str:
        """
        Trip.com 호텔 제휴 링크 생성
        
        Args:
            hotel_id: Trip.com 호텔 ID
            checkin: 체크인 날짜 (YYYY-MM-DD)
            checkout: 체크아웃 날짜 (YYYY-MM-DD)
            rooms: 객실 수
            adults: 성인 수
        
        Returns:
            제휴 딥링크 URL
        """
        if not self.is_trip_configured():
            logger.warning("Trip.com API 키 미설정 - 제휴 링크 생성 불가")
            return ""
        
        # Trip.com 제휴 링크 생성 로직
        # 실제 구현은 Trip.com API 문서 참조
        base_url = "https://www.trip.com/hotels"
        params = {
            "hotelId": hotel_id,
            "checkin": checkin,
            "checkout": checkout,
            "rooms": rooms,
            "adults": adults,
            "partnerid": self.trip_partner_id,
        }
        
        # 서명 생성 (Trip.com API 요구사항)
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        message = f"GET{hotel_id}{timestamp}{query_string}"
        signature = hmac.new(
            self.trip_secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        url = f"{base_url}/{hotel_id}?{query_string}&signature={signature}&timestamp={timestamp}"
        return url
    
    def generate_trip_flight_link(self, origin: str, destination: str,
                                   checkin: str, checkout: str,
                                   passengers: int = 1) -> str:
        """Trip.com 항공권 제휴 링크 생성"""
        if not self.is_trip_configured():
            return ""
        
        base_url = "https://www.trip.com/flights"
        params = {
            "from": origin,
            "to": destination,
            "date": checkin,
            "returnDate": checkout,
            "passengers": passengers,
            "partnerid": self.trip_partner_id,
        }
        
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        message = f"GET flights {timestamp}{query_string}"
        signature = hmac.new(
            self.trip_secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        url = f"{base_url}?{query_string}&signature={signature}&timestamp={timestamp}"
        return url
    
    def generate_skyscanner_link(self, origin: str, destination: str,
                                  checkin: str, checkout: str = "") -> str:
        """
        Skyscanner 제휴 링크 생성
        
        Skyscanner는 정적 링크 방식 사용 가능.
        실제 구현은 Skyscanner Affiliate API 참조.
        """
        if not self.is_skyscanner_configured():
            logger.warning("Skyscanner API 키 미설정")
            # 폴백: 기본 Skyscanner 검색 링크
            encoded_origin = self._encode_airport(origin)
            encoded_dest = self._encode_airport(destination)
            return f"https://www.skyscanner.com/transport/flights/{encoded_origin}/{encoded_dest}/{checkin}/"
        
        # API 기반 링크 생성 (구현 필요)
        # Skyscanner Affiliate API: https://affiliate.skyscanner.net/
        return f"https://www.skyscanner.com/transport/flights/{origin}/{destination}/{checkin}/"
    
    def _encode_airport(self, airport: str) -> str:
        """공항 코드/이름 인코딩"""
        # IATA 코드면 그대로, 도시명이면 인코딩
        if len(airport) == 3 and airport.isalpha():
            return airport.upper()
        return airport.replace(" ", "-").lower()
    
    def generate_booking_hotel_link(self, hotel_id: str, checkin: str, 
                                     checkout: str, locale: str = "en-us") -> str:
        """Booking.com 제휴 링크 생성"""
        if not self.is_booking_configured():
            logger.warning("Booking.com API 키 미설정")
            return ""
        
        # Booking.com Affiliate Partner API
        # 실제 구현은 Booking.com API 문서 참조
        base_url = "https://www.booking.com/hotel"
        return f"{base_url}/{hotel_id}.html?aid={self.booking_api_key}&checkin={checkin}&checkout={checkout}&locale={locale}"
    
    def get_viator_deep_link(self, tour_name: str, city: str) -> Optional[str]:
        """
        Viator 투어 딥링크 조회.
        실제로는 DB의 viator_tours 테이블에서 deep_link를 가져옴.
        이 메서드는 DB 연결 없이 호출 가능한 폴백 제공.
        """
        # 실제 구현은 DB 조회 필요
        # 5000/pipelines/etap/*_writer.py의 fetch_tours() 참조
        logger.info(f"Viator 딥링크 조회: {tour_name} ({city})")
        return None  # DB 연결 없이 호출 시 빈 값 반환
    
    def get_product_card_html(self, provider: str, name: str, url: str,
                               price: str = "", image: str = "",
                               description: str = "") -> str:
        """
        제휴 상품 카드 HTML 생성
        
        Args:
            provider: 'trip', 'skyscanner', 'booking', 'viator', 'klook'
            name: 상품명
            url: 제휴 링크
            price: 가격 (선택)
            image: 이미지 URL (선택)
            description: 설명 (선택)
        
        Returns:
            HTML 문자열
        """
        provider_labels = {
            "trip": "Trip.com",
            "skyscanner": "Skyscanner",
            "booking": "Booking.com",
            "viator": "Viator",
            "klook": "Klook",
            "rentalcars": "Rentalcars.com",
        }
        
        label = provider_labels.get(provider, provider)
        
        if image:
            card_html = f'''
<div class="affiliate-card">
  <a href="{url}" target="_blank" rel="nofollow noopener">
    <img src="{image}" alt="{name}" loading="lazy">
  </a>
  <div class="affiliate-card-body">
    <span class="affiliate-card-provider">{label}</span>
    <a href="{url}" target="_blank" rel="nofollow noopener">
      <strong>{name}</strong>
    </a>
    {f'<p class="affiliate-card-price">{price}</p>' if price else ''}
    {f'<p class="affiliate-card-desc">{description}</p>' if description else ''}
  </div>
</div>'''
        else:
            card_html = f'''
<div class="affiliate-card text-only">
  <span class="affiliate-card-provider">{label}</span>
  <a href="{url}" target="_blank" rel="nofollow noopener">
    <strong>{name}</strong>
  </a>
  {f'<p class="affiliate-card-price">{price}</p>' if price else ''}
  {f'<p class="affiliate-card-desc">{description}</p>' if description else ''}
</div>'''
        
        return card_html
    
    def get_disclosure_html(self) -> str:
        """제휴 면책 문구 HTML"""
        return '''
<div class="affiliate-disclosure">
  <p><strong>제휴Disclosure:</strong> 이 포스트에는 제휴 링크가 포함될 수 있습니다. 
  링크를 통해 예약/구매 시 추가 비용 없이 소정의 수수료를 받을 수 있습니다.</p>
</div>
'''


# 싱글톤 인스턴스
_affiliate_instance = None

def get_affiliate() -> ETAPAffiliate:
    """ETAPAffiliate 싱글톤 반환"""
    global _affiliate_instance
    if _affiliate_instance is None:
        _affiliate_instance = ETAPAffiliate()
    return _affiliate_instance


# 테스트용 메인
if __name__ == "__main__":
    af = get_affiliate()
    print(f"Trip.com 설정: {'OK' if af.is_trip_configured() else '미설정'}")
    print(f"Skyscanner 설정: {'OK' if af.is_skyscanner_configured() else '미설정'}")
    print(f"Booking.com 설정: {'OK' if af.is_booking_configured() else '미설정'}")
    print(f"전체 설정: {'OK' if af.is_configured() else '미설정'}")
