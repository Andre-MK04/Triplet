#if DEBUG
import Foundation
import SwiftUI

/// Deterministic signed-out UI tests. Never compiled into a Release archive;
/// never signs in, issues tokens, deletes Keychain entries, or spends API credit.
actor UITestAuthService: NativeAuthServicing, RefreshTokenStoring {
    func load() -> String? { nil }
    func save(_ token: String) {}
    func clear() {}
    func legalVersions() -> LegalVersions { LegalVersions(termsVersion: "ui-test", privacyVersion: "ui-test") }
    func nativeLogin(email: String, password: String) throws -> NativeAuthTokens { throw APIError.unavailable }
    func nativeSignup(email: String, password: String, displayName: String?, legal: LegalVersions) throws -> NativeAuthTokens { throw APIError.unavailable }
    func nativeRefresh(refreshToken: String) throws -> NativeAuthTokens { throw APIError.unauthorized }
    func nativeLogout(refreshToken: String) {}
    func currentUser() throws -> AuthUser { throw APIError.unauthorized }
    func requestVerificationCode() throws -> VerificationDelivery { throw APIError.unavailable }
    func confirmVerificationCode(_ code: String) throws -> AuthUser { throw APIError.unavailable }
    func setAccessToken(_ token: String?) {}
}

/// Isolated presentation fixture, not an account or a real fare source. All
/// services are local and this screen is absent from every Release build.
@MainActor
struct UITestDiscoverScreen: View {
    private let service: UITestDiscoverService
    @State private var store: TripSearchStore
    @State private var opportunities: OpportunityStore

    init() {
        let service = UITestDiscoverService()
        self.service = service
        _store = State(initialValue: TripSearchStore(service: service))
        _opportunities = State(initialValue: OpportunityStore(service: service))
    }

    var body: some View {
        TabView {
        DiscoverView(store: store, opportunities: opportunities, originAirports: ["CPH"],
                     accountEmail: "ui-test@example.invalid", tripDetailService: service,
                     watchService: service, fareService: service, onWatchSaved: {}, reauthenticate: nil)
            .tint(FarelinColor.action)
            .tabItem { Label("Discover", systemImage: "magnifyingglass") }
            Text("UI test").tabItem { Label("Today", systemImage: "sparkles") }
            Text("UI test").tabItem { Label("Watches", systemImage: "bell") }
            Text("UI test").tabItem { Label("My World", systemImage: "globe") }
            Text("UI test").tabItem { Label("Account", systemImage: "person") }
        }
        .preferredColorScheme(ProcessInfo.processInfo.arguments.contains("-ui-testing-dark") ? .dark : nil)
        .dynamicTypeSize(ProcessInfo.processInfo.arguments.contains("-ui-testing-large-text") ? .accessibility3 : .large)
    }
}

@MainActor
struct UITestTodayScreen: View {
    let session: AuthSession
    @State private var store = DashboardStore(service: UITestDiscoverService())
    @State private var tab = 0
    @State private var watchID: String?
    private let service = UITestDiscoverService()

    var body: some View {
        TabView(selection: $tab) {
            DashboardView(user: UITestDiscoverService.dashboardUser, store: store,
                openDiscover: { tab = 2 }, openWatch: { watchID = $0; tab = 1 }, openWatches: { tab = 1 })
                .tabItem { Label("Today", systemImage: "sparkles") }.tag(0)
            WatchesView(store: store, fareService: service, tripDetailService: service,
                watchService: service, session: session, selectedWatchID: $watchID,
                reauthenticate: nil, discoverTrips: { tab = 2 })
                .tabItem { Label("Watches", systemImage: "bell") }.tag(1)
            Text("Discover trips").accessibilityIdentifier("today-discover-destination")
                .tabItem { Label("Discover", systemImage: "magnifyingglass") }.tag(2)
        }
        .tint(FarelinColor.action)
        .preferredColorScheme(ProcessInfo.processInfo.arguments.contains("-ui-testing-dark") ? .dark : .light)
        .dynamicTypeSize(ProcessInfo.processInfo.arguments.contains("-ui-testing-large-text") ? .accessibility3 : .large)
    }
}

