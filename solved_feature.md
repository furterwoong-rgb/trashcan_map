# 쓱싹(SSEUK-SSAK) 완료된 기능 기록서 (solved_feature.md)

이 문서는 개발이 완료되어 실제 운영 환경([https://trashcan-map.vercel.app](https://trashcan-map.vercel.app))에 배포 및 검증된 기능들의 상세 기술 명세와 구현 기록입니다.

---

## 📌 완료된 기능 목록

| 기능명 | 구현 일자 / 커밋 | 주요 기술 스택 | 핵심 성과 |
| :--- | :--- | :--- | :--- |
| **1. 모바일 지도 해상도 고급화** | `b051b89` (`map_image_resolution_solved`) | Kakao Maps Web API v2 HD Engine | Retina 디스플레이 모바일 타일 선명도 100% 개선 |
| **2. GA4 퍼널 전환율 추적** | `bf55fe8` | Google Analytics 4 (Measurement Protocol) | 진입 ➔ 허용 ➔ 마커 클릭 ➔ 길찾기 클릭 전 과정 측정 |
| **3. 실시간 위치 매핑 & 웹 도보 내비** | `c6df141` (`real_time_mapping_solved`) | HTML5 Geolocation, Kakao Polyline, Circle | 진짜 지도앱 같은 Lock-in, 실시간 거리/시간 HUD, 도착 진동 |

---

## 1. 모바일 지도 해상도 고급화 (Kakao Maps Web API HD 엔진 전환)

<!-- 
  [공식 출처 레퍼런스]
  1. 카카오 지도 Web API 시작 가이드: https://apis.map.kakao.com/web/guide/
  2. 카카오 개발자 콘솔 (도메인 등록 및 앱키): https://developers.kakao.com/console/app
  3. 카카오 지도 고해상도(HD) 기본 지원 및 명세: https://apis.map.kakao.com/web/documentation/#disableHD
  4. 커스텀 오버레이(CustomOverlay) 공식 샘플: https://apis.map.kakao.com/web/sample/customOverlay1/
  5. 마커 클러스터러(MarkerClusterer) 공식 샘플: https://apis.map.kakao.com/web/sample/basicClusterer/
-->

### 🎯 도입 배경 및 목표
* 기존 Leaflet 오픈소스 타일은 모바일 고해상도(Retina / AMOLED) 화면에서 도로명 폰트와 경계선이 흐릿하게 깨지는 문제 존재.
* 카카오 지도 Web API의 HD 타일 서빙 엔진을 도입하여 모바일 화면에서 벡터급 선명도 제공.

### 🛠️ 구현 상세
1. **카카오 개발자 콘솔 Web 플랫폼 도메인 등록**:
   - 도메인 화이트리스트 등록: `http://localhost:3000`, `https://trashcan-map.vercel.app`
2. **SDK 비동기 로딩**:
   ```html
   <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey=발급받은_JAVASCRIPT_KEY&libraries=clusterer&autoload=false"></script>
   ```
3. **지도 컨테이너 초기화 및 HD 렌더링**:
   ```javascript
   kakao.maps.load(() => {
     const container = document.getElementById('map');
     const options = {
       center: new kakao.maps.LatLng(userPos.lat, userPos.lng),
       level: 4 // 도보 탐색 최적 줌 레벨
     };
     map = new kakao.maps.Map(container, options);
     window.addEventListener('resize', () => map.relayout());
   });
   ```
4. **CustomOverlay 마커 및 뷰포트 기반 60fps 렌더링**:
   - `kakao.maps.event.addListener(map, 'idle', ...)` 이벤트를 통해 현재 화면 영역(`map.getBounds()`) 내 마커만 동적 렌더링하여 모바일 60fps 보장.

---

## 2. 퍼널 전환율 추적 (GA4 Custom Events)

### 🎯 도입 배경 및 목표
* 사용자가 서비스에 접속하여 실제로 길찾기 버튼을 누르고 쓰레기통을 찾아가는지 정량적 데이터(퍼널) 측정.
* 측정 ID: `G-DGLKCGVNEJ`

### 🛠️ 수집 이벤트 명세
1. **1단계 (웹 진입)**: `session_start`, `page_view` (GA4 기본 수집)
2. **2단계 (위치 권한 팝업)**: `click_location_consent` (`action: 'allow' | 'skip' | 'close'`)
3. **3단계 (GPS 승인/거부)**: `location_granted` (`accuracy_m`) / `location_denied` (`reason`)
4. **4단계 (쓰레기통 탐색)**: `select_trashcan` (`trash_id`, `trash_name`, `trash_type`)
5. **5단계 (자체 도보 내비 시작)**: `start_navigation` (`trash_id`, `initial_distance_m`)
6. **6단계 (외부 길찾기 모달)**: `open_nav_modal` (`trash_id`)
7. **7단계 (외부 앱 실행 - 최종 전환)**: `click_nav_app` (`app_name: 'kakaomap' | 'navermap' | 'googlemap'`)
8. **8단계 (목적지 도착)**: `arrive_destination` (`trash_id`, `trash_name`)

---

## 3. 실시간 위치 매핑 & 웹 자체 도보 내비게이션 (Real-Time Tracking & Navigation)

> [!NOTE]
> 📖 상세 기술 계획서 원본: [real_time_mapping_feature.md](file:///Users/woongyeol/trash_map/real_time_mapping_feature.md)

### 🎯 핵심 구현 기능
1. **실시간 위치 추적 (`watchPosition`) & 마커 애니메이션**:
   - `CustomOverlay.setPosition()`과 CSS `cubic-bezier(0.25, 1, 0.5, 1)` 트랜지션 결합으로 끊김 없는 부드러운 전진 구현.
   - `kakao.maps.Circle`을 활용한 GPS 정확도 오차 반경(Accuracy Ring) 시각화.
2. **스마트 화면 추종 (Lock-in 모드)**:
   - 보행 시 지도 중심이 사용자를 자동 추종(`map.panTo`).
   - 사용자가 지도를 터치/드래그하면 자동으로 자유 탐색 모드로 전환되며, 우하단 FAB 버튼 터치 시 즉시 추종 모드 복귀.
3. **상단 Glassmorphism 내비게이션 HUD**:
   - `길찾기` 클릭 시 카카오 레벨 2(도보 30m) 밀착 줌 전환.
   - 목적지까지의 남은 거리(m), 도보 소요 시간, 가이드 폴리라인 실시간 단축.
4. **실내/Wi-Fi 측위 예외 처리 (First Fix 보장)**:
   - 맥북(사파리) 및 실내 카페 환경에서 초기 수신 오차(100~300m)가 발생해도 기본 위치(서울시청)에 갇히지 않고 실제 위치로 지도를 이동시키는 관용적 수신 처리.
5. **10m 이내 도착 감지 & 진동 피드백**:
   - 목적지 10m 이내 접근 시 스마트폰 햅틱 진동(`navigator.vibrate`)과 함께 도착 축하 팝업 표출.
6. **배터리 보호**:
   - Page Visibility API(`visibilitychange`)를 통해 브라우저 백그라운드 전환 시 GPS 스트림 일시 정지(`clearWatch`).
