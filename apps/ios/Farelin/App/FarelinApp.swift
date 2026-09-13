import SwiftUI

@main
struct FarelinApp: App {
    private let configuration: AppConfiguration
    @State private var session: AuthSession

    init() {
        do {
            let configuration = try AppConfiguration.current()
            self.configuration = configuration
            _session = State(
                initialValue: AuthSession(
                    service: APIClient(baseURL: configuration.apiBaseURL),
                    tokenStore: KeychainRefreshTokenStore(
                        service: configuration.environment == .staging
                            ? "com.farelin.app.staging.auth"
                            : "com.farelin.app.auth"
                    )
                )
            )
        } catch {
            fatalError("Invalid non-secret app configuration: \(error.localizedDescription)")
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView(configuration: configuration, session: session)
        }
    }
}
