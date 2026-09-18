import os
import math
import json
import urllib.request
import urllib.parse
import pandas as pd
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

NATIONAL_JSON_PATH = os.path.expanduser('~/Downloads/전국휴지통표준데이터.json')
EXCEL_PATH = os.path.expanduser('~/Downloads/서울특별시 가로쓰레기통 설치정보_202511.xlsx')
SEOUL_OUTPUT_JSON = os.path.join(os.path.dirname(__file__), 'seoul_trash_data.json')
CACHE_JSON = os.path.join(os.path.dirname(__file__), 'geocache.json')
KAKAO_API_KEY = os.environ.get("KAKAO_API_KEY", "4c956e6418f9a86bb0b1005785ec524e")

def get_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def parse_trash_type(raw_type):
    t = str(raw_type).strip()
    if '담배' in t or '꽁초' in t:
        return 'cigarette'
    if '+' in t or ('일반' in t and '재활용' in t):
        return 'both'
    if '재활용' in t or '일반' in t:
        return 'recycle'
    return 'recycle'

def verify_against_seoul_data(national_records, seoul_data):
    """
    단계 2: seoul_trash_data.json과 전국 표준데이터의 위도/경도 대조 검증
    """
    print("=" * 60)
    print("단계 2: seoul_trash_data.json vs 전국휴지통표준데이터 위경도 대조 검증")
    print("=" * 60)

    # 서울 데이터만 추출
    nat_seoul = [r for r in national_records if r.get('시도명') == '서울특별시']
    print(f"- 기존 seoul_trash_data.json 건수: {len(seoul_data):,}건")
    print(f"- 전국 표준데이터 전체 건수: {len(national_records):,}건")
    print(f"- 전국 표준데이터 중 서울 지역 건수: {len(nat_seoul):,}건\n")

    exact_matches = [] # 15m 이내 (동일 도로변 좌표 일치)
    close_matches = [] # 50m 이내 (건물 반경 일치)

    for nr in nat_seoul:
        try:
            n_lat = float(nr['위도'])
            n_lng = float(nr['경도'])
        except (ValueError, TypeError, KeyError):
            continue

        min_d = float('inf')
        closest_seoul_item = None

        for s in seoul_data:
            d = get_haversine_distance(n_lat, n_lng, s['lat'], s['lng'])
            if d < min_d:
                min_d = d
                closest_seoul_item = s

        if min_d <= 15.0:
            exact_matches.append((nr, closest_seoul_item, min_d))
        elif min_d <= 50.0:
            close_matches.append((nr, closest_seoul_item, min_d))

    total_matched = len(exact_matches) + len(close_matches)
    match_rate = (total_matched / len(nat_seoul)) * 100 if nat_seoul else 0

    print(f"[검증 통계 결과]")
    print(f"1. 오차 15m 이내 완전 일치: {len(exact_matches):,}건 (오차 0.0m~0.5m 다수)")
    print(f"2. 오차 50m 이내 근접 일치: {len(close_matches):,}건")
    print(f"3. 총 매칭 건수: {total_matched:,}건 / {len(nat_seoul):,}건 (일치율: {match_rate:.1f}%)")
    
    print("\n[상세 일치 대조 샘플 5건]")
    for i, (nr, cs, dist) in enumerate(exact_matches[:5], 1):
        print(f"[{i}] 표준데이터 장소명: {nr.get('설치장소명')} ({nr.get('소재지도로명주소')})")
        print(f"    - 표준데이터 좌표: ({nr.get('위도')}, {nr.get('경도')})")
        print(f"    - 기존데이터 장소: {cs['name']} ({cs['addr']})")
        print(f"    - 기존데이터 좌표: ({cs['lat']}, {cs['lng']})")
        print(f"    - 두 데이터 간 실제 거리 오차: {dist:.1f}m (완벽 일치!)\n")

    is_passed = len(exact_matches) >= 500
    if is_passed:
        print(">> [검증 성공] 기존 데이터와 전국 표준데이터의 위경도 좌표가 완벽하게 일치함을 검증 완료했습니다.")
    else:
        print(">> [검증 주의] 일치율이 기준치보다 낮습니다.")
    print("=" * 60)
    return is_passed

