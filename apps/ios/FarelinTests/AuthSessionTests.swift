import XCTest
@testable import Farelin

@MainActor
final class AuthSessionTests: XCTestCase {
    func testCreateAccountExplainsMissingPasswordInsteadOfSilentlyDisablingSubmit() {
        let message = AuthenticationFormValidator.message(
            mode: .createAccount,
            email: "traveler@example.com",
            password: "",
            acceptedLegal: true,
            legalVersionsLoaded: true
        )

        XCTAssertEqual(message, "Enter your password.")
    }

    func testCreateAccountExplainsMinimumPasswordLength() {
        let message = AuthenticationFormValidator.message(
            mode: .createAccount,
            email: "traveler@example.com",
            password: "too-short",
            acceptedLegal: true,
            legalVersionsLoaded: true
        )

        XCTAssertEqual(message, "Use at least 12 characters for your password.")
    }

    func testLegacySignInDoesNotEnforceTheNewAccountPasswordLength() {
        let message = AuthenticationFormValidator.message(
            mode: .signIn,
            email: "traveler@example.com",
            password: "old-pass",
            acceptedLegal: false,
            legalVersionsLoaded: false
        )

        XCTAssertNil(message)
    }

    func testRestoreWithoutKeychainTokenShowsSignIn() async {
        let service = FakeAuthService()
        let store = MemoryRefreshTokenStore()
        let session = AuthSession(service: service, tokenStore: store)

        await session.restore()

        XCTAssertEqual(session.state, .signedOut)
    }

    func testSignInKeepsAccessTokenInClientAndRefreshTokenInStore() async throws {
        let service = FakeAuthService()
        let store = MemoryRefreshTokenStore()
        let session = AuthSession(service: service, tokenStore: store)

        await session.signIn(email: "traveler@example.com", password: "Strong-pass-123!")

        let storedToken = await store.load()
        let accessToken = await service.savedAccessToken()
        XCTAssertEqual(session.state, .signedIn(.fixture))
        XCTAssertEqual(storedToken, "refresh-new")
        XCTAssertEqual(accessToken, "access-new")
    }

    func testRelaunchRotatesStoredRefreshToken() async throws {
        let service = FakeAuthService()
        let store = MemoryRefreshTokenStore(token: "refresh-old")
        let session = AuthSession(service: service, tokenStore: store)

        await session.restore()

        let storedToken = await store.load()
        let refreshedToken = await service.refreshedWithToken()
        XCTAssertEqual(session.state, .signedIn(.fixture))
        XCTAssertEqual(storedToken, "refresh-new")
        XCTAssertEqual(refreshedToken, "refresh-old")
    }

    func testSignOutRevokesAndClearsLocalSession() async throws {
        let service = FakeAuthService()
        let store = MemoryRefreshTokenStore(token: "refresh-new")
        let session = AuthSession(service: service, tokenStore: store)
        await session.signIn(email: "traveler@example.com", password: "Strong-pass-123!")

        await session.signOut()

        let storedToken = await store.load()
        let logoutToken = await service.loggedOutWithToken()
        let accessToken = await service.savedAccessToken()
        XCTAssertEqual(session.state, .signedOut)
        XCTAssertNil(storedToken)
        XCTAssertEqual(logoutToken, "refresh-new")
        XCTAssertNil(accessToken)
    }

    func testExpiredAccessCanRefreshAndRotateStoredToken() async throws {
        let service = FakeAuthService()
        let store = MemoryRefreshTokenStore(token: "refresh-old")
        let session = AuthSession(service: service, tokenStore: store)

        let refreshed = await session.refreshAccess()
        let storedToken = try await store.load()
        let accessToken = await service.savedAccessToken()

        XCTAssertTrue(refreshed)
        XCTAssertEqual(session.state, .signedIn(.fixture))
        XCTAssertEqual(storedToken, "refresh-new")
        XCTAssertEqual(accessToken, "access-new")
    }

    func testConfirmingVerificationCodeUpdatesSignedInUser() async {
        let service = FakeAuthService()
        let store = MemoryRefreshTokenStore()
        let session = AuthSession(service: service, tokenStore: store)
        await session.signIn(email: "traveler@example.com", password: "Strong-pass-123!")

        await session.confirmVerificationCode("123456")

        let confirmedCode = await service.confirmedCode()
        XCTAssertEqual(session.state, .signedIn(.fixture))
        XCTAssertEqual(confirmedCode, "123456")
        XCTAssertEqual(session.message, "Email confirmed. Your account is ready.")
    }

    func testShortVerificationCodeIsRejectedBeforeNetworkRequest() async {
        let service = FakeAuthService()
        let session = AuthSession(service: service, tokenStore: MemoryRefreshTokenStore())

        await session.confirmVerificationCode("123")

        let confirmedCode = await service.confirmedCode()
        XCTAssertNil(confirmedCode)
        XCTAssertEqual(session.message, "Enter the six-digit code from your email.")
    }
}

private actor MemoryRefreshTokenStore: RefreshTokenStoring {
    private var token: String?

    init(token: String? = nil) {
        self.token = token
    }

    func load() -> String? { token }
    func save(_ token: String) { self.token = token }
    func clear() { token = nil }
}

private actor FakeAuthService: NativeAuthServicing {
    private var accessToken: String?
    private var refreshedToken: String?
    private var logoutToken: String?
    private var verificationCode: String?

    func legalVersions() -> LegalVersions {
        LegalVersions(termsVersion: "current-terms", privacyVersion: "current-privacy")
    }

    func nativeLogin(email: String, password: String) -> NativeAuthTokens { .fixture }

    func nativeSignup(
        email: String,
        password: String,
        displayName: String?,
        legal: LegalVersions
    ) -> NativeAuthTokens { .fixture }

    func nativeRefresh(refreshToken: String) -> NativeAuthTokens {
        refreshedToken = refreshToken
        return .fixture
    }

    func nativeLogout(refreshToken: String) {
        logoutToken = refreshToken
    }

    func currentUser() -> AuthUser { .fixture }

    func requestVerificationCode() -> VerificationDelivery {
        VerificationDelivery(
            message: "Sent.",
            deliveryConfigured: true,
            deliveryAccepted: true
        )
    }

    func confirmVerificationCode(_ code: String) -> AuthUser {
        verificationCode = code
        return .fixture
    }

    func setAccessToken(_ token: String?) {
        accessToken = token
    }

    func savedAccessToken() -> String? { accessToken }
    func refreshedWithToken() -> String? { refreshedToken }
    func loggedOutWithToken() -> String? { logoutToken }
    func confirmedCode() -> String? { verificationCode }
}

private extension AuthUser {
    static let fixture = AuthUser(
        id: "user-1",
        email: "traveler@example.com",
        displayName: "Traveler",
        isVerified: true,
        createdAt: "2026-09-11T12:00:00",
        hasPassword: true,
        connectedProviders: []
    )
}

private extension NativeAuthTokens {
    static let fixture = NativeAuthTokens(
        user: .fixture,
        accessToken: "access-new",
        refreshToken: "refresh-new",
        tokenType: "Bearer",
        expiresInSeconds: 900
    )
}
