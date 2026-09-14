import Foundation
import Observation

struct FarelinAISearchRequest: Encodable, Sendable, Equatable {
    let message: String
    let originAirports: [String]
}

struct FarelinAISearchResponse: Decodable, Sendable {
    let message: String
    let parsedRequest: ParsedTripSearch?
    let trips: [SearchTrip]
    let relaxationNote: String?
    let missingFields: [String]
    let providerMetadata: SearchProviderMetadata?
    let sourceMap: [String: String]?
    let hardBudgetApplied: Bool?
}

struct ParsedTripSearch: Decodable, Sendable {
    let originAirports: [String]
    let destinationAirports: [String]?
    let destinationCountries: [String]
    let destinationRegions: [String]
    let destinationContinents: [String]
    let startDate: String
    let endDate: String
    let minTripLengthDays: Int
    let maxTripLengthDays: Int
    let maxBudget: Double
    let tripPlan: String
    let travelStyles: [String]?
}

struct FlightPlaceResult: Decodable, Identifiable, Hashable, Sendable {
    var id: String { "\(kind):\(code)" }
    let code: String
    let kind: String
    let name: String
    let subtitle: String
    let city: String?
    let countryCode: String?
    let countryName: String?
    let continent: String?
    let searchCodes: [String]
}

struct FarelinAdvancedSearchRequest: Encodable, Sendable, Equatable {
    let originAirports: [String]?
    let destinationAirports: [String]?
    let destinationCountries: [String]?
    let destinationRegions: [String]?
    let destinationContinents: [String]?
    let returnOriginAirports: [String]?
    let startDate: String?
    let endDate: String?
    let minTripLengthDays: Int?
    let maxTripLengthDays: Int?
    let maxBudget: Double?
    let maxGroundTransferHours: Double?
    let tripPlan: String?
    let routeStops: [String]?
    let directOnly: Bool?
    let includeBaggage: Bool?
    let travelStyles: [String]?
}

struct AdvancedSearchDraft: Equatable, Sendable {
    var useProfileOrigins = true
    var selectedOrigins: [String] = []
    var destinations: [FlightPlaceResult] = []
    var useProfileDates = true
    var startDate = Calendar.current.date(byAdding: .day, value: 21, to: .now) ?? .now
    var endDate = Calendar.current.date(byAdding: .day, value: 90, to: .now) ?? .now
    var useProfileTripLength = true
    var minTripLengthDays = 3
    var maxTripLengthDays = 8
    var budgetText = ""
    var tripPlan = "return"
    var travelStyles: [String] = []
    var directPreference = "profile"
    var baggagePreference = "profile"
    var maxGroundTransferHours = 4.0
}

struct SearchProviderMetadata: Decodable, Sendable {
    let providerUsed: String?
    let providerName: String?
    let liveProviderAttempted: Bool
    let liveProviderSucceeded: Bool
    let cachedResultsUsed: Bool
    let cachedResultsStale: Bool
    let providerWarnings: [String]
}

struct SearchFlight: Decodable, Sendable {
    let id: String
    let origin: String
    let destination: String
    let departureDateTime: String
    let arrivalDateTime: String
    let airline: String
    let price: Double
    let currency: String
    let bookingUrl: String?
    let deepLink: String?
    let affiliateUrl: String?
    let stops: Int?
    let durationMinutes: Int?
    let isLive: Bool
    let confidenceLevel: String
    let observedAt: String?
}

struct SearchPriceInfo: Decodable, Sendable {
    let amount: Double
    let currency: String
    let kind: String
    let source: String
    let isLive: Bool
    let isEstimate: Bool
    let observedAt: String?
    let ageHours: Double?
    let freshness: String
    let legCount: Int
}

struct SearchGroundTransfer: Decodable, Sendable {
    let fromAirport: String
    let toAirport: String
    let fromCity: String
    let toCity: String
    let durationHours: Double
    let estimatedCost: Double
    let mode: String
}

struct SearchDestination: Decodable, Sendable {
    let code: String
    let city: String
    let country: String
    let countryCode: String
    let continent: String?
}

