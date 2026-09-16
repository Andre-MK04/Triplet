import Foundation

struct NativeIdentityProviders: Decodable, Sendable { let apple: Bool; let google: Bool }
struct NativeIdentityChallenge: Decodable, Sendable { let id: String; let nonce: String }
struct NativeIdentityPayload: Encodable, Sendable {
    let idToken: String
    var authorizationCode: String? = nil
    var challengeId: String? = nil
    let intent: String
    var acceptedTermsVersion: String? = nil
    var acknowledgedPrivacyVersion: String? = nil
}
protocol NativeIdentityServicing: Sendable {
    func identityProviders() async throws -> NativeIdentityProviders
    func identityChallenge() async throws -> NativeIdentityChallenge
    func identityLogin(provider: String, payload: NativeIdentityPayload) async throws -> NativeAuthTokens
}
