import Foundation
import Observation

@MainActor
@Observable
final class AuthSession {
    enum State: Equatable {
        case restoring
        case restoreFailed
        case signedOut
        case signedIn(AuthUser)
    }

    private(set) var state: State = .restoring
    private(set) var legalVersions: LegalVersions?
    private(set) var isWorking = false
    var message: String?
    var beforeSignOut: (@MainActor @Sendable () async -> Void)?

    private let service: any NativeAuthServicing
    private let tokenStore: any RefreshTokenStoring
    private var refreshTask: Task<Bool, Never>?
    private var generation = 0

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
            _ = refreshToken
            if !(await refreshAccess()), state == .restoring {
                state = .restoreFailed
            }
        } catch {
            state = .restoreFailed
            message = readable(error)
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

    func signIn(provider: String, payload: NativeIdentityPayload, identityService: any NativeIdentityServicing) async {
        await perform { try await identityService.identityLogin(provider: provider, payload: payload) }
    }

    func signOut() async {
        isWorking = true
        await beforeSignOut?()
        generation += 1
        refreshTask?.cancel()
        refreshTask = nil
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

    /// Refreshes an expired bearer session using the rotated token held in Keychain.
    /// Feature stores call this only after an authenticated request returns 401.
    func refreshAccess() async -> Bool {
        if let refreshTask { return await refreshTask.value }
        let epoch = generation
        let task = Task { await self.refreshOnce(epoch: epoch) }
        refreshTask = task
        let result = await task.value
        if generation == epoch { refreshTask = nil }
        return result
    }

    private func refreshOnce(epoch: Int) async -> Bool {
        do {
            guard let refreshToken = try await tokenStore.load() else {
                guard generation == epoch else { return false }
                await clearSession()
                return false
            }
            guard generation == epoch else { return false }
            let tokens = try await service.nativeRefresh(refreshToken: refreshToken)
            guard generation == epoch, !Task.isCancelled else { return false }
            try await establish(tokens, epoch: epoch)
            return true
        } catch APIError.unauthorized {
            guard generation == epoch else { return false }
            await clearSession()
            return false
        } catch {
            // Offline/5xx is not evidence that a Keychain session is invalid.
            guard generation == epoch else { return false }
            message = readable(error)
            return false
        }
    }

    func accountWasDeleted() async {
        generation += 1
        refreshTask?.cancel()
        refreshTask = nil
        await clearSession()
    }

    func requestVerificationCode() async {
        isWorking = true
        defer { isWorking = false }
        do {
            let delivery = try await service.requestVerificationCode()
            message = delivery.deliveryAccepted
                ? "A six-digit code is on its way. It expires in 10 minutes."
                : delivery.deliveryConfigured
                    ? "Please wait a minute before requesting another code."
                    : "Email delivery is not configured for this environment yet."
        } catch {
            message = readable(error)
        }
    }

    func confirmVerificationCode(_ code: String) async {
        let normalized = code.filter(\.isNumber)
        guard normalized.count == 6 else {
            message = "Enter the six-digit code from your email."
            return
        }
        isWorking = true
        defer { isWorking = false }
        do {
            let user = try await service.confirmVerificationCode(normalized)
            state = .signedIn(user)
            message = "Email confirmed. Your account is ready."
        } catch {
            message = readable(error)
        }
    }

    private func perform(_ operation: @escaping @Sendable () async throws -> NativeAuthTokens) async {
        guard !isWorking else { return }
        generation += 1
        let epoch = generation
        isWorking = true
        message = nil
        defer { isWorking = false }
        do {
            let tokens = try await operation()
            guard generation == epoch else { return }
            try await establish(tokens, epoch: epoch)
        } catch {
            message = readable(error)
        }
    }

    private func establish(_ tokens: NativeAuthTokens, epoch: Int) async throws {
        guard tokens.tokenType.lowercased() == "bearer" else { throw APIError.invalidResponse }
        guard generation == epoch else { throw CancellationError() }
        try await tokenStore.save(tokens.refreshToken)
        guard generation == epoch else { throw CancellationError() }
        await service.setAccessToken(tokens.accessToken)
        guard generation == epoch else { throw CancellationError() }
        state = .signedIn(tokens.user)
    }

    private func clearSession() async {
        try? await tokenStore.clear()
        await service.setAccessToken(nil)
        state = .signedOut
    }

    private func readable(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription
            ?? "Farelin could not complete that request."
    }
}