struct SearchTrip: Decodable, Identifiable, Sendable {
    let id: String
    let tripType: String
    let outboundFlight: SearchFlight
    let returnFlight: SearchFlight
    let groundTransfer: SearchGroundTransfer?
    let price: SearchPriceInfo?
    let totalPrice: Double
    let tripLengthDays: Int
    let nights: Int
    let score: Int
    let dealScore: Int
    let fitScore: Int?
    let suggestionId: String?
    let fareKind: String
    let explanation: String
    let warnings: [String]
    let tags: [String]
    let bookingUrl: String?
    let provider: String?
    let destination: SearchDestination?

    var routeTitle: String {
        switch tripType {
        case "open_jaw":
            "\(outboundFlight.origin) → \(outboundFlight.destination) / \(returnFlight.origin) → \(returnFlight.destination)"
        case "multi_city":
            "\(outboundFlight.origin) → \(destination?.city ?? outboundFlight.destination) → \(returnFlight.destination)"
        default:
            "\(outboundFlight.origin) → \(destination?.city ?? outboundFlight.destination)"
        }
    }

    var tripTypeLabel: String {
        switch tripType {
        case "open_jaw": "Open-jaw"
        case "multi_city": "Multi-city"
        default: "Return"
        }
    }

    var checkPriceURL: URL? {
        [bookingUrl, outboundFlight.bookingUrl, outboundFlight.deepLink, outboundFlight.affiliateUrl]
            .compactMap { $0 }
            .compactMap(URL.init(string:))
            .first { $0.scheme == "https" }
    }
}

struct TripSuggestionResponse: Decodable, Sendable {
    let id: String
    let title: String
    let tripType: String
    let createdAt: String?
    let expiresAt: String?
    let dealScore: Int
    let fitScore: Int?
    let trip: SearchTrip
    let itinerary: ItineraryPlan?
    let disclaimer: String
}

struct ItineraryPlan: Decodable, Sendable, Equatable {
    let summary: String
    let days: [ItineraryDay]
    let gettingAround: String?
    let extraCostEstimate: String?
    let disclaimers: [String]
    let generatedAt: String?
}

struct ItineraryDay: Decodable, Sendable, Equatable {
    let label: String
    let items: [ItineraryItem]
}

struct ItineraryItem: Decodable, Sendable, Equatable {
    let partOfDay: String
    let title: String
    let description: String
    let category: String
    let estimatedCost: String
}

struct ItineraryGenerationResponse: Decodable, Sendable {
    let itinerary: ItineraryPlan
    let cached: Bool
}

protocol TripSearchServicing: Sendable {
    func searchTrips(_ request: FarelinAISearchRequest) async throws -> FarelinAISearchResponse
    func advancedSearch(_ request: FarelinAdvancedSearchRequest) async throws -> FarelinAISearchResponse
    func searchPlaces(_ query: String) async throws -> [FlightPlaceResult]
}

protocol TripDetailServicing: Sendable {
    func tripSuggestion(id: String) async throws -> TripSuggestionResponse
    func generateItinerary(suggestionID: String) async throws -> ItineraryGenerationResponse
}

@MainActor
@Observable
final class TripSearchStore {
    var query = ""
    var advanced = AdvancedSearchDraft()
    var placeQuery = ""
    private(set) var response: FarelinAISearchResponse?
    private(set) var placeResults: [FlightPlaceResult] = []
    private(set) var isSearchingPlaces = false
    private(set) var isSearching = false
    private(set) var progressMessage = "Understanding your request…"
    private(set) var errorMessage: String?

    private let service: any TripSearchServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    private var activeSearchTask: Task<Void, Never>?

    init(
        service: any TripSearchServicing,
        reauthenticate: (@MainActor @Sendable () async -> Bool)? = nil
    ) {
        self.service = service
        self.reauthenticate = reauthenticate
    }

    func useExample(_ example: String) {
        query = example
        errorMessage = nil
    }

