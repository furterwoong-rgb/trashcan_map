# 쓱싹(SSEUK-SSAK) 기능 개발 실행 계획서 (howtodo.md)

`todo.md`에 작성된 7가지 요구사항을 기술적 난이도, 사용자 체감 효과, 구현 리스크를 고려하여 **가장 효율적인 3단계 로드맵**으로 정리한 상세 실행 계획입니다.

---

## 📌 전체 실행 로드맵 및 우선순위 요약

| 우선순위 | 작업 항목 | 작업 성격 | 예상 소요 | 기대 효과 | 상태 |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **P0 (완료)** | **1. 모바일 지도 해상도 고급화 (@2x Retina)** | 프론트엔드 UI | 10분 | 즉각적인 시각적 퀄리티/고급화 체감 | **완료 ✅** |
| **P0 (완료)** | **2. 퍼널 전환율 추적 (GA4 Custom Events)** | 데이터/통계 | 30분 | 유저들이 길찾기까지 얼마나 도달하는지 실시간 측정 | **완료 ✅** |
| **P1 (완료)**| **3. 실시간 위치 매핑 & 웹 도보 내비게이션** | 핵심 기능 | 2시간 | 실제 네이버지도처럼 내 위치가 실시간으로 따라옴 | **완료 ✅** |
| **P1 (핵심 고도화)**| **4. 위치 불안정 안내 가이드라인 모달** | UX/CS 대응 | 1시간 | "위치 안 맞아요" 불만 원천 차단 및 이탈 방지 | 대기 |
| **P2 (크라우드소싱)**| **5. 가득 찬 정도 간이 투표 & 신규 제보 받기** | 사용자 참여 | 2시간 | 서버 없이 구글시트/슬랙 연동으로 데이터 수집 시작 | 대기 |
| **P3 (AI 기능)**   | **6. Llama / Gemini Vision 기반 쓰레기통 AI 인증** | AI/백엔드 | 3~4시간 | 사진 판별을 통한 허위 제보 자동 필터링 | 대기 |

---

## 1. 모바일 지도 해상도 고급화 (Kakao Maps Web API HD 엔진 전환 - 완료 ✅)

<!-- 
  [공식 출처 레퍼런스]
  1. 카카오 지도 Web API 시작 가이드: https://apis.map.kakao.com/web/guide/
  2. 카카오 개발자 콘솔 (도메인 등록 및 앱키): https://developers.kakao.com/console/app
  3. 카카오 지도 고해상도(HD) 기본 지원 및 명세: https://apis.map.kakao.com/web/documentation/#disableHD
  4. 커스텀 오버레이(CustomOverlay) 공식 샘플: https://apis.map.kakao.com/web/sample/customOverlay1/
  5. 마커 클러스터러(MarkerClusterer) 공식 샘플: https://apis.map.kakao.com/web/sample/basicClusterer/
-->

