import Foundation

struct AuthUser: Codable, Equatable, Identifiable, Sendable {
    let id: String
    let email: String
    let displayName: String?
    let isVerified: Bool
    let createdAt: String
    let hasPassword: Bool
    let connectedProviders: [String]
}

struct NativeAuthTokens: Decodable, Equatable, Sendable {
    let user: AuthUser
    let accessToken: String
    let refreshToken: String
    let tokenType: String
    let expiresInSeconds: Int
}

struct LegalVersions: Decodable, Equatable, Sendable {
    let termsVersion: String
    let privacyVersion: String
}

struct PlansEnvelope: Decodable, Sendable {
    let termsVersion: String
    let privacyVersion: String
}

struct AuthEnvelope: Decodable, Sendable {
    let user: AuthUser
}

struct VerificationDelivery: Decodable, Sendable {
    let message: String
    let deliveryConfigured: Bool
    let deliveryAccepted: Bool
}

struct LogoutResponse: Decodable, Sendable { let ok: Bool }

struct LoginPayload: Encodable, Sendable {
    let email: String
    let password: String
}

struct SignupPayload: Encodable, Sendable {
    let email: String
    let password: String
    let displayName: String?
    let acceptedTermsVersion: String
    let acknowledgedPrivacyVersion: String
}

struct RefreshPayload: Encodable, Sendable {
    let refreshToken: String
}
