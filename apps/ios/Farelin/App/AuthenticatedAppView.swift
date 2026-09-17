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
    @State private var selectedTab = FarelinTab.discover
    @State private var dashboardStore: DashboardStore
    @State private var profileStore: TravelProfileStore
    @State private var searchStore: TripSearchStore
    @State private var opportunityStore: OpportunityStore
    @State private var worldStore: MyWorldStore
    @State private var showingProfile = false
    @State private var showingAccount = false
    @State private var selectedWatchID: String?

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
        _opportunityStore = State(initialValue: OpportunityStore(
            service: apiClient,
            reauthenticate: { await session.refreshAccess() }
        ))
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
        .safeAreaInset(edge: .top) {
            if !profileStore.isComplete {
                HStack {
                    Spacer()
                    Button("Account", systemImage: "person.crop.circle") { showingAccount = true }
                        .font(.subheadline)
                }.padding(.horizontal, 24)
            }
        }
        .sheet(isPresented: $showingAccount) {
            AccountView(configuration: configuration, session: session, user: user, accountService: apiClient,
                        editProfile: { showingAccount = false })
        }
        .task { await dashboardStore.load() }
        .task { await PushNotifications.shared.restore(accountID: user.id) }
        .onChange(of: PushNotifications.shared.destination, initial: true) {
            if PushNotifications.shared.destination != nil { selectedTab = .watches }
        }
    }

    private var originLimit: Int {
        dashboardStore.dashboard?.usage.maxOriginAirports ?? 3
    }

    private var appTabs: some View {
        TabView(selection: $selectedTab) {
            DiscoverView(
                store: searchStore,
                opportunities: opportunityStore,
                originAirports: profileStore.draft?.originAirports ?? [],
                accountEmail: user.email,
                tripDetailService: apiClient,
                watchService: apiClient,
                fareService: apiClient,
                onWatchSaved: { Task { await dashboardStore.load(force: true) } },
                reauthenticate: { await session.refreshAccess() }
            )
            .tabItem { Label("Discover", systemImage: "magnifyingglass") }
            .tag(FarelinTab.discover)

            DashboardView(user: user, store: dashboardStore, openDiscover: {
                selectedTab = .discover
            }, openWatch: { id in
                selectedWatchID = id
                selectedTab = .watches
            }, openWatches: { selectedTab = .watches })
            .tabItem { Label("Today", systemImage: "sparkles") }
            .tag(FarelinTab.dashboard)

            WatchesView(store: dashboardStore, fareService: apiClient, tripDetailService: apiClient,
                        watchService: apiClient, session: session,
                        selectedWatchID: $selectedWatchID,
                        reauthenticate: { await session.refreshAccess() }) {
                selectedTab = .discover
            }
                .tabItem { Label("Watches", systemImage: "bell") }
                .tag(FarelinTab.watches)

            MyWorldView(
                store: worldStore,
                opportunities: opportunityStore,
                tripDetailService: apiClient,
                reauthenticate: { await session.refreshAccess() },
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
                accountService: apiClient,
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

struct WatchesView: View {
    let store: DashboardStore
    let fareService: any NativeFareSaving
    let tripDetailService: any TripDetailServicing
    let watchService: any WatchManagementServicing
    let session: AuthSession
    @Binding var selectedWatchID: String?
    let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    let discoverTrips: () -> Void
    @State private var pendingDeletion: SavedWatchSummary?
    @State private var savedFares: [SavedFareSummary] = []
    @State private var fareError: String?
    @State private var loadingFares = false

    var body: some View {
        NavigationStack {
            Group {
                if let watches = store.dashboard?.savedSearches, !watches.isEmpty {
                    List {
                        savedFareSection
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
                                NavigationLink("Details & history") {
                                    WatchDetailView(id: watch.id, service: watchService, tripService: tripDetailService,
                                                    session: session, dailyChecks: store.dashboard?.usage.dailyWatchChecks ?? false,
                                                    originLimit: store.dashboard?.usage.maxOriginAirports ?? 3) {
                                        Task { await store.load(force: true) }
                                    }
                                }
                                .font(.caption.weight(.semibold))
                                Text(watch.name ?? "Trip watch")
                                    .font(.headline)
                                Text(watch.routeDescription)
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
                } else if !savedFares.isEmpty {
                    List {
                        savedFareSection
                        Section("Active watches") {
                            Text("No active watches yet. Saved fares are bookmarks, not alerts.")
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                } else if store.isLoading || loadingFares {
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
                        Label("Nothing saved yet", systemImage: "bookmark.slash")
                    } description: {
                        Text(fareError ?? "Save a fare as a bookmark, or create a watch for ongoing alerts.")
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
            .navigationDestination(isPresented: Binding(
                get: { selectedWatchID != nil || PushNotifications.shared.destination != nil },
                set: { if !$0 { selectedWatchID = nil; PushNotifications.shared.destination = nil } }
            )) {
                if let id = destinationWatchID {
                    WatchDetailView(id: id, service: watchService, tripService: tripDetailService,
                                    session: session, dailyChecks: store.dashboard?.usage.dailyWatchChecks ?? false,
                                    originLimit: store.dashboard?.usage.maxOriginAirports ?? 3) {
                        Task { await store.load(force: true) }
                    }
                }
            }
            .task { await store.load() }
            .onAppear { Task { await loadSavedFares() } }
            .refreshable { await store.load(force: true); await loadSavedFares() }
            .sensoryFeedback(.success, trigger: store.completedWatchActions)
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

    private var destinationWatchID: String? {
        if case .watch(let id) = PushNotifications.shared.destination { return id }
        return selectedWatchID
    }

    @ViewBuilder
    private var savedFareSection: some View {
        if let fareError {
            Label(fareError, systemImage: "wifi.exclamationmark")
                .font(.caption).foregroundStyle(FarelinColor.coral)
        }
        if !savedFares.isEmpty {
            Section("Saved fares · not monitored") {
                ForEach(savedFares) { fare in
                    VStack(alignment: .leading, spacing: 5) {
                        HStack {
                            Text(fare.title).font(.headline)
                            Spacer()
                            Text("\(fare.currency) \(fare.observedPrice, specifier: "%.0f")")
                                .font(.subheadline.weight(.bold))
                                .foregroundStyle(FarelinColor.mint)
                        }
                        Text("\(fare.fareStatus.capitalized) fare · last observed \(String(fare.observedAt.prefix(10))) · price may change")
                            .font(.caption).foregroundStyle(.secondary)
                        if !["multi_city", "open_jaw"].contains(fare.tripType), let url = fare.checkPriceURL {
                            Link("Check final price", destination: url)
                                .font(.subheadline.weight(.semibold))
                        }
                        if let trip = fare.trip {
                            NavigationLink("View saved route") {
                                TripDetailView(trip: trip, service: tripDetailService,
                                               reauthenticate: reauthenticate, isSavedSnapshot: true)
                            }
                            .font(.subheadline.weight(.semibold))
                        } else {
                            Text("This older bookmark has no complete itinerary snapshot.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 5)
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) { Task { await deleteFare(fare) } } label: {
                            Label("Remove bookmark", systemImage: "trash")
                        }
                    }
                }
            }
        }
    }

    private func loadSavedFares() async {
        guard !loadingFares else { return }
        loadingFares = true
        fareError = nil
        defer { loadingFares = false }
        do {
            savedFares = try await fareService.savedFares()
        } catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else {
                fareError = "Sign in again to see saved fares."
                return
            }
            do { savedFares = try await fareService.savedFares() }
            catch { fareError = (error as? LocalizedError)?.errorDescription ?? "Saved fares could not load." }
        } catch {
            fareError = (error as? LocalizedError)?.errorDescription ?? "Saved fares could not load."
        }
    }

    private func deleteFare(_ fare: SavedFareSummary) async {
        do {
            try await fareService.deleteSavedFare(id: fare.id)
            savedFares.removeAll { $0.id == fare.id }
        } catch {
            fareError = (error as? LocalizedError)?.errorDescription ?? "Could not remove this fare."
        }
    }
}

private struct AccountView: View {
    let configuration: AppConfiguration
    let session: AuthSession
    let user: AuthUser
    let accountService: any NativeAccountServicing
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
                AccountControls(service: accountService, session: session, hasPassword: user.hasPassword)
                PushPreferencesSection()
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
