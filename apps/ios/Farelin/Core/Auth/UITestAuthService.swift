#if DEBUG
import Foundation

/// Deterministic signed-out UI tests. Never compiled into a Release archive;
/// never signs in, issues tokens, deletes Keychain entries, or spends API credit.
actor UITestAuthService: NativeAuthServicing, RefreshTokenStoring {
    func load() -> String? { nil }
    func save(_ token: String) {}
    func clear() {}
    func legalVersions() -> LegalVersions { LegalVersions(termsVersion: "ui-test", privacyVersion: "ui-test") }
    func nativeLogin(email: String, password: String) throws -> NativeAuthTokens { throw APIError.unavailable }
    func nativeSignup(email: String, password: String, displayName: String?, legal: LegalVersions) throws -> NativeAuthTokens { throw APIError.unavailable }
    func nativeRefresh(refreshToken: String) throws -> NativeAuthTokens { throw APIError.unauthorized }
    func nativeLogout(refreshToken: String) {}
    func currentUser() throws -> AuthUser { throw APIError.unauthorized }
    func requestVerificationCode() throws -> VerificationDelivery { throw APIError.unavailable }
    func confirmVerificationCode(_ code: String) throws -> AuthUser { throw APIError.unavailable }
    func setAccessToken(_ token: String?) {}
}
#endif
