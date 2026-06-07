# /usb-deploy — Ad Hoc IPA 빌드 + USB 직접 설치

TestFlight를 우회하여 Ad Hoc IPA를 빌드하고 USB로 iPhone에 직접 설치한다.
**이 커맨드는 절차 가이드가 아닌 자동 실행 지침이다. Claude가 모든 단계를 자동 수행한다.**

**전제 조건 (사용자 책임):**
- Apple Developer Program 가입 ($99/년)
- GitHub repo에 secrets 설정 (DISTRIBUTION_CERTIFICATE_P12, DISTRIBUTION_CERTIFICATE_PASSWORD, APP_STORE_CONNECT_KEY_ID, APP_STORE_CONNECT_ISSUER_ID, APP_STORE_CONNECT_PRIVATE_KEY, TEAM_ID)
- iPhone USB 연결 + 개발자 모드 ON
- `pymobiledevice3` 설치됨

인자: `$ARGUMENTS` (Xcode 프로젝트 경로. 없으면 자동 탐색)

사용 예시:
- `/usb-deploy` — 현재 디렉토리에서 xcodeproj 자동 탐색
- `/usb-deploy ./MyApp` — 지정 경로의 프로젝트 사용

---

## 자동 실행 지침

**Claude는 아래 모든 단계를 사용자 확인 없이 연속 실행한다. 에러 발생 시 자동 복구를 시도하고, 복구 불가능한 경우에만 사용자에게 알린다.**

### 1단계: 환경 자동 감지

1. `pymobiledevice3 usbmux list` 실행
   - 빈 배열 → 사용자에게 "iPhone USB 연결 + 신뢰 필요" 안내 후 30초 대기, 재시도 (최대 3회)
   - 기기 감지 → UDID, ProductType, ProductVersion 추출하여 변수에 저장

2. **Apple Watch UDID 자동 감지** (watchOS 타겟이 있는 경우)
   - `pymobiledevice3 companion list --udid {{IPHONE_UDID}}` 실행
   - 페어링된 Watch UDID 추출하여 변수에 저장
   - Watch가 없으면 watchOS 타겟 빌드는 포함하되 기기 등록은 iPhone만

3. Xcode 프로젝트 자동 탐색
   - `$ARGUMENTS`가 있으면 해당 경로 사용
   - 없으면 `find . -maxdepth 3 -name "*.xcodeproj"` 으로 탐색
   - 탐색 실패 → 에러 보고 및 중단

4. 프로젝트 정보 자동 추출
   - `project.pbxproj`에서 `PRODUCT_BUNDLE_IDENTIFIER` 추출 (iOS, watchOS 각각)
   - `.xcscheme` 파일에서 scheme 이름 추출
   - `Info.plist`에서 번들 구조 확인
   - watchOS 타겟 존재 여부 확인 (`SDKROOT = watchos` 검색)

### 2단계: Fastlane adhoc lane 자동 생성

`fastlane/Fastfile` 확인:
- `adhoc` lane이 이미 있으면 → UDID만 업데이트
- 없으면 → 1단계에서 추출한 정보로 자동 생성

**생성 규칙:**
- UDID: 1단계에서 추출한 값
- BUNDLE_ID: pbxproj에서 추출한 iOS 번들 ID
- PROJECT: 탐색된 xcodeproj 파일명
- SCHEME: xcscheme에서 추출한 scheme 이름
- watchOS 타겟이 있으면 Watch 프로필도 추가

**Fastlane adhoc lane 템플릿:**

```ruby
desc "Ad Hoc build for USB install"
lane :adhoc do
  api_key = app_store_connect_api_key(
    key_id: ENV["APP_STORE_CONNECT_KEY_ID"],
    issuer_id: ENV["APP_STORE_CONNECT_ISSUER_ID"],
    key_content: ENV["APP_STORE_CONNECT_PRIVATE_KEY"],
    is_key_content_base64: false
  )

  # iPhone + Apple Watch (있으면) 모두 등록
  register_devices(
    devices: {
      "iPhone" => "{{IPHONE_UDID}}",
      # watchOS 타겟이 있고 Watch가 페어링되어 있으면 추가:
      # "Apple Watch" => "{{WATCH_UDID}}",
    },
    api_key: api_key
  )

  get_provisioning_profile(
    api_key: api_key,
    app_identifier: "{{IOS_BUNDLE_ID}}",
    adhoc: true,
    force: true
  )
  ios_uuid = lane_context[SharedValues::SIGH_UUID]

  # watchOS가 있는 경우에만 아래 블록 추가
  # get_provisioning_profile(
  #   api_key: api_key,
  #   app_identifier: "{{WATCH_BUNDLE_ID}}",
  #   adhoc: true,
  #   force: true,
  #   platform: "ios"
  # )
  # watch_uuid = lane_context[SharedValues::SIGH_UUID]

  increment_build_number(
    build_number: Time.now.strftime("%Y%m%d%H%M"),
    xcodeproj: "{{PROJECT}}.xcodeproj"
  )

  build_app(
    scheme: "{{SCHEME}}",
    project: "{{PROJECT}}.xcodeproj",
    configuration: "Release",
    destination: "generic/platform=iOS",
    export_method: "ad-hoc",
    export_options: {
      teamID: ENV["TEAM_ID"],
      compileBitcode: false,
      thinning: "<none>",
      signingStyle: "manual",
      provisioningProfiles: {
        "{{IOS_BUNDLE_ID}}" => ios_uuid,
        # watchOS: "{{WATCH_BUNDLE_ID}}" => watch_uuid,
      },
      signingCertificate: "iPhone Distribution"
    },
    xcargs: "CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY='iPhone Distribution' ENABLE_BITCODE=NO",
    clean: true
  )
end
```

