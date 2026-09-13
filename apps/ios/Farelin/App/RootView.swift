import SwiftUI

struct RootView: View {
    let configuration: AppConfiguration
    let session: AuthSession

    var body: some View {
        Group {
            switch session.state {
            case .restoring:
                RestoringSessionView()
            case .signedOut:
                AuthenticationView(configuration: configuration, session: session)
            case .signedIn(let user):
                SignedInFoundationView(configuration: configuration, session: session, user: user)
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