    func searchPlaces() async {
        let term = placeQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard term.count >= 2 else {
            placeResults = []
            return
        }
        isSearchingPlaces = true
        defer { isSearchingPlaces = false }
        do {
            let matches = try await service.searchPlaces(term)
            guard term == placeQuery.trimmingCharacters(in: .whitespacesAndNewlines) else { return }
            placeResults = matches.filter { !advanced.destinations.contains($0) }
        } catch {
            placeResults = []
            errorMessage = readable(error)
        }
    }

    func addDestination(_ place: FlightPlaceResult) {
        let destinationLimit = advanced.tripPlan == "open_jaw" ? 2 : 6
        guard advanced.destinations.count < destinationLimit, !advanced.destinations.contains(place) else { return }
        advanced.destinations.append(place)
        placeQuery = ""
        placeResults = []
        errorMessage = nil
    }

    func removeDestination(_ place: FlightPlaceResult) {
        advanced.destinations.removeAll { $0 == place }
    }

    func setUseProfileOrigins(_ useProfile: Bool, profileOrigins: [String]) {
        advanced.useProfileOrigins = useProfile
        if !useProfile, advanced.selectedOrigins.isEmpty {
            advanced.selectedOrigins = profileOrigins
        }
    }

    func toggleOrigin(_ code: String) {
        if advanced.selectedOrigins.contains(code) {
            advanced.selectedOrigins.removeAll { $0 == code }
        } else {
            advanced.selectedOrigins.append(code)
        }
    }

    func toggleTravelStyle(_ style: String) {
        if advanced.travelStyles.contains(style) {
            advanced.travelStyles.removeAll { $0 == style }
        } else {
            advanced.travelStyles.append(style)
        }
    }

    func resetAdvancedOverrides() {
        advanced = AdvancedSearchDraft()
        placeQuery = ""
        placeResults = []
        response = nil
        errorMessage = nil
    }

