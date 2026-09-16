import SwiftUI

struct RootView: View {
    let configuration: AppConfiguration
    let session: AuthSession
    let apiClient: APIClient

    var body: some View {
        Group {
            switch session.state {
            case .restoring:
                RestoringSessionView()
            case .restoreFailed:
                ContentUnavailableView {
                    Label("Your account is still saved", systemImage: "wifi.exclamationmark")
                } description: {
                    Text(session.message ?? "Reconnect to restore your Farelin session.")
                } actions: {
                    Button("Try again") { Task { await session.restore() } }
                        .buttonStyle(.borderedProminent)
                    Button("Use another account") { Task { await session.signOut() } }
                }
            case .signedOut:
                AuthenticationView(configuration: configuration, session: session, accountService: apiClient, identityService: apiClient)
            case .signedIn(let user):
                if user.isVerified {
                    AuthenticatedAppView(
                        configuration: configuration,
                        session: session,
                        user: user,
                        apiClient: apiClient
                    )
                } else {
                    SignedInFoundationView(
                        configuration: configuration,
                        session: session,
                        user: user,
                        accountService: apiClient
                    )
                }
            }
        }
        .task {
            guard session.state == .restoring else { return }
            await session.restore()
        }
        .tint(FarelinColor.mint)
    }
}

private struct RestoringSessionView: View {
    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 16) {
                Image("BrandMark")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 48, height: 48)
                    .accessibilityHidden(true)
                ProgressView("Checking your Farelin account…")
                    .foregroundStyle(.secondary)
            }
        }
    }
}
