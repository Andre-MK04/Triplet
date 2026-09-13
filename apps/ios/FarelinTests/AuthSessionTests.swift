import XCTest
@testable import Farelin

@MainActor
final class AuthSessionTests: XCTestCase {
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

    func resendVerification() -> VerificationDelivery {
        VerificationDelivery(
            message: "Sent.",
            deliveryConfigured: true,
            deliveryAccepted: true
        )
    }

    func setAccessToken(_ token: String?) {
        accessToken = token
    }

    func savedAccessToken() -> String? { accessToken }
    func refreshedWithToken() -> String? { refreshedToken }
    func loggedOutWithToken() -> String? { logoutToken }
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
