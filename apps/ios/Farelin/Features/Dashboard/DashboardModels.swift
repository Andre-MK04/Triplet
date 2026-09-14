import Foundation
import Observation

protocol DashboardServicing: Sendable {
    func dashboard() async throws -> DashboardResponse
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
}

@MainActor
@Observable
final class DashboardStore {
    private(set) var dashboard: DashboardResponse?
    private(set) var isLoading = false
    private(set) var errorMessage: String?

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

    private func readable(_ error: Error) -> String {
        (error as? LocalizedError)?.errorDescription
            ?? "Farelin could not load your dashboard."
    }
}
