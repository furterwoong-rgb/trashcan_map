# 다국어 자동 전환 시스템 (Automatic Language Translation / i18n) 실행 계획

## 1. 개요 및 기획 배경

### 1.1 배경 및 목적
* **외국인 관광객의 페인 포인트(Pain Point) 해결**: 서울을 방문하는 해외 관광객들이 가장 크게 겪는 문화 충격 1위는 "길거리에 쓰레기통이 없다"는 점입니다.
* **글로벌 바이럴 및 확장성 확보**: 레딧(Reddit `r/korea`), 틱톡, 인스타그램 등 글로벌 채널에서 외래 관광객 타겟으로 자연 바이럴을 유도하고, 관광공사/지자체 공모전 등에서 공공 혁신성을 인정받기 위함입니다.
* **자동 감지(Zero-Click)**: 외국인이 링크를 누르고 들어왔을 때 별도로 설정 버튼을 찾을 필요 없이, **스마트폰의 시스템 언어를 감지하여 0.1초 만에 영어로 자동 렌더링**됩니다.
* **수동 스위칭 보장**: 사용자가 원할 때 언제든 `[KO / EN]` 버튼을 눌러 언어를 즉시 전환할 수 있습니다.

---

## 2. 언어 감지 및 설정 유지 메커니즘 (Detection & Persistence)

### 2.1 언어 감지 우선순위 (Resolution Flow)
```mermaid
flowchart TD
    A[페이지 접속] --> B{localStorage에<br/>저장된 언어 설정이 있는가?}
    B -- 있음 (수동 선택 기록) --> C[해당 언어 적용 (ko / en)]
    B -- 없음 (최초 방문) --> D{navigator.language<br/>한국어(ko)인가?}
    D -- ko, ko-KR --> E[한국어 (ko) 자동 적용]
    D -- 그 외 (en, ja, zh, fr, es 등) --> F[영어 (en) 자동 적용]
    C --> G[UI 텍스트 및 동적 메시지 렌더링]
    E --> G
    F --> G
```

1. **1순위 (사용자 명시적 선택)**: `localStorage.getItem('trashmap_lang')`
   * 사용자가 과거에 상단 토글 버튼을 직접 눌러 언어를 바꾼 적이 있다면, 그 설정을 최우선으로 존중합니다.
2. **2순위 (시스템 언어 자동 감지)**: `navigator.language || navigator.userLanguage`
   * 언어 코드가 `ko`로 시작하는 경우 (`ko`, `ko-KR` 등) 👉 **한국어 (`ko`)**
   * 그 외의 모든 언어 (`en-US`, `en-GB`, `ja`, `zh-CN`, `fr` 등) 👉 **영어 (`en`)** 자동 설정

---

## 3. i18n 다국어 사전 설계 (Translation Dictionary)

### 3.1 정적 UI 텍스트 (Static Elements)

| 식별자 (Key) | 한국어 (KO) | 영어 (EN) | 설명 / 위치 |
| :--- | :--- | :--- | :--- |
| `app_name` | 쓱싹 | SseukSsak | 로고 텍스트 |
| `app_subtitle` | 내 주변 쓰레기통 | Seoul Trash Bins | 헤더 서브타이틀 배지 |
| `filter_all` | 전체 | All | 필터 칩 1 |
| `filter_recycle` | 일반·재활용 | General / Recycle | 필터 칩 2 |
| `filter_cigarette` | 담배꽁초 | Cigarette Bins | 필터 칩 3 |
| `btn_refresh_title` | 내 위치 다시 찾기 | Refresh Location | 상단 새로고침 툴팁 |
| `btn_recenter_title`| 내 위치로 이동 | Recenter My Location | 플로팅 위치 버튼 툴팁 |
| `sheet_badge_closest`| 가장 가까운 곳 | Nearest Bin | 바텀시트 배지 (최단거리) |
| `sheet_badge_selected`| 선택한 곳 | Selected Bin | 바텀시트 배지 (직접선택) |
| `sheet_title_searching`| 가까운 쓰레기통 탐색 중... | Finding nearest trash bin... | 바텀시트 로딩 타이틀 |
| `sheet_desc_searching` | 위치 정보를 기반으로 가장 가까운 곳을 안내합니다. | Navigating to the closest street bin. | 바텀시트 설명 문구 |
| `btn_start_nav` | 길찾기 | Start Route | 길안내 시작 버튼 |
| `btn_stop_nav` | 안내 종료 | End Route | 길안내 종료 버튼 |
| `btn_other_maps` | 다른 앱으로 길찾기 | Open in Map App | 외부 지도 연결 버튼 |

