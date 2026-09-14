import Foundation
import Observation

struct LocationResult: Decodable, Identifiable, Hashable, Sendable {
    let id: Int
    let name: String
    let countryCode: String
    let countryName: String
    let adminRegion: String?
    let latitude: Double
    let longitude: Double
    let population: Int?
}

struct AirportResult: Decodable, Identifiable, Hashable, Sendable {
    var id: String { iataCode }
    let iataCode: String
    let name: String
    let city: String?
    let countryCode: String
    let countryName: String
    let latitude: Double
    let longitude: Double
    let type: String
    let scheduledService: Bool
    let distanceKm: Double?
}

struct TravelProfileResponse: Decodable, Sendable {
    let userId: String
    let isComplete: Bool
    let homeLocation: String?
    let originAirports: [String]
    let maxAirportTravelTimeMinutes: Int
    let preferredTripTypes: [String]
    let preferredTripLengthMin: Int
    let preferredTripLengthMax: Int
    let budgetComfortZone: String
    let spontaneity: String
    let comfortRules: [String]
    let openJawWillingness: String
    let notificationFrequency: String
    let excludedAirlines: [String]
    let preferredMonths: [Int]
    let baseLocationId: Int?
    let baseLatitude: Double?
    let baseLongitude: Double?
    let maxAirportDistanceKm: Int?
    let recommendedOriginAirports: [String]
    let dealSensitivity: String
    let absoluteMaxBudget: Double?
    let alertTriggerMode: String
    let comfortRuleModes: [String: String]
    let themePreference: String?
}

struct TravelProfilePayload: Encodable, Sendable {
    let homeLocation: String?
    let originAirports: [String]
    let maxAirportTravelTimeMinutes: Int
    let preferredTripTypes: [String]
    let preferredTripLengthMin: Int
    let preferredTripLengthMax: Int
    let budgetComfortZone: String
    let spontaneity: String
    let comfortRules: [String]
    let openJawWillingness: String
    let notificationFrequency: String
    let excludedAirlines: [String]
    let preferredMonths: [Int]
    let baseLocationId: Int?
    let baseLatitude: Double?
    let baseLongitude: Double?
    let maxAirportDistanceKm: Int?
    let recommendedOriginAirports: [String]
    let dealSensitivity: String
    let absoluteMaxBudget: Double?
    let alertTriggerMode: String
    let comfortRuleModes: [String: String]
    let themePreference: String?
}

struct TravelProfileDraft: Equatable, Sendable {
    var homeLocation = ""
    var baseLocationId: Int?
    var baseLatitude: Double?
    var baseLongitude: Double?
    var maxAirportDistanceKm = 200
    var maxAirportTravelTimeMinutes = 120
    var originAirports: [String] = []
    var recommendedOriginAirports: [String] = []
    var preferredTripTypes: [String] = []
    var preferredTripLengthMin = 2
    var preferredTripLengthMax = 7
    var dealSensitivity = "balanced"
    var budgetComfortZone = "under_200"
    var absoluteMaxBudget: Double?
    var spontaneity = "flexible_monthly"
    var comfortRuleModes: [String: String] = [:]
    var openJawWillingness = "simple_returns_only"
    var notificationFrequency = "weekly_digest"
    var alertTriggerMode = "any"
    var themePreference: String?

    init() {}