### 3단계: GitHub Actions 워크플로우 자동 설정

`.github/workflows/` 내 기존 워크플로우를 확인:
- `fastlane adhoc`을 실행하는 step이 있으면 → 그대로 사용
- 없으면 → 기존 워크플로우에 adhoc job 추가 또는 새 워크플로우 생성

**필수 포함 요소:**
- 최신 Xcode 자동 선택: `ls -d /Applications/Xcode*.app | sort -V | tail -1`
- watchOS Platform 다운로드 (watchOS 타겟 있을 때)
- Distribution Certificate 설치 (p12 디코딩 + keychain 임포트)
- `bundle exec fastlane adhoc`
- `actions/upload-artifact@v4`로 IPA 업로드 (artifact 이름: `adhoc-ipa`)

**GitHub Actions 워크플로우 템플릿:**

```yaml
name: Ad Hoc Build

on:
  workflow_dispatch:

jobs:
  adhoc:
    runs-on: macos-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4

      - name: Select latest Xcode
        run: |
          XCODE_PATH=$(ls -d /Applications/Xcode*.app | sort -V | tail -1)
          sudo xcode-select -s "$XCODE_PATH"
          xcodebuild -version

      # watchOS 타겟이 있는 경우에만 추가
      # - name: Download watchOS Platform
      #   run: xcodebuild -downloadPlatform watchOS

      - name: Install Distribution Certificate
        env:
          P12_BASE64: ${{ secrets.DISTRIBUTION_CERTIFICATE_P12 }}
          P12_PASSWORD: ${{ secrets.DISTRIBUTION_CERTIFICATE_PASSWORD }}
        run: |
          CERT_PATH=$RUNNER_TEMP/certificate.p12
          KEYCHAIN_PATH=$RUNNER_TEMP/app-signing.keychain-db
          KEYCHAIN_PASSWORD=$(openssl rand -hex 12)
          echo -n "$P12_BASE64" | base64 --decode > "$CERT_PATH"
          security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
          security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security import "$CERT_PATH" -P "$P12_PASSWORD" -A -t cert -f pkcs12 \
            -k "$KEYCHAIN_PATH"
          security set-key-partition-list -S apple-tool:,apple: \
            -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
          security list-keychains -d user -s "$KEYCHAIN_PATH" login.keychain

      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2'
          bundler-cache: true

      - name: Install Fastlane
        run: bundle install --jobs 4

      - name: Run Fastlane adhoc
        env:
          APP_STORE_CONNECT_KEY_ID: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
          APP_STORE_CONNECT_ISSUER_ID: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
          APP_STORE_CONNECT_PRIVATE_KEY: ${{ secrets.APP_STORE_CONNECT_PRIVATE_KEY }}
          TEAM_ID: ${{ secrets.TEAM_ID }}
        run: bundle exec fastlane adhoc

      - name: Upload IPA
        uses: actions/upload-artifact@v4
        with:
          name: adhoc-ipa
          path: |
            *.ipa
            **/*.ipa
          if-no-files-found: error

      - name: Cleanup keychain and certificate
        if: always()
        run: |
          security delete-keychain "$RUNNER_TEMP/app-signing.keychain-db" || true
          rm -f "$RUNNER_TEMP/certificate.p12"
```

### 4단계: 빌드 실행 + IPA 다운로드

1. 변경사항 커밋 & 푸시
2. `gh workflow run "Ad Hoc Build"` 로 워크플로우 수동 트리거 (`workflow_dispatch` 이벤트)
3. 트리거된 run ID 획득: `gh run list --workflow="Ad Hoc Build" -L 1 --json databaseId -q '.[0].databaseId'` (트리거 직후 1~2초 대기 후 실행)
4. `gh run watch <RUN_ID>` 로 CI 완료 대기
5. 실패 시 → 로그 분석 후 자동 수정 (최대 3회 재시도)
   - 프로비저닝 프로필 오류 → `force: true` 확인
   - Xcode 버전 오류 → Xcode 선택 로직 수정
   - 빌드 오류 → 로그에서 원인 추출하여 수정
