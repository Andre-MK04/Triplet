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
        DiscoverView(store: store, opportunities: opportunities, originAirports: ["CPH"],
                     accountEmail: "ui-test@example.invalid", tripDetailService: service,
                     watchService: service, fareService: service, onWatchSaved: {}, reauthenticate: nil)
            .tint(FarelinColor.action)
    }
}

private actor UITestDiscoverService: TripSearchServicing, OpportunityServicing,
    TripDetailServicing, NativeWatchCreating, NativeFareSaving {
    func searchTrips(_ request: FarelinAISearchRequest) throws -> FarelinAISearchResponse { throw APIError.unavailable }
    func searchPlaces(_ query: String) -> [FlightPlaceResult] { [] }
    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse {
        try await Task.sleep(for: .milliseconds(150))
        return FarelinAISearchResponse(message: "", parsedRequest: nil, trips: [],
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
}
#endif
