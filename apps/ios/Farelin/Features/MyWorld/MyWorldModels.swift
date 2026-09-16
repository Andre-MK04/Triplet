import Foundation
import Observation

struct CountryCatalogResponse: Decodable, Sendable {
    let definition: String
    let worldTotal: Int
    let continentTotal: Int
    let continents: [String]
    let countries: [CountryCatalogEntry]
}

struct CountryCatalogEntry: Decodable, Identifiable, Hashable, Sendable {
    var id: String { code }
    let code: String
    let alpha3: String
    let numericCode: String
    let name: String
    let continent: String
    let countsTowardWorldTotal: Bool
}

struct TravelMapResponse: Decodable, Sendable {
    let countries: [TravelMapCountry]
    let stats: TravelMapStats
    let updatedAt: String?
}

struct TravelMapCountry: Decodable, Identifiable, Hashable, Sendable {
    var id: String { code }
    let code: String
    let name: String
    let continent: String
    let visited: Bool
    let lived: Bool
    let wishlist: Bool
    let primaryStatus: String
    let visitCount: Int
    let residenceCount: Int
    let visits: [CountryVisit]
    let updatedAt: String
}

struct CountryVisit: Decodable, Identifiable, Hashable, Sendable {
    let id: String
    let countryCode: String
    let kind: String
    let startDate: String?
    let endDate: String?
    let startPrecision: String
    let endPrecision: String
    let note: String?
    let tripId: String?
    let createdAt: String
    let updatedAt: String
}

struct TravelMapStats: Decodable, Equatable, Sendable {
    let countriesVisited: Int
    let countriesLivedIn: Int
    let wishlistCountries: Int
    let worldTotal: Int
    let worldExploredPercentage: Double
    let continentsVisited: Int
    let continentTotal: Int
    let continentProgress: [ContinentProgress]
}

struct ContinentProgress: Decodable, Equatable, Sendable {
    let name: String
    let visited: Int
    let total: Int
}

struct CountryStateUpdate: Encodable, Sendable {
    let visited: Bool?
    let lived: Bool?
    let wishlist: Bool?

    init(visited: Bool? = nil, lived: Bool? = nil, wishlist: Bool? = nil) {
        self.visited = visited
        self.lived = lived
        self.wishlist = wishlist
    }
}

protocol TravelMapServicing: Sendable {
    func countryCatalog() async throws -> CountryCatalogResponse
    func travelMap() async throws -> TravelMapResponse
    func updateCountry(_ code: String, update: CountryStateUpdate) async throws -> TravelMapCountry
}

@MainActor
@Observable
final class MyWorldStore {
    private(set) var catalog: [CountryCatalogEntry] = []
    private(set) var map: TravelMapResponse?
    private(set) var isLoading = false
    private(set) var updatingCode: String?
    private(set) var errorMessage: String?
    var selectedCode: String?
    var query = ""

    private let service: any TravelMapServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?

    init(
        service: any TravelMapServicing,
        reauthenticate: (@MainActor @Sendable () async -> Bool)? = nil
    ) {
        self.service = service
        self.reauthenticate = reauthenticate
    }

    var countriesByCode: [String: TravelMapCountry] {
        Dictionary(uniqueKeysWithValues: (map?.countries ?? []).map { ($0.code, $0) })
    }

    var selectedCatalogEntry: CountryCatalogEntry? {
        guard let selectedCode else { return nil }
        return catalog.first { $0.code == selectedCode }
    }

    var selectedCountry: TravelMapCountry? {
        guard let selectedCode else { return nil }
        return countriesByCode[selectedCode]
    }

    var filteredCatalog: [CountryCatalogEntry] {
        let term = query.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let ordered = catalog.sorted {
            $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending
        }
        guard !term.isEmpty else { return ordered }
        return ordered.filter {
            $0.name.lowercased().contains(term)
                || $0.code.lowercased().contains(term)
                || $0.alpha3.lowercased().contains(term)
        }
    }

    func load(force: Bool = false) async {
        guard force || map == nil || catalog.isEmpty else { return }
        guard !isLoading else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let values = try await authenticated {
                async let catalog = self.service.countryCatalog()
                async let map = self.service.travelMap()
                return try await (catalog, map)
            }
            catalog = values.0.countries
            map = values.1
        } catch {
            errorMessage = readable(error)
        }
    }

    func select(_ code: String) {
        guard catalog.contains(where: { $0.code == code }) else { return }
        selectedCode = code
        errorMessage = nil
    }

    func updateSelected(_ update: CountryStateUpdate) async {
        guard let selectedCode, updatingCode == nil else { return }
        updatingCode = selectedCode
        errorMessage = nil
        defer { updatingCode = nil }
        do {
            let updated = try await authenticated {
                try await self.service.updateCountry(selectedCode, update: update)
            }
            guard let current = map else { return }
            var countries = current.countries.filter { $0.code != updated.code }
            if updated.primaryStatus != "unvisited" || updated.visitCount > 0 {
                countries.append(updated)
            }
            // Stats have several derived fields. Reload them from the authority
            // after the responsive local country replacement.
            map = TravelMapResponse(countries: countries, stats: current.stats, updatedAt: updated.updatedAt)
            map = try await authenticated { try await self.service.travelMap() }
        } catch {
            errorMessage = readable(error)
        }
    }

    func dismissSelection() {
        selectedCode = nil
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
            ?? "Farelin could not load your travel map."
    }

    private static func statusRank(_ status: String) -> Int {
        switch status {
        case "lived": 0
        case "visited": 1
        case "wishlist": 2
        default: 3
        }
    }
}
