import SwiftUI

enum FarelinTab: Hashable {
    case dashboard
    case discover
    case watches
    case world
    case account
}

struct AuthenticatedAppView: View {
    let configuration: AppConfiguration
    let session: AuthSession
    let user: AuthUser
    @State private var selectedTab = FarelinTab.dashboard
    @State private var dashboardStore: DashboardStore
    @State private var profileStore: TravelProfileStore
    @State private var searchStore: TripSearchStore
    @State private var showingProfile = false

    init(
        configuration: AppConfiguration,
        session: AuthSession,
        user: AuthUser,
        apiClient: APIClient
    ) {
        self.configuration = configuration
        self.session = session
        self.user = user
        _dashboardStore = State(
            initialValue: DashboardStore(
                service: apiClient,
                reauthenticate: { await session.refreshAccess() }
            )
        )
        _profileStore = State(
            initialValue: TravelProfileStore(
                service: apiClient,
                reauthenticate: { await session.refreshAccess() }
            )
        )
        _searchStore = State(
            initialValue: TripSearchStore(
                service: apiClient,
                reauthenticate: { await session.refreshAccess() }
            )
        )
    }

    var body: some View {
        Group {
            if profileStore.draft == nil {
                profileLoadingState
            } else if !profileStore.isComplete {
                TravelProfileView(store: profileStore, originLimit: originLimit)
            } else {
                appTabs
            }
        }
        .task { await profileStore.load() }
        .task { await dashboardStore.load() }
    }

    private var originLimit: Int {
        dashboardStore.dashboard?.usage.maxOriginAirports ?? 3
    }

    private var appTabs: some View {
        TabView(selection: $selectedTab) {
            DashboardView(user: user, store: dashboardStore) {
                selectedTab = .discover
            }
            .tabItem { Label("Today", systemImage: "sparkles") }
            .tag(FarelinTab.dashboard)

            DiscoverView(
                store: searchStore,
                originAirports: profileStore.draft?.originAirports ?? []
            )
            .tabItem { Label("Discover", systemImage: "magnifyingglass") }
            .tag(FarelinTab.discover)

            WatchesView(store: dashboardStore)
                .tabItem { Label("Watches", systemImage: "bell") }
                .tag(FarelinTab.watches)

            FeaturePreviewView(
                title: "My World",
                headline: "The places that made you.",
                detail: "Your interactive globe and travel history will live here.",
                symbol: "globe.europe.africa.fill"
            )
            .tabItem { Label("My World", systemImage: "globe.europe.africa") }
            .tag(FarelinTab.world)

            AccountView(
                configuration: configuration,
                session: session,
                user: user,
                editProfile: { showingProfile = true }
            )
                .tabItem { Label("Account", systemImage: "person.crop.circle") }
                .tag(FarelinTab.account)
        }
        .tint(FarelinColor.mint)
        .sheet(isPresented: $showingProfile) {
            TravelProfileView(store: profileStore, originLimit: originLimit)
        }
    }

    private var profileLoadingState: some View {
        VStack(spacing: 16) {
            if profileStore.isLoading {
                ProgressView("Loading your travel profile…")
            } else {
                Image(systemName: "person.crop.circle.badge.exclamationmark")
                    .font(.system(size: 36))
                    .foregroundStyle(FarelinColor.coral)
                Text("Your travel profile could not load")
                    .font(.headline)
                Text(profileStore.errorMessage ?? "Check your connection and try again.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                Button("Try again") { Task { await profileStore.load() } }
                    .buttonStyle(.borderedProminent)
            }
        }
        .padding(24)
    }
}

private struct FeaturePreviewView: View {
    let title: String
    let headline: String
    let detail: String
    let symbol: String

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 18) {
                Image(systemName: symbol)
                    .font(.system(size: 38, weight: .medium))
                    .foregroundStyle(FarelinColor.mint)
                Text(headline)
                    .font(.system(size: 32, weight: .bold, design: .rounded))
                    .tracking(-0.7)
                Text(detail)
                    .font(.body)
                    .foregroundStyle(.secondary)
                    .lineSpacing(4)
                Spacer()
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(24)
            .background(Color(.systemBackground))
            .navigationTitle(title)
        }
    }
}

private struct WatchesView: View {
    let store: DashboardStore

    var body: some View {
        NavigationStack {
            Group {
                if let watches = store.dashboard?.savedSearches, !watches.isEmpty {
                    List(watches) { watch in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(watch.name ?? "Trip watch")
                                .font(.headline)
                            Text("\(watch.originAirports.joined(separator: " + ")) → \(watch.destinationAirports?.joined(separator: " + ") ?? "Anywhere")")
                                .font(.subheadline.monospaced())
                            Text("\(watch.frequency.capitalized) · up to €\(watch.maxBudget, specifier: "%.0f")")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 5)
                    }
                } else if store.isLoading {
                    ProgressView("Loading watches…")
                } else {
                    ContentUnavailableView(
                        "No saved watches",
                        systemImage: "bell.slash",
                        description: Text("Saved searches from Farelin will appear here.")
                    )
                }
            }
            .navigationTitle("Watches")
            .task { await store.load() }
            .refreshable { await store.load(force: true) }
        }
    }
}

private struct AccountView: View {
    let configuration: AppConfiguration
    let session: AuthSession
    let user: AuthUser
    let editProfile: () -> Void

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: 14) {
                        Image("BrandMark")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 42, height: 42)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(user.displayName ?? "Farelin traveller")
                                .font(.headline)
                            Text(user.email)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                Section("App") {
                    Button("Travel profile", systemImage: "slider.horizontal.3", action: editProfile)
                    LabeledContent("Environment", value: configuration.environment.rawValue.capitalized)
                    LabeledContent("Version", value: "0.1.0")
                }
                Section {
                    Button("Sign out", role: .destructive) {
                        Task { await session.signOut() }
                    }
                    .disabled(session.isWorking)
                }
            }
            .navigationTitle("Account")
        }
    }
}
