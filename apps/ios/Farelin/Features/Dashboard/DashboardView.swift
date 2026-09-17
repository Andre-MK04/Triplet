import SwiftUI

struct DashboardView: View {
    let user: AuthUser
    let store: DashboardStore
    let openDiscover: () -> Void
    let openWatch: (String) -> Void
    let openWatches: () -> Void
    @State private var showingUsage = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var textSize

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 24) {
                    welcome

                    if let dashboard = store.dashboard {
                        if let error = store.errorMessage { errorState(error) }
                        watchesSection(dashboard.savedSearches)
                        DisclosureGroup("Plan & usage", isExpanded: $showingUsage) {
                            VStack(spacing: 16) {
                                planCard(dashboard.billing)
                                usageSection(dashboard.usage)
                            }.padding(.top, 12)
                        }
                        .accessibilityIdentifier("today-usage")
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
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.22), value: showingUsage)
        }
    }

    private var welcome: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text("WELCOME BACK")
                .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
                .tracking(1.4)
                .foregroundStyle(FarelinColor.action)
            Text(user.displayName?.firstName.map { "Hello, \($0)." } ?? "Hello.")
                .font(FarelinTypography.display(size: 34, weight: .bold))
                .tracking(-0.8)
            Text(store.dashboard.map {
                TodayWatchOverview(watches: $0.savedSearches, now: Date()).message
            } ?? "Your next trip starts here.")
                .font(FarelinTypography.font(.body))
                .foregroundStyle(.secondary)
                .accessibilityIdentifier("today-status")
        }
        .padding(.top, 8)
    }

    private func planCard(_ billing: DashboardBilling) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Image(systemName: billing.plan == "pro" ? "sparkles" : "paperplane.fill")
                .font(FarelinTypography.font(.title2))
                .foregroundStyle(FarelinColor.mint)
                .frame(width: 34)
            VStack(alignment: .leading, spacing: 5) {
                Text(planName(billing.plan))
                    .font(FarelinTypography.font(.headline))
                Text(planDetail(billing))
                    .font(FarelinTypography.font(.subheadline))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text(billing.plan.uppercased())
                .font(FarelinTypography.font(.caption2, weight: .bold, family: .mono))
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
            let layout = textSize.isAccessibilitySize
                ? AnyLayout(VStackLayout(spacing: 12)) : AnyLayout(HStackLayout(spacing: 12))
            layout {
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
                    .font(FarelinTypography.font(.subheadline))
                Spacer()
            }
            .farelinCard()
        }
    }

    private func watchesSection(_ watches: [SavedWatchSummary]) -> some View {
        let overview = TodayWatchOverview(watches: watches, now: Date())
        return VStack(alignment: .leading, spacing: 12) {
            HStack {
                sectionTitle("Saved watches")
                Spacer()
                if !watches.isEmpty {
                    Button("See all", action: openWatches)
                        .font(FarelinTypography.font(.subheadline, weight: .semibold))
                        .accessibilityIdentifier("today-all-watches")
                }
            }

            if watches.isEmpty {
                VStack(alignment: .leading, spacing: 14) {
                    Image(systemName: "bell.slash")
                        .font(FarelinTypography.font(.title2))
                        .foregroundStyle(FarelinColor.coral)
                    Text("No saved watches yet")
                        .font(FarelinTypography.font(.headline))
                    Text("Find a trip you like and Farelin can keep checking it for you.")
                        .font(FarelinTypography.font(.subheadline))
                        .foregroundStyle(.secondary)
                    Button("Find a trip", action: openDiscover)
                        .buttonStyle(FarelinPrimaryButtonStyle())
                        .accessibilityIdentifier("today-discover")
                }
                .farelinCard()
            } else {
                ForEach(overview.orderedWatches.prefix(3)) { watch in
                    Button { openWatch(watch.id) } label: {
                        WatchSummaryCard(watch: watch, state: overview.state(of: watch))
                    }
                    .buttonStyle(TodayWatchButtonStyle())
                    .accessibilityIdentifier("today-watch-\(watch.id)")
                }
                Button("Explore another trip", systemImage: "magnifyingglass", action: openDiscover)
                    .frame(minHeight: 44)
            }
        }
    }

    private var loadingState: some View {
        VStack(spacing: 14) {
            ProgressView()
            Text("Loading your Farelin world…")
                .font(FarelinTypography.font(.subheadline))
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 180)
        .farelinCard()
    }

    private func errorState(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Your dashboard could not load", systemImage: "wifi.exclamationmark")
                .font(FarelinTypography.font(.headline))
            Text(message)
                .font(FarelinTypography.font(.subheadline))
                .foregroundStyle(.secondary)
            Button("Try again") { Task { await store.load(force: true) } }
                .buttonStyle(FarelinPrimaryButtonStyle())
        }
        .farelinCard()
    }

    private func sectionTitle(_ title: String) -> some View {
        Text(title.uppercased())
            .font(FarelinTypography.font(.caption2, weight: .semibold, family: .mono))
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
                .font(FarelinTypography.font(.caption))
                .foregroundStyle(.secondary)
            if unlimited {
                Text("Unlimited")
                    .font(FarelinTypography.font(.title3, weight: .semibold))
                    .foregroundStyle(FarelinColor.mint)
            } else {
                Text("\(used) / \(limit)")
                    .font(FarelinTypography.font(.title3, weight: .semibold).monospacedDigit())
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
    let state: TodayWatchOverview.State

    var body: some View {
        VStack(alignment: .leading, spacing: 13) {
            HStack(alignment: .firstTextBaseline) {
                Text(watch.name ?? "Trip watch")
                    .font(FarelinTypography.font(.headline))
                Spacer()
                Image(systemName: "chevron.right")
                    .font(FarelinTypography.font(.caption, weight: .semibold))
                    .accessibilityHidden(true)
            }
            Text(state.rawValue)
                .font(FarelinTypography.font(.caption, weight: .semibold))
                .foregroundStyle(state == .watching ? FarelinColor.action : Color.secondary)
            Text(watch.routeDescription)
                .font(FarelinTypography.font(.subheadline, weight: .medium, family: .mono))
            VStack(alignment: .leading, spacing: 5) {
                Label("Up to €\(watch.maxBudget, specifier: "%.0f")", systemImage: "eurosign.circle")
                Label(watch.frequency.capitalized, systemImage: "calendar")
                Text("\(TodayWatchOverview.displayDate(watch.startDate)) – \(TodayWatchOverview.displayDate(watch.endDate))")
            }
            .font(FarelinTypography.font(.caption))
            .foregroundStyle(.secondary)
            if let price = watch.lastBestPrice {
                Text("Best observed: €\(price, specifier: "%.0f")")
                    .font(FarelinTypography.font(.subheadline, weight: .semibold))
                    .foregroundStyle(FarelinColor.action)
            }
            if let checked = watch.lastCheckedAt {
                Text("Last checked \(TodayWatchOverview.displayDate(checked)) · price may change")
                    .font(FarelinTypography.font(.caption)).foregroundStyle(.secondary)
            }
            Text(state == .expired ? "Choose new dates" : state == .paused ? "Review or resume" : "View trips & history")
                .font(FarelinTypography.font(.subheadline, weight: .semibold))
                .foregroundStyle(FarelinColor.action)
        }
        .farelinCard()
        .accessibilityElement(children: .combine)
    }

}

private struct TodayWatchButtonStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(reduceMotion ? 1 : configuration.isPressed ? 0.988 : 1)
            .opacity(configuration.isPressed ? 0.84 : 1)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.16), value: configuration.isPressed)
    }
}

private extension String {
    var firstName: String? {
        split(whereSeparator: { $0.isWhitespace }).first.map(String.init)
    }
}
