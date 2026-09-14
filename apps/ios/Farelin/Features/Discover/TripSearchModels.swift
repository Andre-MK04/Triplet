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

protocol TripSearchServicing: Sendable {
    func searchTrips(_ request: FarelinAISearchRequest) async throws -> FarelinAISearchResponse
}

@MainActor
@Observable
final class TripSearchStore {
    var query = ""
    private(set) var response: FarelinAISearchResponse?
    private(set) var isSearching = false
    private(set) var progressMessage = "Understanding your request…"
    private(set) var errorMessage: String?

    private let service: any TripSearchServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?

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

    func search(origins: [String]) async {
        let message = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard message.count >= 8 else {
            errorMessage = "Describe the trip you want in a little more detail."
            return
        }
        guard !origins.isEmpty else {
            errorMessage = "Add at least one origin airport to your travel profile first."
            return
        }
        guard !isSearching else { return }

        isSearching = true
        response = nil
        errorMessage = nil
        progressMessage = "Understanding your request…"
        let progress = startProgressMessages()
        defer {
            progress.cancel()
            isSearching = false
        }

        do {
            response = try await authenticated {
                try await self.service.searchTrips(
                    FarelinAISearchRequest(message: message, originAirports: origins)
                )
            }
        } catch {
            errorMessage = readable(error)
        }
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
