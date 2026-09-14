import SwiftUI

struct DashboardView: View {
    let user: AuthUser
    let store: DashboardStore
    let openDiscover: () -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 24) {
                    welcome

                    if let dashboard = store.dashboard {
                        planCard(dashboard.billing)
                        usageSection(dashboard.usage)
                        watchesSection(dashboard.savedSearches)
                    } else if store.isLoading {
                        loadingState
                    } else if let error = store.errorMessage {
                        errorState(error)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 32)
            }
            .background(Color(.systemBackground))
            .navigationTitle("Today")
            .refreshable { await store.load(force: true) }
            .task { await store.load() }
        }
    }

    private var welcome: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("WELCOME BACK")
                .font(.caption2.monospaced().weight(.semibold))
                .tracking(1.4)
                .foregroundStyle(FarelinColor.mint)
            Text(user.displayName?.firstName.map { "Hello, \($0)." } ?? "Hello.")
                .font(.system(size: 34, weight: .bold, design: .rounded))
                .tracking(-0.8)
            Text("Your fares are being watched quietly.")
                .font(.body)
                .foregroundStyle(.secondary)
        }
        .padding(.top, 8)
    }

    private func planCard(_ billing: DashboardBilling) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: billing.plan == "pro" ? "sparkles" : "paperplane.fill")
                .font(.title2)
                .foregroundStyle(FarelinColor.mint)
                .frame(width: 34)
            VStack(alignment: .leading, spacing: 5) {
                Text(planName(billing.plan))
                    .font(.headline)
                Text(planDetail(billing))
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text(billing.plan.uppercased())
                .font(.caption2.monospaced().weight(.bold))
                .tracking(1)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(FarelinColor.mint.opacity(0.16), in: Capsule())
        }
        .farelinCard()
        .accessibilityElement(children: .combine)
    }

    private func usageSection(_ usage: DashboardUsage) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            sectionTitle("This month")
            HStack(spacing: 12) {
                UsageCard(
                    title: "AI searches",
                    used: usage.aiSearchesThisMonth,
                    limit: usage.aiSearchesPerMonth,
                    unlimited: usage.unlimited,
                    symbol: "wand.and.stars"
                )
                UsageCard(
                    title: "Saved watches",
                    used: usage.activeSavedSearches,
                    limit: usage.savedSearchLimit,
                    unlimited: usage.unlimited,
                    symbol: "bell.badge"
                )
            }
            HStack(spacing: 9) {
                Image(systemName: "clock.arrow.circlepath")
                    .foregroundStyle(FarelinColor.mint)
                Text(usage.dailyWatchChecks ? "Daily and weekly fare checks available" : "Weekly fare checks")
                    .font(.subheadline)
                Spacer()
            }
            .farelinCard()
        }
    }

    private func watchesSection(_ watches: [SavedWatchSummary]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionTitle("Saved watches")
                Spacer()
                if !watches.isEmpty {
                    Text("\(watches.filter(\.isActive).count) active")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if watches.isEmpty {
                VStack(alignment: .leading, spacing: 14) {
                    Image(systemName: "bell.slash")
                        .font(.title2)
                        .foregroundStyle(FarelinColor.coral)
                    Text("No saved watches yet")
                        .font(.headline)
                    Text("Find a trip you like and Farelin can keep checking it for you.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Button("Find a trip", action: openDiscover)
                        .buttonStyle(FarelinPrimaryButtonStyle())
                }
                .farelinCard()
            } else {
                ForEach(watches.prefix(3)) { watch in
                    WatchSummaryCard(watch: watch)
                }
            }
        }
    }

    private var loadingState: some View {
        VStack(spacing: 14) {
            ProgressView()
            Text("Loading your Farelin world…")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 180)
        .farelinCard()
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Your dashboard could not load", systemImage: "wifi.exclamationmark")
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Button("Try again") { Task { await store.load(force: true) } }
                .buttonStyle(FarelinPrimaryButtonStyle())
        }
        .farelinCard()
    }

    private func sectionTitle(_ title: String) -> some View {
        Text(title.uppercased())
            .font(.caption2.monospaced().weight(.semibold))
            .tracking(1.3)
            .foregroundStyle(.secondary)
    }

    private func planName(_ plan: String) -> String {
        switch plan {
        case "trial": "Farelin Pro trial"
        case "pro": "Farelin Pro"
        case "owner": "Farelin Owner"
        default: "Farelin Free"
        }
    }

    private func planDetail(_ billing: DashboardBilling) -> String {
        if billing.plan == "trial" {
            return "\(billing.trialDaysRemaining) days remain in your trial."
        }
        if billing.plan == "pro" || billing.plan == "owner" {
            return "Your enhanced travel tools are active."
        }
        return "A focused start for finding and watching trips."
    }
}

private struct UsageCard: View {
    let title: String
    let used: Int
    let limit: Int
    let unlimited: Bool
    let symbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Image(systemName: symbol)
                .foregroundStyle(FarelinColor.mint)
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            if unlimited {
                Text("Unlimited")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(FarelinColor.mint)
            } else {
                Text("\(used) / \(limit)")
                    .font(.title3.monospacedDigit().weight(.semibold))
                ProgressView(value: Double(used), total: Double(max(limit, 1)))
                    .tint(FarelinColor.mint)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .farelinCard()
        .accessibilityElement(children: .combine)
    }
}

private struct WatchSummaryCard: View {
    let watch: SavedWatchSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(alignment: .firstTextBaseline) {
                Text(watch.name ?? "Trip watch")
                    .font(.headline)
                    .lineLimit(1)
                Spacer()
                Circle()
                    .fill(watch.isActive ? FarelinColor.mint : Color.secondary)
                    .frame(width: 8, height: 8)
                    .accessibilityLabel(watch.isActive ? "Active" : "Paused")
            }
            Text(route)
                .font(.subheadline.monospaced().weight(.medium))
            HStack {
                Label("Up to €\(watch.maxBudget, specifier: "%.0f")", systemImage: "eurosign.circle")
                Spacer()
                Label(watch.frequency.capitalized, systemImage: "calendar")
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            if let price = watch.lastBestPrice {
                Text("Best observed: €\(price, specifier: "%.0f")")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(FarelinColor.mint)
            }
        }
        .farelinCard()
    }

    private var route: String {
        let origins = watch.originAirports.joined(separator: " + ")
        let destinations = watch.destinationAirports?.joined(separator: " + ") ?? "Anywhere"
        return "\(origins) → \(destinations)"
    }
}

private extension String {
    var firstName: String? {
        split(whereSeparator: { $0.isWhitespace }).first.map(String.init)
    }
}
