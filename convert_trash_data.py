import os
import time
import json
import urllib.request
import urllib.parse
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

EXCEL_PATH = os.path.expanduser('~/Downloads/서울특별시 가로쓰레기통 설치정보_202511.xlsx')
OUTPUT_JSON = os.path.join(os.path.dirname(__file__), 'seoul_trash_data.json')
CACHE_JSON = os.path.join(os.path.dirname(__file__), 'geocache.json')
KAKAO_API_KEY = os.environ.get("KAKAO_API_KEY", "4c956e6418f9a86bb0b1005785ec524e")

# 기존 캐시 로드 (있으면 재사용)
if os.path.exists(CACHE_JSON):
    try:
        with open(CACHE_JSON, 'r', encoding='utf-8') as f:
            geo_cache = json.load(f)
    except Exception:
        geo_cache = {}
else:
    geo_cache = {}

def clean_address(gu, addr):
    addr_str = str(addr).strip()
    gu_str = str(gu).strip()
    if not addr_str or addr_str.lower() == 'nan':
        return None
    # '서울특별시 종로구 사직로 125' 형식 정규화
    if not addr_str.startswith('서울'):
        if not addr_str.startswith(gu_str):
            full_addr = f"서울특별시 {gu_str} {addr_str}"
        else:
            full_addr = f"서울특별시 {addr_str}"
    else:
        full_addr = addr_str
    return full_addr

def geocode_kakao(address):
    if address in geo_cache:
        return geo_cache[address]

    # 1. 주소 검색 시도
    encoded = urllib.parse.quote(address)
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={encoded}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            if data.get('documents') and len(data['documents']) > 0:
                doc = data['documents'][0]
                res = (round(float(doc['y']), 6), round(float(doc['x']), 6))
                geo_cache[address] = res
                return res
            
            # 2. 건물/장소 키워드 검색 시도
            url_kw = f"https://dapi.kakao.com/v2/local/search/keyword.json?query={encoded}"
            req_kw = urllib.request.Request(url_kw, headers={"Authorization": f"KakaoAK {KAKAO_API_KEY}"})
            with urllib.request.urlopen(req_kw, timeout=4) as resp_kw:
                data_kw = json.loads(resp_kw.read().decode())
                if data_kw.get('documents') and len(data_kw['documents']) > 0:
                    doc = data_kw['documents'][0]
                    res = (round(float(doc['y']), 6), round(float(doc['x']), 6))
                    geo_cache[address] = res
                    return res
    except Exception:
        pass
    
    geo_cache[address] = None
    return None

def main():
    print("1. 엑셀 파일 로딩 중...")
    df = pd.read_excel(EXCEL_PATH, header=4)
    print(f"총 {len(df)}개 쓰레기통 레코드 로드됨.")

    # 동일 위치 통합 (일반/재활용/담배꽁초)
    location_dict = {}

    for idx, row in df.iterrows():
        gu = row['자치구명']
        raw_addr = row['설치위치']
        detail = row['세부 위치']
        trash_type = str(row['수거 쓰레기 종류']).strip()
        loc_type = str(row['설치 장소 유형']).strip()

        full_addr = clean_address(gu, raw_addr)
        if not full_addr:
            continue

        key = (str(gu).strip(), full_addr)
        if key not in location_dict:
            location_dict[key] = {
                "gu": str(gu).strip(),
                "address": full_addr,
                "details": set(),
                "loc_types": set(),
                "has_recycle": False,
                "has_cigarette": False
            }

        if pd.notna(detail) and str(detail).strip() != 'nan':
            location_dict[key]["details"].add(str(detail).strip())
        if pd.notna(loc_type) and str(loc_type).strip() != 'nan':
            location_dict[key]["loc_types"].add(str(loc_type).strip())

        if '담배' in trash_type or '꽁초' in trash_type:
            location_dict[key]["has_cigarette"] = True
        if '일반' in trash_type or '재활용' in trash_type:
            location_dict[key]["has_recycle"] = True

    unique_keys = list(location_dict.keys())
    print(f"2. 중복 위치 병합 후 고유 지점: {len(unique_keys)}곳")

    # 카카오 지오코딩 병렬 처리 (15개 스레드)
    addresses_to_fetch = [k[1] for k in unique_keys if k[1] not in geo_cache]
    print(f"3. 카카오 API 변환 대상: {len(addresses_to_fetch)}건 (기존 캐시: {len(geo_cache)}건)")

    completed_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(geocode_kakao, addr): addr for addr in addresses_to_fetch}
        for future in as_completed(futures):
            completed_count += 1
            if completed_count % 300 == 0 or completed_count == len(addresses_to_fetch):
                elapsed = time.time() - start_time
                print(f"진행 상황: {completed_count}/{len(addresses_to_fetch)}건 완료 ({elapsed:.1f}초 경과)...")

    # 캐시 파일 저장
    with open(CACHE_JSON, 'w', encoding='utf-8') as f:
        json.dump(geo_cache, f, ensure_ascii=False)

    # 4. 최종 JSON 리스트 생성
    result_list = []
    item_id = 1
    success_count = 0

    for key, info in location_dict.items():
        coords = geo_cache.get(info["address"])
        if not coords:
            # 주소 끝자리 번지수가 없거나 검색 안 될 때 구 + 도로명만으로 재시도
            continue

        lat, lng = coords
        # 서울시 경계 내 좌표 필터 (lat: 37.4 ~ 37.7, lng: 126.7 ~ 127.3)
        if not (37.35 <= lat <= 37.75 and 126.75 <= lng <= 127.25):
            continue

        # 타입 결정
        if info["has_cigarette"] and info["has_recycle"]:
            item_type = "both"
        elif info["has_cigarette"]:
            item_type = "cigarette"
        else:
            item_type = "recycle"

        # 대표 명칭 결정
        details_list = [d for d in info["details"] if d]
        loc_types_list = [lt for lt in info["loc_types"] if lt]

        if details_list:
            display_name = details_list[0]
        else:
            display_name = info["address"].replace("서울특별시 ", "")

        desc_parts = []
        if details_list:
            desc_parts.append(", ".join(details_list))
        if loc_types_list:
            desc_parts.append(f"({', '.join(loc_types_list)})")
        desc = " ".join(desc_parts) if desc_parts else info["address"]

        result_list.append({
            "id": item_id,
            "name": display_name,
            "gu": info["gu"],
            "addr": info["address"],
            "lat": lat,
            "lng": lng,
            "type": item_type,
            "desc": desc
        })
        item_id += 1
        success_count += 1

    # 최종 JSON 파일로 저장
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

    print(f"\n변환 완료!")
    print(f"- 성공적으로 좌표 변환된 쓰레기통: {success_count}곳")
    print(f"- 저장 경로: {OUTPUT_JSON}")
    print(f"- 파일 크기: {os.path.getsize(OUTPUT_JSON) / 1024:.1f} KB")

if __name__ == '__main__':
    main()