    init(response: TravelProfileResponse) {
        homeLocation = response.homeLocation ?? ""
        baseLocationId = response.baseLocationId
        baseLatitude = response.baseLatitude
        baseLongitude = response.baseLongitude
        maxAirportDistanceKm = response.maxAirportDistanceKm ?? 200
        maxAirportTravelTimeMinutes = response.maxAirportTravelTimeMinutes
        // The legacy API response contains VIE solely to satisfy its old schema
        // when no profile exists. Never turn that placeholder into a user choice.
        originAirports = response.isComplete ? response.originAirports : []
        recommendedOriginAirports = response.isComplete ? response.recommendedOriginAirports : []
        preferredTripTypes = response.preferredTripTypes
        preferredTripLengthMin = response.preferredTripLengthMin
        preferredTripLengthMax = response.preferredTripLengthMax
        dealSensitivity = response.dealSensitivity
        budgetComfortZone = response.budgetComfortZone
        absoluteMaxBudget = response.absoluteMaxBudget
        spontaneity = Self.normalizedSpontaneity(response.spontaneity)
        comfortRuleModes = response.comfortRuleModes
        openJawWillingness = response.openJawWillingness
        notificationFrequency = response.notificationFrequency == "push_later"
            ? "weekly_digest"
            : response.notificationFrequency
        alertTriggerMode = response.alertTriggerMode
        themePreference = response.themePreference
    }

    var payload: TravelProfilePayload {
        let activeComfortRules = comfortRuleModes
            .filter { $0.value != "off" }
            .map(\.key)
            .sorted()
        return TravelProfilePayload(
            homeLocation: homeLocation.isEmpty ? nil : homeLocation,
            originAirports: originAirports,
            maxAirportTravelTimeMinutes: maxAirportTravelTimeMinutes,
            preferredTripTypes: preferredTripTypes,
            preferredTripLengthMin: preferredTripLengthMin,
            preferredTripLengthMax: preferredTripLengthMax,
            budgetComfortZone: budgetComfortZone,
            spontaneity: spontaneity,
            comfortRules: activeComfortRules,
            openJawWillingness: openJawWillingness,
            notificationFrequency: notificationFrequency,
            excludedAirlines: [],
            preferredMonths: [],
            baseLocationId: baseLocationId,
            baseLatitude: baseLatitude,
            baseLongitude: baseLongitude,
            maxAirportDistanceKm: maxAirportDistanceKm,
            recommendedOriginAirports: recommendedOriginAirports,
            dealSensitivity: dealSensitivity,
            absoluteMaxBudget: absoluteMaxBudget,
            alertTriggerMode: notificationFrequency == "urgent_only" ? "route_deal" : alertTriggerMode,
            comfortRuleModes: comfortRuleModes.filter { $0.value != "off" },
            themePreference: themePreference
        )
    }

    private static func normalizedSpontaneity(_ value: String) -> String {
        switch value {
        case "tomorrow": "very_spontaneous"
        case "next_week": "soon"
        case "next_month": "flexible_monthly"
        case "planning_ahead": "planner"
        default: value
        }
    }
}

protocol TravelProfileServicing: Sendable {
    func travelProfile() async throws -> TravelProfileResponse
    func updateTravelProfile(_ payload: TravelProfilePayload) async throws -> TravelProfileResponse
    func searchLocations(_ query: String) async throws -> [LocationResult]
    func recommendedAirports(latitude: Double, longitude: Double, maxDistanceKm: Int) async throws -> [AirportResult]
    func searchAirports(_ query: String, latitude: Double?, longitude: Double?) async throws -> [AirportResult]
}

@MainActor
@Observable
final class TravelProfileStore {
    private(set) var draft: TravelProfileDraft?
    private(set) var isComplete = false
    private(set) var isLoading = false
    private(set) var isSaving = false
    private(set) var locationResults: [LocationResult] = []
    private(set) var airportResults: [AirportResult] = []
    private(set) var recommendedAirports: [AirportResult] = []
    private(set) var isSearchingLocations = false
    private(set) var isSearchingAirports = false
    private(set) var isLoadingRecommendations = false
    var errorMessage: String?

    private let service: any TravelProfileServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?

    init(
        service: any TravelProfileServicing,
        reauthenticate: (@MainActor @Sendable () async -> Bool)? = nil
    ) {
        self.service = service
        self.reauthenticate = reauthenticate
    }