### 🎯 왜 카카오 지도 API로 모바일 해상도 문제를 해결하는가?
* **고해상도(HD Retina) 기본 내장**:
  - 카카오 지도 Web API는 모바일 디바이스(아이폰 Super Retina, 갤럭시 AMOLED)의 픽셀 밀도(DPR)를 자동으로 감지하여 **HD급 고해상도 타일을 기본 타일로 서빙**합니다.
  - 별도의 화질 저하 없이 국내 도로명, 횡단보도, 건물 윤곽선이 벡터급 선명도로 렌더링됩니다.
  - *출처:* [Kakao 지도 Web API Docs - disableHD()](https://apis.map.kakao.com/web/documentation/#disableHD) (고해상도 기기에서 기본값으로 HD 타일 자동 활성화)

---

### 🛠️ 단계별 구체적 실행 계획

#### [Step 1] 카카오 개발자 콘솔 Web 플랫폼 도메인 등록 (필수 선행 조건)
* **목적**: 발급받은 JavaScript 키가 승인된 웹사이트에서만 작동하도록 도메인 화이트리스트 등록.
* **설정 경로**:
  1. [카카오 개발자 콘솔](https://developers.kakao.com/console/app) ➔ 내 애플리케이션 선택
  2. 좌측 메뉴 **[앱 설정] ➔ [플랫폼] ➔ [Web 플랫폼 등록]**
  3. **사이트 도메인(Site Domain)** 입력:
     - 로컬 테스트: `http://localhost:3000`
     - 실제 Vercel 배포 주소: `https://trashcan-map.vercel.app`
* *출처:* [카카오 지도 시작 가이드 - 플랫폼 등록](https://apis.map.kakao.com/web/guide/#loadstart)

#### [Step 2] HTML 내 카카오 지도 Web SDK 로드 스크립트 선언
* 기존 Leaflet CDN(`leaflet.css`, `leaflet.js`) 대신 카카오 지도 공식 SDK 삽입:
  ```html
  <!-- 
    카카오 지도 Web API v2 SDK (비동기 안전 로딩 및 클러스터러 라이브러리 포함)
    출처: https://apis.map.kakao.com/web/guide/#loadstart 
  -->
  <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey=발급받은_JAVASCRIPT_KEY&libraries=clusterer&autoload=false"></script>
  ```
  *(※ `autoload=false`를 주어 브라우저 렌더링 후 `kakao.maps.load()`를 통해 가장 안정적으로 초기화)*

#### [Step 3] 지도 컨테이너 초기화 및 HD 렌더링
* `index.html` 내 `initMap()` 함수를 카카오 지도 문법으로 전환:
  ```javascript
  /*
    출처: https://apis.map.kakao.com/web/sample/basicMap/
  */
  kakao.maps.load(() => {
    const container = document.getElementById('map');
    const options = {
      center: new kakao.maps.LatLng(userPos.lat, userPos.lng), // 중심 좌표
      level: 3 // 확대 레벨 (카카오는 숫자가 작을수록 확대, 3~4가 도보 최적)
    };
    map = new kakao.maps.Map(container, options);
    
    // 모바일 리사이즈 시 깨짐 방지
    window.addEventListener('resize', () => map.relayout());
  });
  ```

#### [Step 4] 커스텀 마커를 카카오 `CustomOverlay`로 1:1 전환
* 기존 Leaflet `L.divIcon`으로 만든 펄스 링(내 위치) 및 토스 스타일 쓰레기통 마커 DOM을 카카오의 `kakao.maps.CustomOverlay`로 완벽 호환:
  ```javascript
  /*
    출처: https://apis.map.kakao.com/web/sample/customOverlay1/
  */
  function renderUserMarker() {
    const content = `
      <div class="custom-pulse-marker">
        <div class="pulse-dot-container">
          <div class="pulse-ring"></div>
          <div class="pulse-core"></div>
        </div>
      </div>
    `;
    const userOverlay = new kakao.maps.CustomOverlay({
      position: new kakao.maps.LatLng(userPos.lat, userPos.lng),
      content: content,
      yAnchor: 0.5,
      zIndex: 1000
    });
    userOverlay.setMap(map);
  }
  ```

#### [Step 5] 6,000개 마커 대량 렌더링 최적화
* **방식 A (화면 영역 기반 렌더링 - 현재 쓱싹 방식)**:
  - `kakao.maps.event.addListener(map, 'idle', () => { ... })` 이벤트로 현재 화면 영역(`map.getBounds()`)에 들어오는 쓰레기통만 화면에 꽂아 60fps 유지.
  - *출처:* [카카오 이벤트 리스너 문서](https://apis.map.kakao.com/web/documentation/#event)
* **방식 B (공식 클러스터러 라이브러리)**:
  - 축소 시 숫자로 묶어주고 확대 시 개별 마커로 펼침.
  - *출처:* [카카오 지도 MarkerClusterer 샘플](https://apis.map.kakao.com/web/sample/basicClusterer/)

---

## 2. 퍼널 전환율 추적 (GA4 적용 완료 ✅)

### 🎯 목표
* 방문자가 들어와서 **[내 위치 허용] ➔ [쓰레기통 마커 클릭] ➔ [외부 길찾기 클릭]**까지 실제로 이어지는지 단계별 전환율을 숫자로 파악.

### 🛠️ 구현 내용 (완료 `bf55fe8`)
* 측정 ID: `G-DGLKCGVNEJ` 적용 완료
* **단계별 GA4 이벤트 매핑**:
  1. **1단계: 진입** ➔ GA4 자동 수집 (`session_start`, `page_view`)
  2. **2단계: 위치 허용 팝업 선택** ➔ `click_location_consent` (`action: 'allow' | 'skip' | 'close'`)
  3. **3단계: GPS 권한 승인/거부** ➔ `location_granted` (`accuracy_m`) / `location_denied` (`reason`)
  4. **4단계: 쓰레기통 마커/아이템 클릭** ➔ `select_trashcan` (`trash_id`, `trash_name`, `trash_type`)
  5. **5단계: 경로 점선 보기** ➔ `click_show_line` (`trash_id`)
  6. **6단계: 길찾기 모달 열기** ➔ `open_nav_modal` (`trash_id`)
  7. **7단계: 외부 지도앱 클릭 (최종 전환)** ➔ `click_nav_app` (`app_name: 'kakaomap' | 'navermap' | 'googlemap'`)
  8. **기타 탐색 이벤트** ➔ `change_filter`, `click_recenter`, `click_refresh_location`

### 📊 GA4 탐색 보고서에서 퍼널 보는 법
* 구글 애널리틱스 좌측 메뉴: **[탐색(Explore)] ➔ [유입경로 탐색 분석(Funnel Exploration)]** 선택
* 단계(Steps) 추가:
  - Step 1: `session_start` (웹 진입)
  - Step 2: `location_granted` (내 위치 허용 완료)
  - Step 3: `select_trashcan` (쓰레기통 클릭)
  - Step 4: `click_nav_app` (길찾기 앱 클릭 - 최종 전환)
* ➔ 단계별 이탈률과 전환율 막대그래프를 즉시 확인할 수 있습니다.

---

## 3. 실시간 위치 매핑 및 웹 자체 도보 내비게이션 (완료 ✅)

> [!NOTE]
> 📖 **상세 기술 설계 및 카카오 공식 API 기반 실행 계획서**: [real_time_mapping_feature.md](file:///Users/woongyeol/trash_map/real_time_mapping_feature.md)를 반드시 참고하세요.
> 카카오 지도 공식 Web API 문서 기반의 `CustomOverlay.setPosition`, `Map.panTo`, `Polyline.setPath`, `Circle(정확도 반경)`, GPS Jitter 방지 알고리즘 및 추종 모드(Lock-in) 상태 머신이 구체적으로 설계되어 있습니다.

### 🎯 목표
* 사용자가 길거리를 걸어갈 때 내 위치(파란 원)가 부드럽게 실시간으로 따라오고, 쓰레기통과의 남은 거리가 실시간으로 갱신되도록 개선.

### 🛠️ 구현 방법
1. **`watchPosition` 도입**:
   - 기존 1회성 `getCurrentPosition` 대신 `navigator.geolocation.watchPosition` 적용.
   - GPS 튐(Jitter) 방지: 오차 반경(`coords.accuracy`)이 30m 이하인 신뢰할 수 있는 좌표만 반영.
2. **마커 애니메이션**:
   - 순간이동하지 않고 부드럽게 이동하도록 CSS Transition(`transition: transform 0.3s ease`) 또는 Leaflet 부드러운 좌표 갱신 함수 구현.
3. **지도 추적 모드 분리 (UX 필수)**:
   - **추적 켜짐 모드**: 내가 걸어가면 지도 중심이 내 위치를 계속 따라감.
   - **자유 탐색 모드**: 사용자가 지도를 손으로 쓸어 넘기면(드래그) 자동 추적이 풀리고 원하는 곳을 자유롭게 둘러볼 수 있게 전환.
   - 우하단에 [내 위치로 화면 맞추기] 플로팅 버튼을 두어 원터치로 추적 모드 재활성화.
4. **배터리 최적화**:
   - `document.addEventListener('visibilitychange', ...)`를 감지하여 유저가 화면을 끄거나 다른 앱으로 넘어가면 GPS 추적을 일시 정지(`clearWatch`)하여 배터리 방전 방지.

---

## 4. 위치 불안정 제보 대응 (안드로이드/아이폰 가이드 모달)

### 🎯 문제 원인
* **아이폰**: 설정 > 사파리/에타 > 위치에서 **'정확한 위치' 토글이 꺼져 있으면** 반경 500m~1km 오차가 발생함.
* **인앱 브라우저**: 에브리타임/카톡/인스타 내부 브라우저는 OS 보안상 정밀 GPS를 가끔 차단하거나 캐시된 엉뚱한 위치를 줌.

### 🛠️ 구현 방법
1. **정확도 이상 감지 로직**:
   - GPS 수신 결과 `coords.accuracy > 50` (오차가 50m 이상)이거나 위치 권한이 거부된 경우:
   - 화면 상단에 경고 배너 표시: *"⚠️ 위치가 부정확합니다 (오차 약 XXm) [정확하게 맞추기]"*
2. **OS별 안내 바텀시트 모달**:
   - **아이폰 탭**: `설정 > 개인정보 보호 > 위치 서비스 > Safari(또는 에브리타임) > '정확한 위치' 켜기`
   - **안드로이드 탭**: `설정 > 위치 > 위치 정확도 개선 켜기`
   - **인앱 브라우저 탈출 버튼**: 상단에 *"더 정확한 위치를 위해 사파리/크롬으로 열기"* 버튼 제공 (`kakaotalk://web/openExternal?url=...` 등).

---

## 5. 쓰레기통 상태 확인 (여유/가득참) & 신규 위치 제보

### 🎯 현실적인 2단계 접근법

#### [Step 1: 간이 1초 피드백 (서버 불필요, 즉시 도입)]
* 쓰레기통 상세 바텀시트 하단에 **"현재 쓰레기통 상태는?"** 버튼 배치:
  - 🟢 여유로움 | 🟡 보통 | 🔴 꽉 참 | ❌ 없어짐
* 사용자가 누르면 로컬 스토리지(`localStorage`) 또는 무료 클라우드 DB(Supabase / Firebase 무료 플랜)에 1초 만에 저장.
* 가장 최근 제보 상태를 마커 팝업에 *"10분 전: 여유로움"* 형태로 표시.

#### [Step 2: 신규 쓰레기통 제보하기]
* 지도 우하단에 `[+ 쓰레기통 제보]` 버튼 추가.
* 현재 내 위치 좌표 자동 입력 + 사진 1장 첨부 + 분류(일반/재활용/담배).
* 전송처: 무료 **Google Sheets API(Apps Script)** 또는 **개발자 텔레그램 봇**으로 즉시 알림 전송 ➔ 검토 후 `seoul_trash_data.json`에 반영.

---

## 6. AI Vision 기반 사진 분석 (Llama 3.2 Vision / Gemini Flash)

### 🎯 구현 방식
사용자가 찍은 사진이 "진짜 길거리 쓰레기통인지" 그리고 "가득 찼는지"를 AI로 자동 판별하여 허위 제보를 거르는 시스템.

### 🛠️ 기술 아키텍처
1. **보안을 위한 서버리스 함수 (API 키 보호)**:
   - 클라이언트(브라우저)에서 AI API를 직접 호출하면 API 키가 유출되므로, **Vercel Serverless Function (`/api/verify-trash.js`)**에서 호출.
2. **모델 추천**:
   - **Gemini 2.0 Flash / 1.5 Flash** 또는 **Llama 3.2 Vision (Groq)**
   - 이유: 1장 분석에 **0.5초**밖에 안 걸리고, 비용이 사실상 무료 수준(Free tier 수천 건/월).
3. **구조화된 출력(JSON Prompt)**:
   ```json
   {
     "is_trashcan": true,
     "fullness": "full", // "empty" | "normal" | "full"
     "confidence": 0.95
   }
   ```
4. **클라이언트 이미지 압축 (필수)**:
   - 모바일 카메라 원본 사진(5MB~10MB)을 그대로 올리면 업로드가 느려지고 비용 발생.
   - 브라우저 Canvas API를 통해 **가로 800px, 용량 200KB 내외로 즉시 압축**한 뒤 전송.

---

## 📋 추천 작업 순서

1. **1차 작업 (내일 오전 추천)**:
   - `index.html` 지도 타일에 `@2x Retina` 옵션 적용 (화질 대폭 개선)
   - Vercel Custom Event 적용 (퍼널 통계 측정 시작)
2. **2차 작업 (내일 오후 추천)**:
   - `watchPosition` 실시간 트래킹 모드 구현
   - 위치 정확도 안내 모달 추가
3. **3차 작업 (차주 진행)**:
   - 간이 상태 피드백 (여유/가득참) 및 신규 제보 폼 연동
   - AI 사진 분석 API 연결
