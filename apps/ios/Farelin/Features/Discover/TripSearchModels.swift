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
    let routeStops: [String]?
    let returnOriginAirports: [String]?
    let maxGroundTransferHours: Double?
    let directOnly: Bool?
    let includeBaggage: Bool?
    var maxStops: Int? = nil
}

struct NativeSavedWatchRequest: Encodable, Sendable {
    let email: String
    let name: String
    let originAirports: [String]
    var destinationAirports: [String]?
    let startDate: String
    let endDate: String
    let minTripLengthDays: Int
    let maxTripLengthDays: Int
    let maxBudget: Double
    let maxGroundTransferHours: Double
    let tripStyle: String
    let frequency: String
    let triggerMode: String
    var destinationCountries: [String] = []
    var destinationRegions: [String] = []
    var destinationContinents: [String] = []
    var tripPlan: String = "return"
    var routeStops: [String]? = nil
    var returnOriginAirports: [String]? = nil
    var travelStyles: [String] = []
    var directOnly: Bool? = nil
    var includeBaggage: Bool? = nil
    var maxStops: Int? = nil
}

protocol NativeWatchCreating: Sendable {
    func createWatch(_ request: NativeSavedWatchRequest) async throws -> SavedWatchSummary
}

struct SavedFareSummary: Decodable, Identifiable, Sendable {
    let id: String
    let suggestionId: String
    let title: String
    let tripType: String
    let observedPrice: Double
    let currency: String
    let fareStatus: String
    let observedAt: String
    let checkPriceUrl: String?
    let savedAt: String
    let disclaimer: String
    let trip: SearchTrip?

    var checkPriceURL: URL? {
        if let trip, let url = trip.checkPriceURL { return url }
        guard let checkPriceUrl, let url = URL(string: checkPriceUrl), url.scheme == "https",
              url.host != nil, url.user == nil, url.password == nil else { return nil }
        return url
    }
}

protocol NativeFareSaving: Sendable {
    func savedFares() async throws -> [SavedFareSummary]
    func saveFare(suggestionId: String) async throws -> SavedFareSummary
    func deleteSavedFare(id: String) async throws
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
    var flexibleBudget: Bool = false
    var maxStops: Int? = nil
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
    var flexibleBudget = false
    var tripPlan = "return"
    var travelStyles: [String] = []
    var directPreference = "profile"
    var baggagePreference = "profile"
    var useDefaultGroundTransfer = true
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

struct SearchTripSegment: Decodable, Sendable {
    let kind: String
    let origin: String
    let destination: String
    let originCity: String
    let destinationCity: String
    let departureDate: String
    let flight: SearchFlight?
    let transfer: SearchGroundTransfer?
    let bookingUrl: String?
}

struct SearchCityStay: Decodable, Sendable {
    let code: String
    let city: String
    let country: String
    let countryCode: String
    let arrivalDate: String
    let departureDate: String
    let nights: Int
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
    let segments: [SearchTripSegment]?
    let stays: [SearchCityStay]?
    let flightCost: Double?
    let groundEstimate: Double?
    let transportTotalEstimate: Double?
    let durationMatch: String?
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
            ([segments?.first?.origin ?? outboundFlight.origin] +
             ((segments ?? []).isEmpty ? (stays ?? []).map(\.city) + [returnFlight.destination] :
                (segments ?? []).map { $0.destination == returnFlight.destination ? $0.destination : $0.destinationCity }))
                .joined(separator: " → ")
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
        // One provider search for all flight legs. This is not one protected
        // fare quote; ground crossings remain the traveller's arrangement.
        if tripType == "multi_city" || (tripType == "open_jaw" && !(segments ?? []).isEmpty) {
            guard provider == "travelpayouts" else { return nil }
            return FarelinProviderSearchLink.combined(trip: self)
        }
        return [bookingUrl, outboundFlight.bookingUrl, outboundFlight.deepLink, outboundFlight.affiliateUrl]
            .compactMap { $0 }
            .compactMap(URL.init(string:))
            .first { $0.scheme == "https" && $0.host != nil && $0.user == nil && $0.password == nil }
    }
}