### 3.2 팝업 모달 텍스트 (Modals)

| 모달 | 식별자 (Key) | 한국어 (KO) | 영어 (EN) |
| :--- | :--- | :--- | :--- |
| **도착 알림<br/>(Arrival Modal)** | `modal_arrival_title` | 목적지 주변에 도착했습니다! | You have arrived near the bin! |
| | `modal_arrival_desc` | 10m 이내에 쓰레기통이 위치해 있습니다.<br/>주변 인도나 가로등 근처를 둘러보세요. | The bin is within 10m.<br/>Look around near street lamps or sidewalk. |
| | `modal_arrival_confirm` | 확인 (길안내 완료) | Done (Finish Route) |
| **위치 권한<br/>(Location Modal)**| `modal_loc_title` | 내 주변 쓰레기통을 찾을까요? | Find street bins near you? |
| | `modal_loc_desc` | 현재 계신 위치를 기준으로 가장 가까운 쓰레기통까지의 거리와 도보 길안내를 제공해 드립니다. | We find the nearest street trash bins based on your current location with walking directions. |
| | `modal_loc_allow` | 📍 내 위치로 찾기 (허용) | 📍 Find with My Location (Allow) |
| | `modal_loc_skip` | 기본 위치로 둘러보기 | Browse Seoul Default View |
| **외부 지도<br/>(Nav Modal)** | `modal_map_title` | 도보 길찾기 앱 선택 | Select Navigation Map |
| | `modal_map_desc` | 선택하신 앱으로 목적지까지의 도보 길찾기 화면을 바로 열어드립니다. | Open walking directions to the destination in your preferred map app. |
| | `modal_map_kakao` | 카카오맵으로 길찾기 | KakaoMap Walking Directions |
| | `modal_map_naver` | 네이버 지도로 길찾기 | Naver Map Walking Directions |
| | `modal_map_google` | 구글 지도로 길찾기 | Google Maps (Overview) |
| | `modal_map_google_sub`| 국내 법률상 도보 미지원(대중교통/위치) | Walking route limited in Korea (Public Transit/Location) |

### 3.3 동적 런타임 텍스트 (Dynamic Formatter)

| 상황 | 한국어 템플릿 (KO) | 영어 템플릿 (EN) |
| :--- | :--- | :--- |
| **GPS 탐색 중** | `GPS 위치 파악 중...` | `Locating your GPS...` |
| **GPS 연결 중** | `📍 실시간 GPS 연결 중...` | `📍 Connecting to live GPS...` |
| **GPS 추적 중** | `📍 실시간 위치 추적 중` | `📍 Live GPS Tracking Active` |
| **위치 권한 거부** | `⚠️ 위치 권한 거부됨` | `⚠️ Location permission denied` |
| **도보 시간 계산** | `도보 {m}분` | `{m} min walk` |
| **1분 미만 도보** | `도보 1분 미만` | `< 1 min walk` |
| **거리 계산** | `{d}m` / `{d}km` | `{d}m` / `{d}km` |
| **쓰레기통 종류** | `일반·재활용` / `담배꽁초` / `종류 미상` | `General · Recyclable` / `Cigarette Bin` / `Public Bin` |

---

## 4. UI/UX 디자인 상세 계획