    /// Claims the submission synchronously before starting any asynchronous work.
    /// This prevents rapid taps from creating multiple metered AI searches.
    func submit(origins: [String]) {
        guard activeSearchTask == nil, let request = beginSearch(origins: origins) else { return }

        activeSearchTask = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.performSearch(request)
            self.activeSearchTask = nil
        }
    }

    func search(origins: [String]) async {
        guard let request = beginSearch(origins: origins) else { return }
        await performSearch(request)
    }

    func submitAdvanced(profileOrigins: [String]) {
        guard activeSearchTask == nil, let request = beginAdvancedSearch(profileOrigins: profileOrigins) else { return }

        activeSearchTask = Task { @MainActor [weak self] in
            guard let self else { return }
            await self.performAdvancedSearch(request)
            self.activeSearchTask = nil
        }
    }

    func searchAdvanced(profileOrigins: [String]) async {
        guard let request = beginAdvancedSearch(profileOrigins: profileOrigins) else { return }
        await performAdvancedSearch(request)
    }

    private func beginSearch(origins: [String]) -> FarelinAISearchRequest? {
        let message = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard message.count >= 8 else {
            errorMessage = "Describe the trip you want in a little more detail."
            return nil
        }
        guard !origins.isEmpty else {
            errorMessage = "Add at least one origin airport to your travel profile first."
            return nil
        }
        guard !isSearching else { return nil }

        isSearching = true
        response = nil
        errorMessage = nil
        progressMessage = "Understanding your request…"
        return FarelinAISearchRequest(message: message, originAirports: origins)
    }

    private func performSearch(_ request: FarelinAISearchRequest) async {
        let progress = startProgressMessages()
        defer {
            progress.cancel()
            isSearching = false
        }

        do {
            response = try await authenticated {
                try await self.service.searchTrips(request)
            }
        } catch {
            errorMessage = readable(error)
        }
    }

    private func beginAdvancedSearch(profileOrigins: [String]) -> FarelinAdvancedSearchRequest? {
        guard !isSearching else { return nil }
        let origins = advanced.useProfileOrigins ? nil : advanced.selectedOrigins
        if !advanced.useProfileOrigins, origins?.isEmpty != false {
            errorMessage = "Keep at least one origin airport for this search."
            return nil
        }
        if advanced.useProfileOrigins, profileOrigins.isEmpty {
            errorMessage = "Add at least one origin airport to your travel profile first."
            return nil
        }
        if !advanced.useProfileDates, advanced.endDate < advanced.startDate {
            errorMessage = "The end of your date window must be after its start."
            return nil
        }
        if !advanced.useProfileTripLength, advanced.maxTripLengthDays < advanced.minTripLengthDays {
            errorMessage = "Maximum trip length must be at least the minimum."
            return nil
        }
        let budgetText = advanced.budgetText
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: ",", with: ".")
        let budget = budgetText.isEmpty ? nil : Double(budgetText)
        if !budgetText.isEmpty, budget == nil || budget! < 20 || budget! > 5000 {
            errorMessage = "Enter a flight budget between €20 and €5,000, or leave it blank."
            return nil
        }

        let tripPlan = advanced.tripPlan == "profile" ? nil : advanced.tripPlan
        let routePlaces = advanced.destinations.filter { $0.kind == "city" || $0.kind == "airport" }
        if tripPlan == "open_jaw" && routePlaces.count != 2 {
            errorMessage = "Add exactly two cities or airports: where you land, then where you fly home from."
            return nil
        }
        if tripPlan == "open_jaw" && routePlaces.count != advanced.destinations.count {
            errorMessage = "Open-jaw trips need two specific cities or airports rather than regions or countries."
            return nil
        }
        if tripPlan == "multi_city" && routePlaces.count < 2 {
            errorMessage = "Add at least two cities or airports in travel order for a multi-city trip."
            return nil
        }
        if tripPlan == "multi_city" && routePlaces.count != advanced.destinations.count {
            errorMessage = "Multi-city routes need specific cities or airports rather than regions or countries."
            return nil
        }

        let scopedDestinations = tripPlan == "open_jaw" ? [] : advanced.destinations
        let airports = scopedDestinations
            .filter { $0.kind == "city" || $0.kind == "airport" }
            .map(\.code)
        let countries = scopedDestinations.filter { $0.kind == "country" }.map(\.code)
        let regions = scopedDestinations.filter { $0.kind == "region" }.map(\.code)
        let continents = scopedDestinations.filter { $0.kind == "continent" }.map(\.code)

        isSearching = true
        response = nil
        errorMessage = nil
        progressMessage = "Resolving your profile defaults…"
        return FarelinAdvancedSearchRequest(
            originAirports: origins,
            destinationAirports: tripPlan == "open_jaw" ? [routePlaces[0].code] : (airports.isEmpty ? nil : airports),
            destinationCountries: countries.isEmpty ? nil : countries,
            destinationRegions: regions.isEmpty ? nil : regions,
            destinationContinents: continents.isEmpty ? nil : continents,
            returnOriginAirports: tripPlan == "open_jaw" ? [routePlaces[1].code] : nil,
            startDate: advanced.useProfileDates ? nil : Self.apiDate(advanced.startDate),
            endDate: advanced.useProfileDates ? nil : Self.apiDate(advanced.endDate),
            minTripLengthDays: advanced.useProfileTripLength ? nil : advanced.minTripLengthDays,
            maxTripLengthDays: advanced.useProfileTripLength ? nil : advanced.maxTripLengthDays,
            maxBudget: budget,
            maxGroundTransferHours: advanced.maxGroundTransferHours,
            tripPlan: tripPlan,
            routeStops: tripPlan == "multi_city" ? routePlaces.map(\.code) : nil,
            directOnly: Self.optionalPreference(advanced.directPreference, requiredValue: "direct"),
            includeBaggage: Self.optionalPreference(advanced.baggagePreference, requiredValue: "included"),
            travelStyles: advanced.travelStyles.isEmpty ? nil : advanced.travelStyles
        )
    }

    private func performAdvancedSearch(_ request: FarelinAdvancedSearchRequest) async {
        let progress = startProgressMessages()
        defer {
            progress.cancel()
            isSearching = false
        }
        do {
            response = try await authenticated {
                try await self.service.advancedSearch(request)
            }
        } catch {
            errorMessage = readable(error)
        }
    }

    private static func optionalPreference(_ value: String, requiredValue: String) -> Bool? {
        if value == "profile" { return nil }
        return value == requiredValue
    }

    private static func apiDate(_ date: Date) -> String {
        let components = Calendar(identifier: .gregorian).dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", components.year ?? 2000, components.month ?? 1, components.day ?? 1)
    }

    func clearResults() {
        response = nil
        errorMessage = nil
    }

    private func startProgressMessages() -> Task<Void, Never> {
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .seconds(1.1))
            guard !Task.isCancelled else { return }
            self?.progressMessage = "Checking fare observations…"
            try? await Task.sleep(for: .seconds(1.5))
            guard !Task.isCancelled else { return }
            self?.progressMessage = "Scoring trip ideas…"
        }
    }

    private func authenticated<T: Sendable>(
        _ operation: @escaping @MainActor @Sendable () async throws -> T
    ) async throws -> T {
        do {
            return try await operation()
        } catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else { throw APIError.unauthorized }
            return try await operation()
        }
    }

    private func readable(_ error: Error) -> String {
        if case APIError.server(_, let statusCode) = error, statusCode == 429 {
            return "You’re searching quickly. Wait a few seconds and try again."
        }
        return (error as? LocalizedError)?.errorDescription
            ?? "Farelin could not complete that search."
    }
}