    func load() async {
        guard draft == nil, !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let response = try await authenticated { try await self.service.travelProfile() }
            draft = TravelProfileDraft(response: response)
            isComplete = response.isComplete
        } catch {
            errorMessage = readable(error)
        }
    }

    func update(_ change: (inout TravelProfileDraft) -> Void) {
        guard var draft else { return }
        change(&draft)
        self.draft = draft
        errorMessage = nil
    }

    func searchLocations(_ query: String) async {
        let normalized = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard normalized.count >= 2 else {
            locationResults = []
            return
        }
        isSearchingLocations = true
        defer { isSearchingLocations = false }
        do {
            locationResults = try await service.searchLocations(normalized)
        } catch {
            locationResults = []
            errorMessage = readable(error)
        }
    }

    func selectLocation(_ location: LocationResult) async {
        update {
            $0.homeLocation = "\(location.name), \(location.countryName)"
            $0.baseLocationId = location.id
            $0.baseLatitude = location.latitude
            $0.baseLongitude = location.longitude
            $0.originAirports = []
            $0.recommendedOriginAirports = []
        }
        locationResults = []
        await loadRecommendedAirports()
    }

    func invalidateSelectedLocation() {
        update {
            $0.baseLocationId = nil
            $0.baseLatitude = nil
            $0.baseLongitude = nil
            $0.originAirports = []
            $0.recommendedOriginAirports = []
        }
        recommendedAirports = []
    }

    func loadRecommendedAirports(preselectLimit: Int? = nil) async {
        guard let draft, let latitude = draft.baseLatitude, let longitude = draft.baseLongitude else {
            recommendedAirports = []
            return
        }
        isLoadingRecommendations = true
        defer { isLoadingRecommendations = false }
        do {
            let airports = try await service.recommendedAirports(
                latitude: latitude,
                longitude: longitude,
                maxDistanceKm: draft.maxAirportDistanceKm
            )
            recommendedAirports = airports
            update { profile in
                profile.recommendedOriginAirports = airports.map(\.iataCode)
                if profile.originAirports.isEmpty, let preselectLimit {
                    profile.originAirports = airports.prefix(min(3, preselectLimit)).map(\.iataCode)
                }
            }
        } catch {
            recommendedAirports = []
            errorMessage = readable(error)
        }
    }

    func searchAirports(_ query: String) async {
        let normalized = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard normalized.count >= 2 else {
            airportResults = []
            return
        }
        isSearchingAirports = true
        defer { isSearchingAirports = false }
        do {
            airportResults = try await service.searchAirports(
                normalized,
                latitude: draft?.baseLatitude,
                longitude: draft?.baseLongitude
            )
        } catch {
            airportResults = []
            errorMessage = readable(error)
        }
    }

    func toggleAirport(_ airport: AirportResult, limit: Int) {
        toggleAirportCode(airport.iataCode, limit: limit)
    }

    func toggleAirportCode(_ code: String, limit: Int) {
        guard var draft else { return }
        if draft.originAirports.contains(code) {
            draft.originAirports.removeAll { $0 == code }
        } else if draft.originAirports.count < limit {
            draft.originAirports.append(code)
        } else {
            errorMessage = "Your current plan allows up to \(limit) origin airports."
            return
        }
        self.draft = draft
    }

    func save() async -> Bool {
        guard let draft else { return false }
        guard draft.baseLocationId != nil else {
            errorMessage = "Choose a matching city before saving."
            return false
        }
        guard !draft.originAirports.isEmpty else {
            errorMessage = "Choose at least one origin airport."
            return false
        }
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        do {
            let response = try await authenticated {
                try await self.service.updateTravelProfile(draft.payload)
            }
            self.draft = TravelProfileDraft(response: response)
            isComplete = response.isComplete
            return true
        } catch {
            errorMessage = readable(error)
            return false
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
        (error as? LocalizedError)?.errorDescription
            ?? "Farelin could not complete that request."
    }
}