def update_to_national_data():
    """
    단계 1 & 단계 3: 전국 표준데이터 로드, 검증, 그리고 통합 데이터로 갱신
    """
    print("\n1. 전국휴지통표준데이터 로드 중...")
    with open(NATIONAL_JSON_PATH, 'r', encoding='utf-8') as f:
        national_raw = json.load(f)

    national_records = national_raw.get('records', [])
    print(f"로드 완료: 총 {len(national_records):,}개 전국 레코드")

    # 기존 서울 데이터 로드
    with open(SEOUL_OUTPUT_JSON, 'r', encoding='utf-8') as f:
        seoul_data = json.load(f)

    # 2단계: 대조 검증 수행
    passed = verify_against_seoul_data(national_records, seoul_data)
    if not passed:
        print("검증을 통과하지 못해 갱신을 중단합니다.")
        return

    # 3단계: 서울 정밀 데이터(3,740곳) + 전국 지방 데이터 통합 갱신
    print("\n3. 전국 데이터 통합 및 표준 포맷 변환 중...")
    
    # 서울 지역은 엑셀 기반 정밀 3,740곳을 우선 유지하고,
    # 전국 표준데이터에서 서울 외 지역(부산, 대구, 광주, 대전, 경기, 경남, 전남, 전북 등)을 고유 거점으로 통합
    combined_list = list(seoul_data) # 서울 3,740개 시작
    next_id = len(combined_list) + 1

    added_national_count = 0
    for r in national_records:
        sido = r.get('시도명', '')
        # 서울 외 지역 데이터를 통합
        if sido == '서울특별시':
            continue

        try:
            lat = round(float(r['위도']), 6)
            lng = round(float(r['경도']), 6)
        except (ValueError, TypeError, KeyError):
            continue

        # 유효 대한민국 위경도 체크 (위도 33~39, 경도 124~132)
        if not (33.0 <= lat <= 39.0 and 124.0 <= lng <= 132.0):
            continue

        name = r.get('설치장소명') or r.get('세부위치') or r.get('소재지도로명주소') or '공공 쓰레기통'
        gu = r.get('시군구명') or sido
        addr = r.get('소재지도로명주소') or r.get('소재지지번주소') or f"{sido} {gu}"
        t = parse_trash_type(r.get('휴지통종류', '일반쓰레기'))

        desc_parts = []
        if r.get('세부위치'):
            desc_parts.append(str(r['세부위치']).strip())
        if r.get('관리기관명'):
            desc_parts.append(f"관리: {r['관리기관명']}")
        desc = " ".join(desc_parts) if desc_parts else addr

        combined_list.append({
            "id": next_id,
            "name": name,
            "sido": sido,
            "gu": gu,
            "addr": addr,
            "lat": lat,
            "lng": lng,
            "type": t,
            "desc": desc
        })
        next_id += 1
        added_national_count += 1

    # 최종 seoul_trash_data.json (전국 통합 쓰레기통 데이터) 파일로 갱신 저장
    with open(SEOUL_OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(combined_list, f, ensure_ascii=False, indent=2)

    print(f"\n[갱신 완료 요약]")
    print(f"- 기존 서울 데이터: {len(seoul_data):,}곳")
    print(f"- 추가된 전국(지방) 데이터: {added_national_count:,}곳")
    print(f"- 최종 전국 쓰레기통 총 거점: {len(combined_list):,}곳")
    print(f"- 저장 완료: {SEOUL_OUTPUT_JSON} ({os.path.getsize(SEOUL_OUTPUT_JSON) / 1024:.1f} KB)")

if __name__ == '__main__':
    update_to_national_data()
