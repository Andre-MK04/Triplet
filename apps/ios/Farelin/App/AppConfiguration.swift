import Foundation

enum FarelinEnvironment: String, Sendable {
    case staging
    case production
}

enum ConfigurationError: LocalizedError, Equatable {
    case missing(String)
    case invalidEnvironment(String)
    case invalidAPIURL
    case insecureAPIURL
    case environmentHostMismatch

    var errorDescription: String? {
        switch self {
        case .missing(let key): "Missing \(key)."
        case .invalidEnvironment: "Unknown app environment."
        case .invalidAPIURL: "The API URL is invalid."
        case .insecureAPIURL: "The API URL must use HTTPS."
        case .environmentHostMismatch: "The app environment and API host do not match."
        }
    }
}

struct AppConfiguration: Sendable, Equatable {
    let environment: FarelinEnvironment
    let apiBaseURL: URL

    static func current(bundle: Bundle = .main) throws -> AppConfiguration {
        guard let environment = bundle.object(forInfoDictionaryKey: "AppEnvironment") as? String else {
            throw ConfigurationError.missing("AppEnvironment")
        }
        guard let apiBaseURL = bundle.object(forInfoDictionaryKey: "APIBaseURL") as? String else {
            throw ConfigurationError.missing("APIBaseURL")
        }
        return try AppConfiguration(environmentValue: environment, apiBaseURLValue: apiBaseURL)
    }

    init(environmentValue: String, apiBaseURLValue: String) throws {
        guard let environment = FarelinEnvironment(rawValue: environmentValue) else {
            throw ConfigurationError.invalidEnvironment(environmentValue)
        }
        guard let url = URL(string: apiBaseURLValue), url.host != nil else {
            throw ConfigurationError.invalidAPIURL
        }
        guard url.scheme == "https" else {
            throw ConfigurationError.insecureAPIURL
        }
        let host = url.host?.lowercased() ?? ""
        if environment == .production, host.contains("staging") {
            throw ConfigurationError.environmentHostMismatch
        }
        if environment == .staging, !host.contains("staging") {
            throw ConfigurationError.environmentHostMismatch
        }
        self.environment = environment
        self.apiBaseURL = url
    }
}