6. 성공 시 → `gh run download <RUN_ID> --name adhoc-ipa -D ./ipa_output`로 IPA 다운로드

### 5단계: USB 직접 설치

**iPhone 앱 설치:**
```bash
pymobiledevice3 apps install ./ipa_output/*.ipa --udid {{IPHONE_UDID}}
```

- `Installation succeed.` → watchOS 확인 후 6단계로
- `ApplicationVerificationFailed` → export_method 확인, 3단계부터 재시도
- 기타 에러 → 에러 메시지 분석 후 자동 복구 시도

**watchOS companion 앱 (watchOS 타겟이 있는 경우):**
- watchOS companion 앱은 iPhone에 IPA를 설치하면 자동으로 페어링된 Apple Watch로 전파된다
- 자동 전파되지 않는 경우: Watch 앱 → 설정 → "자동으로 앱 설치" 확인 요청
- Watch UDID가 `register_devices`에 등록되어 있어야 프로비저닝이 유효하다

**설치 실패 시 syslog 진단:**
```bash
pymobiledevice3 syslog live --udid {{IPHONE_UDID}} | grep -i "install\|error\|fail"
```
설치 에러의 정확한 원인 (코드 서명, 프로비저닝, 호환성 등)을 실시간으로 확인하여 자동 복구에 활용한다.

### 6단계: 설치 검증

**iPhone 앱 검증:**
```bash
pymobiledevice3 apps list --udid {{IPHONE_UDID}} | grep -i "{{IOS_BUNDLE_ID}}"
```

앱이 목록에 있으면 → watchOS 확인 후 **성공 보고**
없으면 → 5단계 재시도

**watchOS 앱 검증 (watchOS 타겟이 있는 경우):**
- iPhone에 앱이 설치된 후, Watch companion 앱이 자동 전파되기까지 최대 1~2분 소요
- 전파 확인이 어려운 경우: "iPhone에 앱이 설치되었습니다. Apple Watch에서 앱이 표시되는지 확인해주세요." 안내

---

## 자동 복구 규칙

| 에러 | 자동 복구 방법 |
|------|---------------|
| `usbmux list` 빈 배열 | 30초 대기 후 재시도 (3회) |
| `ApplicationVerificationFailed` | export_method를 "ad-hoc"으로 수정 후 재빌드 |
| `provisioning profile not found` | `force: true`로 프로필 재생성 후 재빌드 |
| `no implicit conversion of Symbol` | `lane_context[SharedValues::SIGH_UUID]`로 수정 |
| CI Xcode 버전 불일치 | 최신 Xcode 자동 선택 로직 적용 |
| CI 빌드 실패 (기타) | 로그에서 에러 추출 → pbxproj/Info.plist 자동 수정 → 재빌드 |
| `Gemfile not found` | Gemfile 자동 생성 (`source "https://rubygems.org"` + `gem "fastlane"`) 후 `bundle install` |
| watchOS SDK 미설치 | `xcodebuild -downloadPlatform watchOS` 추가 |
| UDID 미등록 | `register_devices` 자동 실행 |
| Watch 앱 설치 실패 (`could not be installed`) | `pymobiledevice3 companion list`로 Watch UDID 추출 → `register_devices`에 추가 → Ad Hoc 프로필 재생성(`force: true`) → 재빌드 → USB 재설치 |
| Watch UDID 미감지 | Watch가 iPhone에 페어링되어 있는지 확인 요청 |
| `companion list` 서브커맨드 실패 | pymobiledevice3 버전 확인 → `pip install -U pymobiledevice3` → 재시도. 여전히 실패 시 Watch UDID 수동 입력 요청 |

---

## 참고: TestFlight vs Ad Hoc

| | TestFlight | Ad Hoc (USB) |
|---|---|---|
| 비용 | 무료 | 무료 |
| 기기 등록 | 불필요 | UDID 자동 등록 |
| 설치 방법 | TestFlight 앱 | USB + pymobiledevice3 |
| 베타 심사 | External은 필요 | 불필요 |
| variant 생성 | Apple 서버 (실패 가능) | 빌드 그대로 설치 |
| 최대 기기 수 | 10,000명 | 100대 |

## 이 방법을 쓰는 이유

TestFlight에서 `terminalReason: 1` (no compatible variant) 에러가 발생할 때, Apple 서버가 device-specific binary variant를 생성하지 못하는 경우가 있다. Ad Hoc 빌드는 Apple 서버의 variant 생성을 우회하여 빌드된 IPA를 그대로 설치한다. USB 시스템 로그(`pymobiledevice3 syslog live`)로 설치 실패 원인을 정확히 진단할 수 있다.
