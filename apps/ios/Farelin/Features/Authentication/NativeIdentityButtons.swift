import AuthenticationServices
import CryptoKit
@preconcurrency import GoogleSignIn
import SwiftUI

struct NativeIdentityButtons: View {
    let session: AuthSession
    let service: any NativeIdentityServicing
    let creatingAccount: Bool
    let acceptedLegal: Bool
    @Environment(\.colorScheme) private var colorScheme
    @State private var providers: NativeIdentityProviders?
    @State private var challenge: NativeIdentityChallenge?
    @State private var busy = false
    @State private var message: String?

    private var canContinue: Bool {
        !busy && !session.isWorking && (!creatingAccount || (acceptedLegal && session.legalVersions != nil))
    }

    var body: some View {
        VStack(spacing: 14) {
            if providers?.apple == true {
                SignInWithAppleButton(creatingAccount ? .signUp : .signIn) { request in
                    request.requestedScopes = [.email, .fullName]
                    if let challenge { request.nonce = Self.hashedNonce(challenge.nonce) }
                } onCompletion: { result in
                    Task { await finishApple(result) }
                }
                .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                .frame(height: 50)
                .clipShape(.rect(cornerRadius: 14))
                .disabled(!canContinue || challenge == nil)
                .accessibilityIdentifier("auth-apple")
            }
            if providers?.google == true, googleClientID != nil {
                Button {
                    Task { await signInWithGoogle() }
                } label: {
                    HStack { Text("Continue with Google"); if busy { ProgressView() } }
                        .font(.headline).frame(maxWidth: .infinity).frame(height: 50)
                        .background(FarelinColor.raised, in: .rect(cornerRadius: 14))
                }
                .buttonStyle(.plain)
                .disabled(!canContinue)
                .accessibilityIdentifier("auth-google")
            }
            if creatingAccount, !acceptedLegal, providers?.apple == true || providers?.google == true {
                Text("Accept the terms above before creating an account with Apple or Google.")
                    .font(.caption).foregroundStyle(FarelinColor.mist)
            }
            if let message { Text(message).font(.footnote).foregroundStyle(FarelinColor.coral) }
        }
        .task { await load() }
    }

    nonisolated static func hashedNonce(_ nonce: String) -> String {
        SHA256.hash(data: Data(nonce.utf8)).map { String(format: "%02x", $0) }.joined()
    }
    private var googleClientID: String? {
        let value = Bundle.main.object(forInfoDictionaryKey: "GoogleIOSClientID") as? String
        return value.flatMap { $0.isEmpty || $0.contains("$(") ? nil : $0 }
    }
    private func load() async {
        do {
            providers = try await service.identityProviders()
            if providers?.apple == true { challenge = try await service.identityChallenge() }
        } catch { providers = nil }
    }
    private func payload(token: String, code: String? = nil, challengeId: String? = nil) -> NativeIdentityPayload {
        NativeIdentityPayload(idToken: token, authorizationCode: code, challengeId: challengeId,
            intent: creatingAccount ? "signup" : "login",
            acceptedTermsVersion: creatingAccount ? session.legalVersions?.termsVersion : nil,
            acknowledgedPrivacyVersion: creatingAccount ? session.legalVersions?.privacyVersion : nil)
    }
    private func finishApple(_ result: Result<ASAuthorization, any Error>) async {
        guard canContinue else { return }
        busy = true; message = nil
        defer { busy = false }
        do {
            let authorization = try result.get()
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken, let token = String(data: tokenData, encoding: .utf8),
                  let codeData = credential.authorizationCode, let code = String(data: codeData, encoding: .utf8),
                  let challenge else { throw APIError.invalidResponse }
            await session.signIn(provider: "apple", payload: payload(token: token, code: code, challengeId: challenge.id), identityService: service)
        } catch {
            if (error as? ASAuthorizationError)?.code != .canceled { message = "Apple sign-in could not finish. Please try again." }
        }
        challenge = try? await service.identityChallenge()
    }
    private func signInWithGoogle() async {
        guard canContinue, let clientID = googleClientID,
              let presenter = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene })
                .flatMap(\.windows).first(where: \.isKeyWindow)?.rootViewController else { return }
        busy = true; message = nil
        defer { busy = false }
        do {
            let serverID = Bundle.main.object(forInfoDictionaryKey: "GoogleServerClientID") as? String
            GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: clientID,
                serverClientID: serverID?.isEmpty == false ? serverID : nil)
            let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: presenter)
            guard let token = result.user.idToken?.tokenString else { throw APIError.invalidResponse }
            await session.signIn(provider: "google", payload: payload(token: token), identityService: service)
            // Farelin owns the session; don't retain a second provider login locally.
            GIDSignIn.sharedInstance.signOut()
        } catch {
            if (error as NSError).code != GIDSignInError.canceled.rawValue {
                message = "Google sign-in could not finish. Please try again."
            }
        }
    }
}
