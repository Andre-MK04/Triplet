import SwiftUI

@main
struct FarelinApp: App {
    private let configuration: AppConfiguration
    private let apiClient: APIClient
    @State private var session: AuthSession

    init() {
        do {
            let configuration = try AppConfiguration.current()
            let apiClient = APIClient(baseURL: configuration.apiBaseURL)
            self.configuration = configuration
            self.apiClient = apiClient
            _session = State(
                initialValue: AuthSession(
                    service: apiClient,
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
            RootView(configuration: configuration, session: session, apiClient: apiClient)
        }
    }
}
