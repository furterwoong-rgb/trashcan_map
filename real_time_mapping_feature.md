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
