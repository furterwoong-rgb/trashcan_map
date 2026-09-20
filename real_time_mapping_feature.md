# 쓱싹(SSEUK-SSAK) 실시간 위치 매핑 기능 실행 계획서 (real_time_mapping_feature.md)

이 문서는 사용자가 길거리를 이동할 때 내 위치 마커가 실시간으로 부드럽게 따라오고, 쓰레기통과의 남은 거리와 길안내 점선이 실시간으로 갱신되는 **진짜 지도앱 스타일의 실시간 위치 매핑(Real-Time Location Tracking / Lock-in)** 기능의 상세 기술 설계 및 실행 계획입니다.

---

## 📌 공식 카카오 지도 Web API 기술 레퍼런스

본 계획서의 모든 지도 제어 로직은 **카카오 지도 Web API 공식 문서 및 공식 샘플**에 명시된 정식 API 메서드만을 기반으로 설계되었습니다.

1. **카카오 지도 Geolocation 공식 샘플**:
   * 링크: [https://apis.map.kakao.com/web/sample/geolocationMarker/](https://apis.map.kakao.com/web/sample/geolocationMarker/)
   * 핵심 내용: HTML5 Geolocation API 연동 및 좌표 획득, 지도 중심 및 마커 위치 제어.
2. **`kakao.maps.CustomOverlay.setPosition(position)`**:
   * 링크: [https://apis.map.kakao.com/web/documentation/#CustomOverlay_setPosition](https://apis.map.kakao.com/web/documentation/#CustomOverlay_setPosition)
   * 핵심 내용: 마커를 매번 삭제하고 새로 생성하는 비용 없이, 기존 `CustomOverlay`의 좌표를 즉시 이동시킴 (`O(1)` 최적화).
3. **`kakao.maps.Map.panTo(latlng)`**:
   * 링크: [https://apis.map.kakao.com/web/documentation/#Map_panTo](https://apis.map.kakao.com/web/documentation/#Map_panTo)
   * 핵심 내용: 지도의 중심 좌표를 부드러운 애니메이션 효과와 함께 이동.
4. **`kakao.maps.Polyline.setPath(path)`**:
   * 링크: [https://apis.map.kakao.com/web/documentation/#Polyline_setPath](https://apis.map.kakao.com/web/documentation/#Polyline_setPath)
   * 핵심 내용: 기존 폴리라인 객체를 재생성하지 않고 선분의 정점 배열(`LatLng[]`)을 실시간 재설정.
5. **`kakao.maps.Circle.setPosition(position)` & `setRadius(radius)`**:
   * 링크: [https://apis.map.kakao.com/web/documentation/#Circle](https://apis.map.kakao.com/web/documentation/#Circle)
   * 핵심 내용: GPS 수신 정확도 오차 반경(`coords.accuracy`)을 지도 위에 반투명 원으로 표현 및 실시간 갱신.
6. **카카오 지도 `dragstart` 이벤트 리스너**:
   * 링크: [https://apis.map.kakao.com/web/documentation/#Map_Events](https://apis.map.kakao.com/web/documentation/#Map_Events)
   * 핵심 내용: 사용자의 지도 터치/드래그 시점을 감지하여 자동 화면 추종(Lock-in)을 자연스럽게 일시 해제.

---

## 🎯 기능 개발 핵심 목표

1. **진짜 지도앱 같은 Lock-in 경험**: 사용자가 걸어갈 때 내 위치 펄스 마커가 부드럽게 전진하고, 지도가 내 위치를 중심으로 따라감.
2. **실시간 정보 갱신**: 보행에 따라 바텀 시트의 남은 거리(`42m 도보 1분` ➔ `35m` ➔ `20m`), 직선 안내선(`Polyline`)이 실시간 동기화.
3. **지능형 사용자 UX (추종 모드 vs 자유 탐색 모드)**:
   * 지도를 보고 걸을 때는 **내 위치 자동 추종 (Lock-in ON)**.
   * 사용자가 다른 곳을 둘러보려고 지도를 드래그하면 **자유 탐색 모드 (Lock-in OFF)**로 자동 전환.
   * 우하단 [내 위치 버튼]을 누르면 즉시 **추종 모드 복귀**.
4. **배터리 방전 방지 및 GPS 튐(Jitter) 억제**: 실내나 빌딩 숲에서 발생하는 GPS 오차를 필터링하고 백그라운드 전환 시 추적 일시 정지.

---

## 🛠️ 상세 아키텍처 및 4단계 구현 계획

### [Step 1] `navigator.geolocation.watchPosition` 스트림 도입 및 수명 주기 관리

* **현재 상태**: 1회성 `getCurrentPosition`만 호출하여 초기 위치만 멈춰 있음.
* **개선 방식**:
  ```javascript
  let watchId = null;
  let isTrackingLocked = true; // 화면 추종 활성화 여부

  function startLiveLocationTracking() {
    if (!navigator.geolocation) return;

    if (watchId !== null) {
      navigator.geolocation.clearWatch(watchId);
    }

    const options = {
      enableHighAccuracy: true, // GPS 위성 수신 최대화
      timeout: 10000,           // 10초 타임아웃
      maximumAge: 0             // 캐시된 이전 좌표 사용 금지
    };

    watchId = navigator.geolocation.watchPosition(
      onLocationSuccess,
      onLocationError,
      options
    );
  }
  ```
* **배터리 보호 (Lifecycle Management)**:
  - 브라우저의 Page Visibility API(`document.addEventListener('visibilitychange')`) 연동:
    * 유저가 화면을 끄거나 다른 앱으로 전환 시: `navigator.geolocation.clearWatch(watchId); watchId = null;`
    * 다시 웹 화면으로 복귀 시: `startLiveLocationTracking()` 즉시 재가동.

---

### [Step 2] GPS 튐(Jitter) 방지 및 거리 임계값(Threshold) 필터링

스마트폰 GPS는 가만히 있어도 1~2m씩 흔들리거나, 건물 실내에서 갑자기 수십 미터 튀는 현상이 있습니다. 이를 방지하는 정밀 필터 알고리즘을 도입합니다.

```javascript
let lastProcessedPos = null;
const MIN_ACCURACY_METERS = 40; // 40m 이상 부정확한 오차는 마커 이동 보류
const MIN_MOVE_DISTANCE_METERS = 2; // 최소 2m 이상 실제 이동했을 때만 지도/경로 갱신

function onLocationSuccess(position) {
  const { latitude, longitude, accuracy } = position.coords;

  // 1. 심각한 GPS 오차 필터링
  if (accuracy > MIN_ACCURACY_METERS) {
    console.warn(`[쓱싹] GPS 정확도 부족 (오차 반경: ${Math.round(accuracy)}m)`);
    updateAccuracyCircle(latitude, longitude, accuracy); // 오차 원만 갱신하고 마커 점프 방지
    return;
  }

  // 2. 미세한 떨림 방지 (2m 미만 이동 무시)
  if (lastProcessedPos) {
    const movedDist = calculateDistance(lastProcessedPos.lat, lastProcessedPos.lng, latitude, longitude);
    if (movedDist < MIN_MOVE_DISTANCE_METERS) {
      return; // 불필요한 렌더링 스킵
    }
  }

  lastProcessedPos = { lat: latitude, lng: longitude };
  userPos = { lat: latitude, lng: longitude };

  // 3. 카카오 지도 실시간 갱신 실행
  updateLiveComponents(latitude, longitude, accuracy);
}
```

---

### [Step 3] 카카오 지도 공식 API 메서드를 활용한 실시간 화면 동기화

마커를 매번 지우고 다시 만들면 화면이 깜빡이고 브라우저 성능이 급격히 떨어집니다. 카카오 지도의 고성능 전용 메서드를 사용합니다.

#### 1. 내 위치 펄스 마커 이동 (`CustomOverlay.setPosition`)
* 출처: [Kakao CustomOverlay setPosition API](https://apis.map.kakao.com/web/documentation/#CustomOverlay_setPosition)
```javascript
const newLatLng = new kakao.maps.LatLng(latitude, longitude);
if (userOverlay) {
  userOverlay.setPosition(newLatLng); // 깜빡임 없이 즉시 좌표 갱신
}
```

#### 2. GPS 오차 반경 원 표시 (`kakao.maps.Circle`)
* 출처: [Kakao Circle API](https://apis.map.kakao.com/web/documentation/#Circle)
* 네이버/카카오 지도 공식 앱처럼 내 위치 주변에 옅은 파란색 반투명 원을 표시하여 신뢰도 제공:
```javascript
let accuracyCircle = null;

function updateAccuracyCircle(lat, lng, accuracy) {
  const pos = new kakao.maps.LatLng(lat, lng);
  if (!accuracyCircle) {
    accuracyCircle = new kakao.maps.Circle({
      map: map,
      center: pos,
      radius: accuracy,
      strokeWeight: 1,
      strokeColor: '#3182F6',
      strokeOpacity: 0.4,
      fillColor: '#3182F6',
      fillOpacity: 0.08
    });
  } else {
    accuracyCircle.setPosition(pos);
    accuracyCircle.setRadius(accuracy);
  }
}
```

#### 3. 지도 중심 부드러운 패닝 (`Map.panTo`)
* 출처: [Kakao Map panTo API](https://apis.map.kakao.com/web/documentation/#Map_panTo)
* 사용자가 자유 탐색 중이 아닐 때만(`isTrackingLocked === true`) 지도 중심을 자동으로 따라오게 함:
```javascript
if (isTrackingLocked && map) {
  map.panTo(newLatLng);
}
```

#### 4. 길안내 점선 실시간 재연결 (`Polyline.setPath`)
* 출처: [Kakao Polyline setPath API](https://apis.map.kakao.com/web/documentation/#Polyline_setPath)
```javascript
if (guidePolyline && selectedTrash) {
  const newPath = [
    new kakao.maps.LatLng(latitude, longitude),
    new kakao.maps.LatLng(selectedTrash.lat, selectedTrash.lng)
  ];
  guidePolyline.setPath(newPath); // 가이드라인이 내 발걸음에 맞춰 실시간으로 줄어듦
}
```

#### 5. 바텀 시트 실시간 거리/도보시간 재계산
* 사용자가 걸어가면 `42m 도보 1분` 숫자가 실시간으로 감소:
```javascript
if (selectedTrash) {
  const dist = calculateDistance(latitude, longitude, selectedTrash.lat, selectedTrash.lng);
  selectedTrash.distance = dist;
  document.getElementById('sheet-distance').textContent = formatDistance(dist);
  document.getElementById('sheet-walk-time').textContent = calculateWalkTime(dist);
}
```

---

### [Step 4] 사용자 인터랙션 UX 설계 (Lock-in 상태 머신)

* **이벤트 감지**:
  1. **지도 드래그 시 (`dragstart`)**:
     * 사용자가 손가락으로 지도를 움직이면 즉시 `isTrackingLocked = false;`로 전환.
     * 우측 하단 [내 위치 버튼(`btn-recenter`)]의 아이콘 스타일을 비활성(회색) 상태로 변경하여 "현재 자유 탐색 중"임을 시각적으로 안내.
  2. **내 위치 버튼 클릭 시 (`btn-recenter`)**:
     * `isTrackingLocked = true;`로 복구.
     * `map.panTo(new kakao.maps.LatLng(userPos.lat, userPos.lng));` 실행.
     * 버튼을 활성(파란색 토스 블루) 스타일로 하이라이트.
* **마커 CSS 부드러운 이동 효과 (Smooth Transition)**:
  - `.custom-pulse-marker`에 CSS 속성을 부여하여 좌표 이동 시 순간이동하지 않고 미끄러지듯 이동:
  ```css
  .custom-pulse-marker {
    transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1);
  }
  ```

---

## 📊 수정 영향 범위 (Scope of Modification)

* **대상 파일**: `index.html` (프론트엔드 단일 파일)
* **영향받는 기존 함수**:
  - `requestLocation()`: 1회성 `getCurrentPosition` 대신 `startLiveLocationTracking()` 호출로 고도화
  - `setupEventListeners()`: `kakao.maps.event.addListener(map, 'dragstart', ...)` 리스너 추가
  - `renderUserMarker()`: `accuracyCircle` 연동 및 `userOverlay.setPosition` 유지
* **기존 데이터 및 이벤트 보존**:
  - GA4 퍼널 측정 이벤트(`location_granted`, `select_trashcan` 등) 100% 정상 작동 유지
  - 외부 길찾기 링크(카카오맵 도보 길찾기 URL 등) 실시간 좌표 동기화 유지

---

## 🧪 검증 및 테스트 계획 (Verification Plan)

1. **데스크톱 사파리/크롬 가상 센서 시뮬레이션**:
   * 개발자 도구 ➔ [Sensors(센서)] ➔ [Location] ➔ [Walk] 프리셋 설정으로 가상 보행 테스트.
   * 내 위치 마커가 경로를 따라 자동으로 움직이고, 지도 중심(`panTo`)과 가이드라인(`setPath`)이 부드럽게 추종하는지 확인.
2. **지도 드래그 시 Lock-in 해제 테스트**:
   * 시뮬레이션 중 지도를 손으로 드래그했을 때 지도가 튕기지 않고 드래그한 위치에 그대로 머무는지(자유 탐색) 확인.
   * `btn-recenter` 버튼 클릭 시 즉시 내 위치로 화면이 빨려 들어가며 Lock-in이 재개되는지 확인.
3. **모바일 실제 디바이스(iOS/Android) 실외 테스트**:
   * 실제 10~20m 걸으며 바텀 시트의 거리가 실시간으로 `40m -> 30m -> 20m`로 줄어드는지 체감 테스트.
   * 백그라운드 전환(홈 화면 이동) 후 복귀 시 배터리/GPS 정상 재개 여부 확인.

---

## 🚀 [Phase 2 고도화 계획] 실제 인도 및 횡단보도 기반 도보 길안내 (Pedestrian Routing)

### 1. 사용자 피드백 배경 및 핵심 문제점
* **기존 방식의 한계 (직선 경로 & 유클리드 거리)**:
  - 현재는 사용자와 쓰레기통 간의 **직선(Air-distance)**을 점선 폴리라인으로 표시하고 거리를 계산함.
  - 도심 골목길이나 안암동 참살이길처럼 건물이 가로막혀 있거나 횡단보도를 건너야 하는 구간에서 **"건물을 뚫고 지나가는 선"**이 표시되어 실제 보행자가 걷는 체감과 괴리가 발생함.
* **개선 목표**:
  - 카카오맵/네비게이션 앱처럼 **실제 보행 가능한 인도, 골목길, 횡단보도를 꺾어 들어가는 정밀한 보행자 경로선**을 지도에 렌더링.
  - 직선거리가 아닌 **실제 걸어야 하는 보행 거리(m)**와 **예상 보행 시간(분)**을 HUD에 노출.

---

### 2. 카카오맵 API 도보 길안내 지원 여부 기술 검토 (Fact Check)

| 구분 | 카카오맵 Javascript SDK (웹용) | 카카오맵 / 모빌리티 REST API |
| :--- | :--- | :--- |
| **지원 여부** | ❌ **직접 지원 안 됨** | ⭕ **지원됨 (REST API 제공)** |
| **상세 내용** | 지도 타일 렌더링, 마커, 오버레이, 폴리라인(`Polyline`), 주소/장소 검색만 제공.<br>도보 경로 알고리즘/메서드는 SDK 내에 내장되어 있지 않음. | `GET https://dapi.kakao.com/v2/routing/walk` 또는 카카오모빌리티 도보 길찾기 API로 출발지/목적지 좌표를 보내면 실제 인도/횡단보도 경유 좌표 배열 반환. |
| **무료 쿼터** | 일 30만 건 (지도 렌더링) | **일 1,000건 무료** (초과 시 유료 또는 제한) |
| **호출 방식** | 브라우저 클라이언트 JS | 서버 사이드 (REST API Key 필요) |

> ⚠️ **핵심 기술적 주의점 (보안 & CORS)**:
> - 카카오 REST API는 요청 헤더에 `Authorization: KakaoAK {REST_API_KEY}`를 실어 보내야 합니다.
> - 클라이언트 브라우저(`index.html`)에서 직접 카카오 REST API를 호출하면 **(1) 비밀 REST API 키가 외부에 탈취**되고, **(2) 브라우저 CORS 정책으로 호출이 차단**될 수 있습니다.
> - 따라서 **Vercel Serverless Function (`/api/pedestrian-route.js`)을 프록시(BFF 패턴)로 두는 아키텍처**가 필수적입니다.

---

### 3. 기술 대안 비교 (카카오 vs TMAP)

| 비교 항목 | 1안: 카카오맵 도보 REST API (추천) | 2안: TMAP 보행자 경로 API | 3안: OpenStreetMap (OSRM) |
| :--- | :--- | :--- | :--- |
| **무료 쿼터** | 일 1,000건 무료 | 일 1,000건 무료 | 완전 무료 (오픈소스) |
| **국내 인도/골목 정확도**| ⭐⭐⭐⭐ (카카오맵 데이터와 일치) | ⭐⭐⭐⭐⭐ (국내 보행자 내비 원조) | ⭐⭐ (한국 골목/횡단보도 유실 많음) |
| **연동 복잡도** | 카카오 개발자 콘솔에서 키 하나로 통일 가능 | SK Open API 별도 가입 및 키 발급 필요 | 자체 서버 구축 필요 |
| **결론** | **1순위로 카카오 도보 REST API 채택.** 일일 1,000회는 현재 트래픽(일 100회 미만)에서 충분함. |

---

### 4. 아키텍처 및 구현 설계 (Implementation Architecture)

```mermaid
sequenceDiagram
    autonumber
    actor User as 사용자 (모바일 웹)
    participant Client as 쓱싹 프론트엔드 (index.html)
    participant Server as Vercel Serverless (/api/route)
    participant Kakao as 카카오 도보 길찾기 REST API

    User->>Client: 쓰레기통 선택 후 [길찾기] 클릭
    Client->>Client: 즉시 직선 가이드라인 임시 렌더링 (체감 대기시간 0초)
    Client->>Server: GET /api/pedestrian-route?origin=경도,위도&dest=경도,위도
    Server->>Kakao: GET /v2/routing/walk (with KAKAO_REST_API_KEY)
    Kakao--Server: 횡단보도/인도 경유 좌표 목록, 실제 도보거리, 시간 반환
    Server-->>Client: JSON { status: "OK", distance: 240, duration: 210, path: [...] }
    Client->>Client: guideLine.setPath(path)로 실제 인도 경로선으로 교체!
    Client->>Client: HUD에 "실제 도보 240m (약 3분)" 표시
```

#### ① 백엔드: Vercel Serverless Function (`/api/pedestrian-route.js`)
* **역할**: 클라이언트의 요청을 받아 카카오 도보 API를 호출하고 좌표 데이터만 가공하여 응답.
* **보안**: `process.env.KAKAO_REST_API_KEY`를 Vercel 환경 변수로 안전하게 은닉.
* **캐싱 (성능 & 쿼터 절약)**:
  - 1,000건 쿼터를 아끼기 위해 동일한 출발지/목적지 요청은 1시간 동안 브라우저/Vercel 엣지 캐시(`Cache-Control: s-maxage=3600`) 적용.

#### ② 프론트엔드: 체감 성능 최적화 (Optimistic UI)
* 사용자가 [길찾기]를 누르는 즉시:
  1. **0.01초 만에**: 기존의 직선 점선을 먼저 화면에 띄워 대기 시간 지루함 제거.
  2. **0.2초 후**: `/api/pedestrian-route` 응답이 오면 직선 점선을 **꺾인 인도/횡단보도 상세 폴리라인**으로 자연스럽게 교체.
  3. 상단 HUD의 거리를 유클리드 직선거리(예: 170m)에서 **실제 도보거리(예: 240m)**로 갱신.

#### ③ API 쿼터 절약 및 GPS 이동 추종 로직 (Smart Re-routing)
* 사용자가 걸어갈 때마다 매초 REST API를 호출하면 1,000건 쿼터가 순식간에 소진됨.
* **해결책**:
  - 이미 받아온 상세 경로 좌표들(`pathCoordinates`)을 메모리에 보관.
  - 사용자가 이동할 때 내 위치와 가장 가까운 경로 점을 찾아 **지나온 구간만 잘라내고(Polyline Trim), 남은 앞부분만 계속 표시**.
  - 만약 사용자가 원래 안내된 경로에서 **50m 이상 벗어난 경우(Off-track)**에만 새로운 경로를 재요청(Re-routing).

#### ④ 안전 장치 (Fallback Strategy)
* 만약 카카오 일 1,000건 쿼터가 소진되거나 네트워크 오류가 발생할 경우:
  - 에러 팝업 없이 **기존의 부드러운 직선 안내선으로 자동 Fallback**.
  - 서비스가 절대 중단되지 않도록 무결성 보장.

---

### 5. 실행 로드맵 (Execution Checklist)

- [x] **Step 1**: SK Open API(openapi.sk.com) TMAP 상품(무료 1,000건/일) 활성화 및 AppKey 검증 완료 (`iK60UGHNRY4v9vNaGNgMz3B4H8zWKyQi70J0FzDL`).
- [x] **Step 2**: Vercel Serverless Function (`api/pedestrian-route.js`) 구축 (TMAP 보행자 경로 API 연동, 36개 횡단보도/인도 상세 좌표 및 소요시간 파싱 완료).
- [x] **Step 3**: `index.html` 프론트엔드 연동 (Optimistic UI 0초 직선 ➔ 0.2초 정밀 도보 경로선 교체, 도보 거리/시간 HUD 노출, 실시간 Polyline Trim 및 경로 이탈 스마트 재탐색).
- [x] **Step 4**: 무중단 Fallback 장치 구축 (API 쿼터 소진 또는 에러 시 부드러운 직선 안내선 유지).
- [ ] **Step 5**: Vercel 배포 및 안암역 ~ 참살이길 실제 도보 필드 테스트.