private actor UITestDiscoverService: TripSearchServicing, OpportunityServicing,
    TripDetailServicing, NativeWatchCreating, NativeFareSaving, DashboardServicing, WatchManagementServicing {
    static let dashboardUser = AuthUser(id: "ui-test", email: "ui-test@example.invalid",
        displayName: "Traveler", isVerified: true, createdAt: "2026-09-17", hasPassword: true, connectedProviders: [])
    func dashboard() -> DashboardResponse {
        let usage = DashboardUsage(aiSearchesThisMonth: 1, aiSearchesPerMonth: 3, activeSavedSearches: 1,
            savedSearchLimit: 1, maxOriginAirports: 3, dailyWatchChecks: false, unlimited: false)
        let watches = ProcessInfo.processInfo.arguments.contains("-ui-testing-empty") ? [] : [testWatch]
        return DashboardResponse(user: Self.dashboardUser,
            billing: DashboardBilling(plan: "free", subscriptionStatus: "none", trialDaysRemaining: 0,
                usage: usage, canStartTrial: true, canUpgrade: true, canManageBilling: false),
            usage: usage, savedSearches: watches,
            savedSearchSummary: SavedSearchSummary(total: watches.count, active: watches.filter(\.isActive).count))
    }
    private var testWatch: SavedWatchSummary {
        SavedWatchSummary(id: "nordic", name: "Nordic weekends", originAirports: ["CPH"], destinationAirports: ["ARN"],
            startDate: "2099-10-01", endDate: "2099-12-01", maxBudget: 200, frequency: "weekly",
            isActive: !ProcessInfo.processInfo.arguments.contains("-ui-testing-paused"),
            lastCheckedAt: "2026-09-17T12:00:00Z", lastNotifiedAt: nil, lastBestPrice: 125)
    }
    func pauseWatch(id: String) throws -> SavedWatchSummary { throw APIError.unavailable }
    func resumeWatch(id: String) throws -> SavedWatchSummary { throw APIError.unavailable }
    func deleteWatch(id: String) throws { throw APIError.unavailable }
    func watch(id: String) -> NativeWatchDetail {
        NativeWatchDetail(id: id, name: "Nordic weekends", originAirports: ["CPH"], destinationAirports: ["ARN"],
            destinationCountries: [], destinationRegions: [], destinationContinents: [], tripPlan: "return",
            routeStops: nil, returnOriginAirports: nil, startDate: "2099-10-01", endDate: "2099-12-01",
            minTripLengthDays: 3, maxTripLengthDays: 5, maxBudget: 200, maxGroundTransferHours: 4,
            frequency: "weekly", triggerMode: "any", directOnly: false, includeBaggage: false, isActive: testWatch.isActive)
    }
    func watchInsights(id: String) -> NativeWatchInsights {
        NativeWatchInsights(totalChecks: 1, notificationCount: 0, lowestObservedPrice: 125, history: [], deliveries: [])
    }
    func updateWatch(id: String, update: NativeWatchUpdate) throws -> NativeWatchDetail { throw APIError.unavailable }
    func previewWatch(id: String) -> NativeWatchPreview { NativeWatchPreview(matchingTrips: []) }
    func updateWatchRoute(id: String, update: NativeWatchRouteUpdate) throws -> NativeWatchDetail { throw APIError.unavailable }
    func watchAirports(query: String) -> [AirportResult] { [] }
    func watchPlaces(query: String) -> [FlightPlaceResult] { [] }
    func searchTrips(_ request: FarelinAISearchRequest) throws -> FarelinAISearchResponse { throw APIError.unavailable }
    func searchPlaces(_ query: String) -> [FlightPlaceResult] { [] }
    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse {
        try await Task.sleep(for: .milliseconds(150))
        let trips = ProcessInfo.processInfo.arguments.contains("-ui-testing-results")
            ? (0..<6).map { Self.trip(index: $0) } : []
        let parsed = trips.isEmpty ? nil : ParsedTripSearch(originAirports: ["CPH"], destinationAirports: nil,
            destinationCountries: [], destinationRegions: [], destinationContinents: [],
            startDate: "2026-10-07", endDate: "2026-12-15", minTripLengthDays: 4,
            maxTripLengthDays: 7, maxBudget: 400, tripPlan: "return", travelStyles: ["food"],
            routeStops: nil, returnOriginAirports: nil, maxGroundTransferHours: 4, directOnly: false, includeBaggage: false)
        return FarelinAISearchResponse(message: trips.isEmpty ? "" : "Found six observed trip options from your structured search.", parsedRequest: parsed, trips: trips,
            relaxationNote: nil, missingFields: [], providerMetadata: nil, sourceMap: nil, hardBudgetApplied: nil)
    }
    func opportunities() -> NativeOpportunityFeed {
        NativeOpportunityFeed(trips: [], originAirports: ["CPH"], source: "ui_test", isReady: true, isStale: false)
    }
    func tripSuggestion(id: String) throws -> TripSuggestionResponse { throw APIError.unavailable }
    func generateItinerary(suggestionID: String) throws -> ItineraryGenerationResponse { throw APIError.unavailable }
    func createWatch(_ request: NativeSavedWatchRequest) throws -> SavedWatchSummary { throw APIError.unavailable }
    func savedFares() -> [SavedFareSummary] { [] }
    func saveFare(suggestionId: String) throws -> SavedFareSummary { throw APIError.unavailable }
    func deleteSavedFare(id: String) throws { throw APIError.unavailable }

    private static func trip(index: Int) -> SearchTrip {
        let out = SearchFlight(id: "out-\(index)", origin: "CPH", destination: "ARN",
            departureDateTime: "2026-10-16T09:00:00Z", arrivalDateTime: "2026-10-16T10:15:00Z",
            airline: "SK", price: 105, currency: "EUR", bookingUrl: "https://example.invalid/check",
            deepLink: nil, affiliateUrl: nil, stops: 0, durationMinutes: 75, isLive: false,
            confidenceLevel: "indicative", observedAt: "2026-09-14T10:00:00Z")
        let back = SearchFlight(id: "back-\(index)", origin: "ARN", destination: "CPH",
            departureDateTime: "2026-10-18T19:00:00Z", arrivalDateTime: "2026-10-18T20:15:00Z",
            airline: "SK", price: 105, currency: "EUR", bookingUrl: "https://example.invalid/check",
            deepLink: nil, affiliateUrl: nil, stops: 0, durationMinutes: 75, isLive: false,
            confidenceLevel: "indicative", observedAt: "2026-09-14T10:00:00Z")
        return SearchTrip(id: "ui-trip-\(index)", tripType: "same_city", outboundFlight: out,
            returnFlight: back, groundTransfer: nil, segments: nil, stays: nil, flightCost: nil,
            groundEstimate: nil, transportTotalEstimate: nil, durationMatch: nil, price: nil,
            totalPrice: 210, tripLengthDays: 2, nights: 2, score: 80, dealScore: 80, fitScore: 85,
            suggestionId: nil, fareKind: "round_trip_bundle", explanation: "UI test fixture.",
            warnings: [], tags: ["food"], bookingUrl: "https://example.invalid/check",
            provider: "ui_test", destination: SearchDestination(code: "STO", city: "Stockholm",
                country: "Sweden", countryCode: "SE", continent: "Europe"))
    }
}
#endif
