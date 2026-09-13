import Foundation
import Observation

@MainActor
@Observable
final class AuthSession {
    enum State: Equatable {
        case restoring
        case signedOut
        case signedIn(AuthUser)
    }

    private(set) var state: State = .restoring
    private(set) var legalVersions: LegalVersions?
    private(set) var isWorking = false
    var message: String?

    private let service: any NativeAuthServicing
    private let tokenStore: any RefreshTokenStoring

    init(service: any NativeAuthServicing, tokenStore: any RefreshTokenStoring) {
        self.service = service
        self.tokenStore = tokenStore
    }

    func restore() async {
        state = .restoring
        async let legalRequest = service.legalVersions()
        do {
            legalVersions = try await legalRequest
        } catch {
            legalVersions = nil
        }

        do {
            guard let refreshToken = try await tokenStore.load() else {
                state = .signedOut
                return
            }
            let tokens = try await service.nativeRefresh(refreshToken: refreshToken)
            try await establish(tokens)
        } catch {
            try? await tokenStore.clear()
            await service.setAccessToken(nil)
            state = .signedOut
        }
    }

    func signIn(email: String, password: String) async {
        await perform {
            try await self.service.nativeLogin(email: email, password: password)
        }
    }

    func signUp(email: String, password: String, displayName: String?) async {
        guard let legalVersions else {
            message = "Farelin could not load the current terms. Check your connection and try again."
            return
        }
        await perform {
            try await self.service.nativeSignup(
                email: email,
                password: password,
                displayName: displayName,
                legal: legalVersions
            )
        }
    }

    func signOut() async {
        isWorking = true
        let refreshToken = try? await tokenStore.load()
        if let refreshToken {
            try? await service.nativeLogout(refreshToken: refreshToken)
        }
        try? await tokenStore.clear()
        await service.setAccessToken(nil)
        state = .signedOut
        message = nil
        isWorking = false
    }

    func resendVerification() async {
        isWorking = true
        defer { isWorking = false }
        do {
            let delivery = try await service.resendVerification()
            message = delivery.deliveryAccepted
                ? "A fresh verification link is on its way."
                : "Farelin could not send a verification email right now."
        } catch {
            message = readable(error)
        }
    }

    func refreshUser() async {
        do {
            let user = try await service.currentUser()
            state = .signedIn(user)
            message = user.isVerified ? "Email confirmed." : "This email is not confirmed yet."
        } catch {
            message = readable(error)
        }
    }

    private func perform(_ operation: @escaping @Sendable () async throws -> NativeAuthTokens) async {
        isWorking = true
        message = nil
        defer { isWorking = false }
        do {
            let tokens = try await operation()
            try await establish(tokens)
        } catch {
            message = readable(error)
        }
    }

    private func establish(_ tokens: NativeAuthTokens) async throws {
        guard tokens.tokenType.lowercased() == "bearer" else { throw APIError.invalidResponse }
        try await tokenStore.save(tokens.refreshToken)
        await service.setAccessToken(tokens.accessToken)
        state = .signedIn(tokens.user)
    }

    private func readable(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription
            ?? "Farelin could not complete that request."
    }
}