@MainActor
@Observable
final class TripDetailStore {
    private(set) var trip: SearchTrip
    private(set) var title: String?
    private(set) var itinerary: ItineraryPlan?
    private(set) var disclaimer = "Prices may change. Check the final price with the provider."
    private(set) var isLoading = false
    private(set) var isGenerating = false
    private(set) var itineraryWasCached = false
    private(set) var errorMessage: String?

    let suggestionID: String?
    private let service: any TripDetailServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?
    private var hasLoaded = false

    init(
        trip: SearchTrip,
        suggestionID: String?,
        service: any TripDetailServicing,
        reauthenticate: (@MainActor @Sendable () async -> Bool)? = nil
    ) {
        self.trip = trip
        self.suggestionID = suggestionID
        self.service = service
        self.reauthenticate = reauthenticate
    }

    func load() async {
        guard !hasLoaded, let suggestionID else { return }
        hasLoaded = true
        isLoading = true
        defer { isLoading = false }
        do {
            let suggestion = try await authenticated {
                try await self.service.tripSuggestion(id: suggestionID)
            }
            trip = suggestion.trip
            title = suggestion.title
            itinerary = suggestion.itinerary
            itineraryWasCached = suggestion.itinerary != nil
            disclaimer = suggestion.disclaimer
        } catch {
            // The search result remains useful even if its persisted suggestion
            // expired between the results screen and this detail view.
            errorMessage = readable(error)
        }
    }

    func generateItinerary() async {
        guard itinerary == nil, !isGenerating, let suggestionID else { return }
        isGenerating = true
        errorMessage = nil
        await performGeneration(suggestionID: suggestionID)
    }

    func submitItineraryGeneration() {
        guard itinerary == nil, !isGenerating, let suggestionID else { return }
        isGenerating = true
        errorMessage = nil
        Task { @MainActor [weak self] in
            await self?.performGeneration(suggestionID: suggestionID)
        }
    }

    private func performGeneration(suggestionID: String) async {
        defer { isGenerating = false }
        do {
            let result = try await authenticated {
                try await self.service.generateItinerary(suggestionID: suggestionID)
            }
            itinerary = result.itinerary
            itineraryWasCached = result.cached
        } catch {
            errorMessage = readable(error)
        }
    }

    func dismissError() {
        errorMessage = nil
    }

    private func authenticated<T: Sendable>(
        _ operation: @escaping @MainActor @Sendable () async throws -> T
    ) async throws -> T {
        do {
            return try await operation()
        } catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else { throw APIError.unauthorized }
            return try await operation()
        }
    }

    private func readable(_ error: Error) -> String {
        if case APIError.server(_, let statusCode) = error, statusCode == 402 {
            return "Your current plan’s AI allowance has been reached. You can still check the fare with the provider."
        }
        return (error as? LocalizedError)?.errorDescription
            ?? "Farelin could not load this trip right now."
    }
}