### 4.1 언어 전환 토글 버튼 디자인 (Header Top-Right)
* **위치**: 헤더 우측 상단 `#btn-refresh` 버튼의 좌측에 배치.
* **외형**:
  * 글래스모피즘 캡슐형 버튼 (`px-2.5 py-1.5 rounded-xl border border-gray-200/70 bg-white/80 backdrop-blur-md`)
  * 아이콘 및 텍스트: `🌐 EN` (한국어 모드일 때) / `🌐 KO` (영어 모드일 때)
  * 클릭 시: 가벼운 햅틱 애니메이션(`active:scale-95`)과 함께 전체 화면의 텍스트가 깜빡임 없이 즉시 전환.

---

## 5. 기술적 고려사항 및 한계 극복 방안

### 5.1 카카오맵 지도 타일과 공공데이터 원천 텍스트
* **현실적 한계**: 카카오맵 기본 지도 타일(도로명, 건물명)과 서울시 공공데이터의 쓰레기통 주소명(예: `신당동 청구역 버스정류장 02-189`)은 한글 텍스트입니다.
* **극복 전략**:
  1. **시각적 가이드의 완전성**: 외국인 관광객에게 가장 중요한 것은 긴 주소명이 아니라 **"내 위치의 파란 점"**, **"가장 가까운 쓰레기통 핀"**, **"보행로를 따라 연결된 파란색 도보 안내선"**, **"도보 2분 (125m)"** 정보입니다.
  2. **바텀시트 주소 가공**: 서울시 주소 표기 중 구/동 이름 뒤의 시설물(예: `청구역 버스정류장`, `이태원역 3번출구`)을 식별할 수 있는 핵심 키워드는 가능하면 영문 카테고리(`Nearest Street Bin near Cheonggu Stn`) 등으로 친절하게 보조합니다.
  3. **구글 지도 선택권 강화**: 외국인은 카카오맵/네이버지도 앱이 설치되어 있지 않은 경우가 많으므로, "다른 앱으로 길찾기" 클릭 시 구글 지도로 좌표를 즉시 확인할 수 있도록 연동 상태를 유지합니다.

---

## 6. 단계별 상세 구현 로드맵 (Step-by-Step)

```
[Phase 1: i18n 모듈 설계]
  └── translations 객체 정의 (KO / EN)
  └── getLang(), setLang(), t(key, params) 헬퍼 함수 작성

[Phase 2: HTML 정적 요소 마킹]
  └── HTML 태그에 data-i18n="key" 및 data-i18n-attr="placeholder:key" 속성 부여
  └── updateStaticTranslations() 함수로 일괄 텍스트 치환 적용

[Phase 3: 동적 스크립트 텍스트 i18n 적용]
  └── updateBottomSheet(), startNavigation(), sub-status 등 하드코딩된 한글 텍스트를 t() 함수로 래핑

[Phase 4: 언어 전환 토글 버튼 배치 및 이벤트 바인딩]
  └── 헤더에 #btn-lang-toggle 추가
  └── 클릭 시 ko <-> en 스위치 및 localStorage 동기화

[Phase 5: 검증 및 GA4 트래킹 연동]
  └── 브라우저 언어 영문(en-US) 모의 테스트 (크롬 개발자도구 센서/언어)
  └── trackGAEvent('language_set', { language: currentLang }) 연동
```

---

## 7. 기대 효과
1. **외국인 관광객 유입 극대화**: 한국 여행 커뮤니티(Reddit, 외국인 인스타 여행 팁, 교환학생 단톡방)에서 즉각적인 반응 획득.
2. **공공/관광 지원사업 경쟁력 확보**: "외국인 관광객 서울 여행 만족도 향상 및 보행 친화 스마트 맵"으로 브랜딩 강화.
3. **완전 자동화(Zero-Friction)**: 외국인은 접속하는 순간 영어로 보이고, 한국인은 기존과 동일하게 한글로 보여 양쪽 유저 모두에게 최고의 사용성을 제공.