enum FarelinProviderSearchLink {
    static func combined(trip: SearchTrip) -> URL? {
        let legs = (trip.segments ?? []).filter { $0.kind == "flight" }
        guard (2...7).contains(legs.count), legs.allSatisfy({ $0.flight != nil }) else { return nil }
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(secondsFromGMT: 0)
        parser.dateFormat = "yyyy-MM-dd"
        parser.isLenient = false
        let output = DateFormatter()
        output.locale = parser.locale
        output.timeZone = parser.timeZone
        output.dateFormat = "ddMM"
        var route = ""
        var previousDestination: String?
        var previousDate: Date?
        for leg in legs {
            let origin = leg.origin.uppercased(), destination = leg.destination.uppercased()
            guard [origin, destination].allSatisfy({ code in
                code.utf8.count == 3 && code.utf8.allSatisfy { (65...90).contains($0) }
            }), origin != destination,
                  let date = parser.date(from: String(leg.departureDate.prefix(10))),
                  previousDate == nil || date >= previousDate! else { return nil }
            if route.isEmpty { route = origin }
            else if previousDestination != origin { route += "-" + origin }
            route += output.string(from: date) + destination
            previousDestination = destination
            previousDate = date
        }
        var url = URLComponents(string: "https://www.aviasales.com/search/\(route)1")!
        url.queryItems = [URLQueryItem(name: "currency", value: trip.outboundFlight.currency.lowercased())]
        let source = legs.first?.bookingUrl ?? legs.first?.flight?.bookingUrl ?? trip.outboundFlight.bookingUrl
        if let source, let components = URLComponents(string: source),
           components.host == "www.aviasales.com" || components.host == "aviasales.com",
           let marker = components.queryItems?.first(where: { $0.name == "marker" })?.value,
           !marker.isEmpty, marker.count <= 30, marker.utf8.allSatisfy({ (48...57).contains($0) }) {
            url.queryItems?.append(URLQueryItem(name: "marker", value: marker))
        }
        return url.url
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

struct NativeOpportunityFeed: Decodable, Sendable {
    let trips: [SearchTrip]
    let originAirports: [String]
    let source: String
    let isReady: Bool
    let isStale: Bool
}

protocol OpportunityServicing: Sendable {
    func opportunities() async throws -> NativeOpportunityFeed
}

/// Reads only the signed-in user's observed-price cache. No AI or provider calls.
@MainActor
@Observable
final class OpportunityStore {
    private(set) var feed: NativeOpportunityFeed?
    private(set) var isLoading = false
    private(set) var errorMessage: String?
    private let service: any OpportunityServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?

    init(service: any OpportunityServicing, reauthenticate: (@MainActor @Sendable () async -> Bool)? = nil) {
        self.service = service
        self.reauthenticate = reauthenticate
    }

    func load() async {
        guard feed == nil && !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            feed = try await service.opportunities()
            errorMessage = nil
        } catch APIError.unauthorized {
            if await reauthenticate?() == true {
                do {
                    feed = try await service.opportunities()
                    errorMessage = nil
                } catch {
                    errorMessage = error.localizedDescription
                }
            } else {
                errorMessage = APIError.unauthorized.localizedDescription
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
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
    private(set) var lastSearchUsedAI = false
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
        guard activeSearchTask == nil else { return }

        activeSearchTask = Task { @MainActor [weak self] in
            guard let self else { return }
            guard await self.resolveTypedDestinationIfNeeded(),
                  let request = self.beginAdvancedSearch(profileOrigins: profileOrigins) else {
                self.activeSearchTask = nil
                return
            }
            await self.performAdvancedSearch(request)
            self.activeSearchTask = nil
        }
    }

    func searchAdvanced(profileOrigins: [String]) async {
        guard await resolveTypedDestinationIfNeeded() else { return }
        guard let request = beginAdvancedSearch(profileOrigins: profileOrigins) else { return }
        await performAdvancedSearch(request)
    }

    private func resolveTypedDestinationIfNeeded() async -> Bool {
        guard advanced.destinations.isEmpty else { return true }
        let typed = placeQuery.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !typed.isEmpty else { return true }
        guard typed.count >= 2 else {
            errorMessage = "Choose a place or region from the suggestions."
            return false
        }
        do {
            let candidates = placeResults.isEmpty ? try await service.searchPlaces(typed) : placeResults
            guard typed == placeQuery.trimmingCharacters(in: .whitespacesAndNewlines) else { return false }
            let exact = candidates.filter {
                $0.name.caseInsensitiveCompare(typed) == .orderedSame
                    || $0.code.caseInsensitiveCompare(typed) == .orderedSame
            }
            let place = exact.count == 1 ? exact.first :
                (exact.allSatisfy { ["region", "continent"].contains($0.kind) }
                    ? exact.first { $0.kind == "continent" } : nil)
            guard let place else {
                errorMessage = "Choose a matching place or region from the suggestions before searching."
                return false
            }
            addDestination(place)
            return true
        } catch {
            errorMessage = readable(error)
            return false
        }
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

        lastSearchUsedAI = true
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
        let broadScope = advanced.destinations.filter { ["country", "region", "continent"].contains($0.kind) }
        let isScopedJourney = !broadScope.isEmpty && routePlaces.isEmpty
        if ["open_jaw", "multi_city"].contains(tripPlan ?? ""), !advanced.destinations.isEmpty,
           !broadScope.isEmpty && !routePlaces.isEmpty {
            errorMessage = "Choose either places in travel order or a broad region, not both."
            return nil
        }
        if tripPlan == "open_jaw" && !isScopedJourney && routePlaces.count != 2 {
            errorMessage = "Add exactly two cities or airports: where you land, then where you fly home from."
            return nil
        }
        if ["open_jaw", "multi_city"].contains(tripPlan ?? ""), advanced.destinations.isEmpty {
            errorMessage = "Choose two places in order, or one region, country or continent."
            return nil
        }
        if tripPlan == "multi_city" && !isScopedJourney && routePlaces.count < 2 {
            errorMessage = "Add at least two cities or airports in travel order for a multi-city trip."
            return nil
        }

        let scopedDestinations = tripPlan == "open_jaw" && !isScopedJourney ? [] : advanced.destinations
        let airports = scopedDestinations
            .filter { $0.kind == "city" || $0.kind == "airport" }
            .map(\.code)
        let countries = scopedDestinations.filter { $0.kind == "country" }.map(\.code)
        let regions = scopedDestinations.filter { $0.kind == "region" }.map(\.code)
        let continents = scopedDestinations.filter { $0.kind == "continent" }.map(\.code)

        lastSearchUsedAI = false
        isSearching = true
        response = nil
        errorMessage = nil
        progressMessage = "Resolving your profile defaults…"
        return FarelinAdvancedSearchRequest(
            originAirports: origins,
            destinationAirports: tripPlan == "open_jaw" && !isScopedJourney ? [routePlaces[0].code] : (airports.isEmpty ? nil : airports),
            destinationCountries: countries.isEmpty ? nil : countries,
            destinationRegions: regions.isEmpty ? nil : regions,
            destinationContinents: continents.isEmpty ? nil : continents,
            returnOriginAirports: tripPlan == "open_jaw" && !isScopedJourney ? [routePlaces[1].code] : nil,
            startDate: advanced.useProfileDates ? nil : Self.apiDate(advanced.startDate),
            endDate: advanced.useProfileDates ? nil : Self.apiDate(advanced.endDate),
            minTripLengthDays: advanced.useProfileTripLength ? nil : advanced.minTripLengthDays,
            maxTripLengthDays: advanced.useProfileTripLength ? nil : advanced.maxTripLengthDays,
            maxBudget: budget,
            maxGroundTransferHours: advanced.useDefaultGroundTransfer ? nil : advanced.maxGroundTransferHours,
            tripPlan: tripPlan,
            routeStops: tripPlan == "multi_city" && !isScopedJourney ? routePlaces.map(\.code) : nil,
            directOnly: Self.optionalPreference(advanced.directPreference, requiredValue: "direct"),
            includeBaggage: Self.optionalPreference(advanced.baggagePreference, requiredValue: "included"),
            travelStyles: advanced.travelStyles.isEmpty ? nil : advanced.travelStyles,
            flexibleBudget: advanced.flexibleBudget,
            maxStops: advanced.directPreference == "one_stop" ? 1 : (advanced.directPreference == "direct" ? 0 : nil)
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

    /// Prepares an explicit date override for review, without submitting a search
    /// or changing the user's route, budget, duration or comfort choices.
    @discardableResult
    func prepareWiderDateWindow() -> Bool {
        guard let window = widenedDateWindow() else { return false }
        advanced.useProfileDates = false
        advanced.startDate = window.start
        advanced.endDate = window.end
        clearResults()
        return true
    }

    var canReviewWiderDates: Bool { widenedDateWindow() != nil }

    private func widenedDateWindow() -> (start: Date, end: Date)? {
        guard !isSearching, !lastSearchUsedAI else { return nil }
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.isLenient = false
        let start: Date
        let end: Date
        if let parsed = response?.parsedRequest {
            guard let parsedStart = formatter.date(from: parsed.startDate),
                  let parsedEnd = formatter.date(from: parsed.endDate),
                  parsedEnd >= parsedStart else { return nil }
            start = parsedStart
            end = parsedEnd
        } else {
            guard !advanced.useProfileDates, advanced.endDate >= advanced.startDate else { return nil }
            start = advanced.startDate
            end = advanced.endDate
        }
        guard let widerEnd = formatter.calendar.date(byAdding: .day, value: 30, to: end) else { return nil }
        return (start, widerEnd)
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
