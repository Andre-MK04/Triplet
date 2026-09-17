import Foundation
import Observation

protocol DashboardServicing: Sendable {
    func dashboard() async throws -> DashboardResponse
    func pauseWatch(id: String) async throws -> SavedWatchSummary
    func resumeWatch(id: String) async throws -> SavedWatchSummary
    func deleteWatch(id: String) async throws
}

struct DashboardResponse: Decodable, Sendable {
    let user: AuthUser
    let billing: DashboardBilling
    let usage: DashboardUsage
    let savedSearches: [SavedWatchSummary]
    let savedSearchSummary: SavedSearchSummary
}

struct DashboardBilling: Decodable, Sendable {
    let plan: String
    let subscriptionStatus: String
    let trialDaysRemaining: Int
    let usage: DashboardUsage
    let canStartTrial: Bool
    let canUpgrade: Bool
    let canManageBilling: Bool
}

struct DashboardUsage: Decodable, Sendable {
    let aiSearchesThisMonth: Int
    let aiSearchesPerMonth: Int
    let activeSavedSearches: Int
    let savedSearchLimit: Int
    let maxOriginAirports: Int
    let dailyWatchChecks: Bool
    let unlimited: Bool
}

struct SavedSearchSummary: Decodable, Sendable {
    let total: Int
    let active: Int
}

struct SavedWatchSummary: Decodable, Identifiable, Sendable {
    let id: String
    let name: String?
    let originAirports: [String]
    let destinationAirports: [String]?
    let startDate: String
    let endDate: String
    let maxBudget: Double
    let frequency: String
    let isActive: Bool
    let lastCheckedAt: String?
    let lastNotifiedAt: String?
    let lastBestPrice: Double?
    var destinationCountries: [String]? = nil
    var destinationRegions: [String]? = nil
    var destinationContinents: [String]? = nil
    var routeStops: [String]? = nil

    var routeDescription: String {
        let destinations: String
        if let routeStops, !routeStops.isEmpty {
            destinations = routeStops.joined(separator: " → ")
        } else {
            let scope = (destinationAirports ?? []) + (destinationRegions ?? [])
                + (destinationCountries ?? []) + (destinationContinents ?? [])
            destinations = scope.isEmpty ? "Anywhere" : scope.joined(separator: " + ")
        }
        return "\(originAirports.joined(separator: " + ")) → \(destinations)"
    }
}

/// Presentation only: never changes scheduler state or treats old prices as live.
struct TodayWatchOverview {
    enum State: String {
        case expired = "Window ended"
        case paused = "Paused"
        case waiting = "Awaiting first check"
        case watching = "Watching"
    }

    let watches: [SavedWatchSummary]
    let now: Date

    func state(of watch: SavedWatchSummary) -> State {
        if let end = Self.date(watch.endDate), end < Self.startOfDay(now) { return .expired }
        if !watch.isActive { return .paused }
        return watch.lastCheckedAt == nil ? .waiting : .watching
    }

    var monitoringCount: Int {
        watches.filter { [.waiting, .watching].contains(state(of: $0)) }.count
    }

    var orderedWatches: [SavedWatchSummary] {
        watches.sorted {
            let left = priority($0)
            let right = priority($1)
            if left != right { return left < right }
            // Recent recorded notifications are a reason to inspect, not proof of savings.
            let leftDate = Self.date($0.lastNotifiedAt ?? "") ?? .distantPast
            let rightDate = Self.date($1.lastNotifiedAt ?? "") ?? .distantPast
            if leftDate != rightDate { return leftDate > rightDate }
            return $0.id < $1.id
        }
    }

    var message: String {
        if watches.isEmpty { return "Find a trip you like. Let Farelin watch for the next opportunity." }
        if monitoringCount > 0 {
            return "\(monitoringCount) watch\(monitoringCount == 1 ? " is" : "es are") set to check on schedule."
        }
        if watches.allSatisfy({ state(of: $0) == .expired }) {
            return "Your travel windows have ended. Choose fresh dates to keep exploring."
        }
        return "No watches are checking right now. You can review or resume them."
    }

    private func priority(_ watch: SavedWatchSummary) -> Int {
        switch state(of: watch) {
        case .watching: return 0
        case .waiting: return 1
        case .paused: return 2
        case .expired: return 3
        }
    }

    static func displayDate(_ value: String) -> String {
        guard let date = date(value) else { return "Date unavailable" }
        let formatter = DateFormatter()
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.setLocalizedDateFormatFromTemplate("d MMM yyyy")
        return formatter.string(from: date)
    }

    private static func startOfDay(_ date: Date) -> Date {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        return calendar.startOfDay(for: date)
    }

    private static func date(_ value: String) -> Date? {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let result = iso.date(from: value) { return result }
        iso.formatOptions = [.withInternetDateTime]
        if let result = iso.date(from: value) { return result }
        // The API also serializes UTC datetimes without a timezone suffix.
        if value.contains("T") {
            iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let result = iso.date(from: value + "Z") { return result }
            iso.formatOptions = [.withInternetDateTime]
            if let result = iso.date(from: value + "Z") { return result }
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.isLenient = false
        return formatter.date(from: String(value.prefix(10)))
    }
}

@MainActor
@Observable
final class DashboardStore {
    private(set) var dashboard: DashboardResponse?
    private(set) var isLoading = false
    private(set) var errorMessage: String?
    private(set) var workingWatchID: String?
    private(set) var completedWatchActions = 0

    private let service: any DashboardServicing
    private let reauthenticate: (@MainActor @Sendable () async -> Bool)?

    init(
        service: any DashboardServicing,
        reauthenticate: (@MainActor @Sendable () async -> Bool)? = nil
    ) {
        self.service = service
        self.reauthenticate = reauthenticate
    }

    func load(force: Bool = false) async {
        guard force || dashboard == nil else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            dashboard = try await service.dashboard()
        } catch APIError.unauthorized {
            guard let reauthenticate, await reauthenticate() else {
                errorMessage = APIError.unauthorized.errorDescription
                return
            }
            do {
                dashboard = try await service.dashboard()
            } catch {
                errorMessage = readable(error)
            }
        } catch {
            errorMessage = readable(error)
        }
    }

    func setWatch(_ watch: SavedWatchSummary, active: Bool) async {
        guard workingWatchID == nil else { return }
        workingWatchID = watch.id
        errorMessage = nil
        defer { workingWatchID = nil }
        do {
            _ = try await authenticated {
                if active {
                    return try await self.service.resumeWatch(id: watch.id)
                }
                return try await self.service.pauseWatch(id: watch.id)
            }
            await load(force: true)
            completedWatchActions += 1
        } catch {
            errorMessage = readable(error)
        }
    }

    func deleteWatch(_ watch: SavedWatchSummary) async {
        guard workingWatchID == nil else { return }
        workingWatchID = watch.id
        errorMessage = nil
        defer { workingWatchID = nil }
        do {
            try await authenticated { try await self.service.deleteWatch(id: watch.id) }
            await load(force: true)
            completedWatchActions += 1
        } catch {
            errorMessage = readable(error)
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
            ?? "Farelin could not load your dashboard."
    }
}
