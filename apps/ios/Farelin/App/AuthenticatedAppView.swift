import CoreLocation
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
    let apiClient: APIClient
    @State private var selectedTab = FarelinTab.dashboard
    @State private var dashboardStore: DashboardStore
    @State private var profileStore: TravelProfileStore
    @State private var searchStore: TripSearchStore
    @State private var worldStore: MyWorldStore
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
        self.apiClient = apiClient
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
        _worldStore = State(
            initialValue: MyWorldStore(
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
                originAirports: profileStore.draft?.originAirports ?? [],
                accountEmail: user.email,
                tripDetailService: apiClient,
                watchService: apiClient,
                onWatchSaved: { Task { await dashboardStore.load(force: true) } },
                reauthenticate: { await session.refreshAccess() }
            )
            .tabItem { Label("Discover", systemImage: "magnifyingglass") }
            .tag(FarelinTab.discover)

            WatchesView(store: dashboardStore) {
                selectedTab = .discover
            }
                .tabItem { Label("Watches", systemImage: "bell") }
                .tag(FarelinTab.watches)

            MyWorldView(
                store: worldStore,
                homeCoordinate: homeCoordinate,
                isActive: selectedTab == .world,
                planTrip: { country in
                    searchStore.query = "Find me a trip to \(country.name)"
                    selectedTab = .discover
                }
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

    private var homeCoordinate: CLLocationCoordinate2D? {
        guard
            let latitude = profileStore.draft?.baseLatitude,
            let longitude = profileStore.draft?.baseLongitude
        else { return nil }
        return CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
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

private struct WatchesView: View {
    let store: DashboardStore
    let discoverTrips: () -> Void
    @State private var pendingDeletion: SavedWatchSummary?

    var body: some View {
        NavigationStack {
            Group {
                if let watches = store.dashboard?.savedSearches, !watches.isEmpty {
                    List {
                        if let error = store.errorMessage {
                            Label(error, systemImage: "exclamationmark.triangle")
                                .foregroundStyle(FarelinColor.coral)
                                .font(.subheadline)
                        }
                        ForEach(watches) { watch in
                        HStack(spacing: 12) {
                            Circle()
                                .fill(watch.isActive ? FarelinColor.mint : Color.secondary.opacity(0.45))
                                .frame(width: 9, height: 9)
                            VStack(alignment: .leading, spacing: 6) {
                                Text(watch.name ?? "Trip watch")
                                    .font(.headline)
                                Text("\(watch.originAirports.joined(separator: " + ")) → \(watch.destinationAirports?.joined(separator: " + ") ?? "Anywhere")")
                                    .font(.subheadline.monospaced())
                                Text("\(watch.isActive ? "Active" : "Paused") · \(watch.frequency.capitalized) · up to €\(watch.maxBudget, specifier: "%.0f")")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            if store.workingWatchID == watch.id {
                                ProgressView().controlSize(.small)
                            } else {
                                Menu {
                                    Button(watch.isActive ? "Pause watch" : "Resume watch", systemImage: watch.isActive ? "pause" : "play") {
                                        Task { await store.setWatch(watch, active: !watch.isActive) }
                                    }
                                    Button("Delete watch", systemImage: "trash", role: .destructive) {
                                        pendingDeletion = watch
                                    }
                                } label: {
                                    Image(systemName: "ellipsis.circle")
                                        .font(.title3)
                                        .foregroundStyle(.secondary)
                                }
                                .accessibilityLabel("Actions for \(watch.name ?? "trip watch")")
                            }
                        }
                        .padding(.vertical, 5)
                        .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                            Button(role: .destructive) { pendingDeletion = watch } label: {
                                Label("Delete", systemImage: "trash")
                            }
                            Button { Task { await store.setWatch(watch, active: !watch.isActive) } } label: {
                                Label(watch.isActive ? "Pause" : "Resume", systemImage: watch.isActive ? "pause" : "play")
                            }
                            .tint(FarelinColor.mint)
                        }
                        }
                    }
                } else if store.isLoading {
                    ProgressView("Loading watches…")
                } else if let error = store.errorMessage {
                    ContentUnavailableView {
                        Label("Watches could not load", systemImage: "wifi.exclamationmark")
                    } description: {
                        Text(error)
                    } actions: {
                        Button("Try again") { Task { await store.load(force: true) } }
                            .buttonStyle(.borderedProminent)
                    }
                } else {
                    ContentUnavailableView {
                        Label("No saved watches", systemImage: "bell.slash")
                    } description: {
                        Text("Find a trip you like, then ask Farelin to keep watching fares from your airports.")
                    } actions: {
                        Button("Discover trips", action: discoverTrips)
                            .buttonStyle(.borderedProminent)
                    }
                }
            }
            .navigationTitle("Watches")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Discover", systemImage: "magnifyingglass", action: discoverTrips)
                }
            }
            .task { await store.load() }
            .refreshable { await store.load(force: true) }
            .alert("Delete this watch?", isPresented: Binding(
                get: { pendingDeletion != nil },
                set: { if !$0 { pendingDeletion = nil } }
            )) {
                Button("Cancel", role: .cancel) { pendingDeletion = nil }
                Button("Delete", role: .destructive) {
                    guard let watch = pendingDeletion else { return }
                    pendingDeletion = nil
                    Task { await store.deleteWatch(watch) }
                }
            } message: {
                Text("Farelin will stop checking this search. This cannot be undone.")
            }
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
                    LabeledContent("Email", value: user.isVerified ? "Confirmed" : "Not confirmed")
                    LabeledContent("Environment", value: configuration.environment.rawValue.capitalized)
                    LabeledContent("Version", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Development")
                }
                Section("Help & privacy") {
                    Link("Contact Farelin", destination: URL(string: "https://www.farelin.com/contact")!)
                    Link("Privacy policy", destination: URL(string: "https://www.farelin.com/privacy")!)
                    Link("Terms of service", destination: URL(string: "https://www.farelin.com/terms")!)
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
