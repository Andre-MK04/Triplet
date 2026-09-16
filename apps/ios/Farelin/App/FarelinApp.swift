import SwiftUI
@preconcurrency import GoogleSignIn

@main
struct FarelinApp: App {
    @UIApplicationDelegateAdaptor(PushAppDelegate.self) private var appDelegate
    private let configuration: AppConfiguration
    private let apiClient: APIClient
    @State private var session: AuthSession

    init() {
        do {
            let configuration = try AppConfiguration.current()
            let apiClient = APIClient(baseURL: configuration.apiBaseURL)
            self.configuration = configuration
            self.apiClient = apiClient
            let authService: any NativeAuthServicing
            let tokenStore: any RefreshTokenStoring
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("-ui-testing") {
                let isolated = UITestAuthService()
                authService = isolated; tokenStore = isolated
            } else {
                authService = apiClient
                tokenStore = KeychainRefreshTokenStore(service: configuration.environment == .staging
                    ? "com.farelin.app.staging.auth" : "com.farelin.app.auth")
            }
            #else
            authService = apiClient
            tokenStore = KeychainRefreshTokenStore(service: configuration.environment == .staging
                ? "com.farelin.app.staging.auth" : "com.farelin.app.auth")
            #endif
            let session = AuthSession(service: authService, tokenStore: tokenStore)
            _session = State(initialValue: session)
            PushNotifications.shared.configure(service: apiClient, reauthenticate: { await session.refreshAccess() })
            session.beforeSignOut = { await PushNotifications.shared.disconnect(forSignOut: true) }
        } catch {
            fatalError("Invalid non-secret app configuration: \(error.localizedDescription)")
        }
    }

    var body: some Scene {
        WindowGroup {
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("-ui-testing"),
               ProcessInfo.processInfo.arguments.contains("-ui-testing-discover") {
                UITestDiscoverScreen()
            } else {
                RootView(configuration: configuration, session: session, apiClient: apiClient)
                    .onOpenURL { url in _ = GIDSignIn.sharedInstance.handle(url) }
            }
            #else
            RootView(configuration: configuration, session: session, apiClient: apiClient)
                .onOpenURL { url in _ = GIDSignIn.sharedInstance.handle(url) }
            #endif
        }
    }
}
